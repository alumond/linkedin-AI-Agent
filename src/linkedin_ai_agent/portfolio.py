"""Public, inspectable GitHub evidence for posts about the user's own builds."""
from __future__ import annotations

import base64
import os
import re
from pathlib import PurePosixPath
from urllib.parse import quote, urlparse

import requests


ANGLES = ("problem", "user-experience", "implementation", "workflow", "data-quality",
          "validation", "design-decision", "limitation", "next-improvement")
DEMO_HOST_SUFFIXES = (
    "streamlit.app",
    "appdeploy.ai",
    "vercel.app",
    "netlify.app",
    "onrender.com",
    "github.io",
)
TELEGRAM_HOSTS = ("t.me", "telegram.me")
SCREENSHOT_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def excluded_material(text: str, terms: list[str]) -> bool:
    compact = re.sub(r"[^a-z0-9]", "", text.casefold())
    return any(re.sub(r"[^a-z0-9]", "", term.casefold()) in compact for term in terms if term.strip())


class GitHubProjects:
    def __init__(self, owner: str, excluded_terms: list[str] | None = None,
                 project_overrides: dict[str, dict] | None = None) -> None:
        self.owner = owner
        self.excluded_terms = excluded_terms or []
        self.project_overrides = project_overrides or {}
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/vnd.github+json",
                                     "X-GitHub-Api-Version": "2022-11-28"})
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def _get(self, path: str):
        response = self.session.get(f"https://api.github.com/repos/{quote(self.owner, safe='')}/{path}", timeout=30)
        response.raise_for_status()
        return response.json()

    def _verified_demo_url(self, homepage: str | None, readme_text: str) -> str:
        links = self._verified_public_links(homepage, readme_text, [])
        return next((item["url"] for item in links if item["kind"] == "public_demo"), "")

    def _verified_public_links(self, homepage: str | None, readme_text: str,
                               configured: list[dict]) -> list[dict]:
        """Return only reachable, explicitly classified public experiences."""
        raw_links: list[dict] = []
        if configured:
            raw_links.extend(configured)
        else:
            candidates = [homepage or ""]
            candidates.extend(re.findall(r"https://[^\s)\]>\"']+", readme_text))
            raw_links.extend({"kind": "public_demo", "label": "Try the app", "url": item}
                             for item in candidates if item)

        verified: list[dict] = []
        seen: set[str] = set()
        for item in raw_links:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind", "")).strip().casefold()
            candidate = str(item.get("url", "")).strip().rstrip(".,;")
            parsed = urlparse(candidate)
            host = (parsed.hostname or "").casefold()
            if candidate in seen or parsed.scheme != "https" or parsed.username or parsed.password:
                continue
            if kind == "public_demo":
                allowed = any(host == suffix or host.endswith("." + suffix)
                              for suffix in DEMO_HOST_SUFFIXES)
                default_label = "Try the app"
            elif kind == "telegram":
                allowed = host in TELEGRAM_HOSTS and bool(parsed.path.strip("/"))
                default_label = "Open the Telegram bot"
            else:
                continue
            if not allowed:
                continue
            try:
                response = self.session.get(candidate, timeout=15, allow_redirects=True, stream=True)
                response.close()
            except requests.RequestException:
                continue
            if response.status_code >= 400:
                continue
            seen.add(candidate)
            verified.append({"kind": kind, "label": str(item.get("label") or default_label),
                             "url": candidate})
        return verified

    def _screenshot_from_override(self, project_name: str, project_url: str) -> dict | None:
        configured = self.project_overrides.get(project_name, {}).get("screenshot")
        if not isinstance(configured, dict):
            return None
        repository = str(configured.get("repository", "")).rstrip("/")
        image_path = str(configured.get("path", "")).strip("/")
        parsed = urlparse(repository)
        parts = parsed.path.strip("/").split("/")
        if (parsed.scheme != "https" or parsed.netloc.casefold() != "github.com"
                or len(parts) != 2 or parts[0].casefold() != self.owner.casefold()
                or PurePosixPath(image_path).suffix.casefold() not in SCREENSHOT_SUFFIXES):
            raise ValueError(f"Invalid screenshot source configured for {project_name}.")
        source_repo = quote(parts[1], safe="")
        source_meta = self._get(source_repo)
        source_branch = source_meta["default_branch"]
        source_commit = self._get(f"{source_repo}/commits/{quote(source_branch, safe='')}")["sha"]
        content = self._get(f"{source_repo}/contents/{quote(image_path, safe='/')}")
        if (content.get("type") != "file" or not content.get("sha")
                or not content.get("download_url") or content.get("size", 0) <= 0):
            raise ValueError(f"Screenshot source is not a downloadable repository image for {project_name}.")
        return {
            "project_repository": project_url,
            "source_repository": repository,
            "source_url": f"{repository}/blob/{source_commit}/{quote(content['path'], safe='/')}",
            "download_url": (f"https://raw.githubusercontent.com/{quote(self.owner, safe='')}/"
                             f"{source_repo}/{source_commit}/{quote(content['path'], safe='/')}"),
            "source_commit_sha": source_commit,
            "source_blob_sha": content["sha"],
            "path": content["path"],
            "size": content["size"],
        }

    @staticmethod
    def _tree_screenshot(project_url: str, tree: list[dict]) -> dict | None:
        images = [item for item in tree if item.get("type") == "blob"
                  and PurePosixPath(item.get("path", "")).suffix.casefold() in SCREENSHOT_SUFFIXES
                  and 0 < item.get("size", 0) < 20_000_000]
        if not images:
            return None
        def priority(item: dict) -> tuple:
            path = item["path"].casefold()
            return (not any(word in path for word in ("screenshot", "preview", "dashboard", "app", "ui")), path)
        item = sorted(images, key=priority)[0]
        return {
            "project_repository": project_url,
            "source_repository": project_url,
            "source_url": f"{project_url}/blob/{{branch}}/{quote(item['path'], safe='/')}",
            "download_url": "",
            "source_blob_sha": item["sha"],
            "path": item["path"],
            "size": item["size"],
        }

    def collect(self, names: list[str], history: list[dict], limit: int = 4, exclude: set | None = None) -> list[dict]:
        response = self.session.get(f"https://api.github.com/users/{quote(self.owner, safe='')}/repos",
                                    params={"per_page": 100, "sort": "updated"}, timeout=30)
        response.raise_for_status()
        discovered = [repo["name"] for repo in response.json()
                      if not repo.get("private") and not repo.get("fork")
                      and repo["name"] != "linkedin-AI-Agent"]
        names = [name for name in dict.fromkeys(names + discovered) if name not in (exclude or set())]
        # Alternate projects before revisiting a build from a new angle.
        def coverage(name: str) -> int:
            prefix = f"https://github.com/{self.owner}/{name}"
            return sum(str(item.get("primary_source_url", "")).rstrip("/") == prefix for item in history)

        projects = []
        failures = []
        for name in sorted(names, key=coverage):
            try:
                project = self.read_project(name)
                if project:
                    projects.append(project)
            except (requests.RequestException, ValueError, KeyError) as exc:
                failures.append(f"{name}: {type(exc).__name__}")
            if len(projects) >= limit:
                break
        if not projects:
            raise RuntimeError("No public project evidence could be read. " + "; ".join(failures))
        return projects

    def read_project(self, name: str) -> dict | None:
        repo = quote(name, safe="")
        meta = self._get(repo)
        if meta.get("private") or meta.get("fork"):
            return None
        if excluded_material(name + " " + (meta.get("description") or ""), self.excluded_terms):
            return None
        readme = self._get(f"{repo}/readme")
        files = [{"url": readme["html_url"], "path": readme["path"],
                  "text": base64.b64decode(readme["content"]).decode("utf-8")[:12000]}]
        branch = meta["default_branch"]
        tree = self._get(f"{repo}/git/trees/{quote(branch, safe='')}?recursive=1").get("tree", [])
        if excluded_material(files[0]["text"] + " ".join(item["path"] for item in tree), self.excluded_terms):
            return None
        def eligible(item):
            path = item["path"]
            return (item["type"] == "blob" and item.get("size", 0) < 50000
                    and PurePosixPath(path).suffix in {".py", ".js", ".ts", ".tsx", ".html"}
                    and not any(part in path.lower() for part in
                                ("node_modules", "vendor", "lock", "secret", "credential", "config", "test", "migration", "generated")))
        choices = sorted((item for item in tree if eligible(item)),
                         key=lambda item: (not any(word in item["path"] for word in ("analytics", "main", "engine", "dashboard")), item["path"]))
        for item in choices[:2]:
            content = self._get(f"{repo}/contents/{quote(item['path'], safe='/')}?ref={quote(branch, safe='')}")
            files.append({"url": content["html_url"], "path": item["path"],
                          "text": base64.b64decode(content["content"]).decode("utf-8")[:12000]})
        if any(excluded_material(file["text"], self.excluded_terms) for file in files):
            return None
        commits = self._get(f"{repo}/commits?per_page=3")
        updates = [{"url": commit["html_url"], "message": commit["commit"]["message"][:500],
                    "date": commit["commit"]["committer"]["date"]} for commit in commits]
        override = self.project_overrides.get(name, {})
        public_links = self._verified_public_links(meta.get("homepage"), files[0]["text"],
                                                   list(override.get("public_links", [])))
        demo_url = next((item["url"] for item in public_links if item["kind"] == "public_demo"), "")
        evidence_text = "\n".join(file["text"] for file in files)
        missing_public_links: list[str] = []
        if re.search(r"\btelegram\s+bot\b", evidence_text, re.IGNORECASE) and not any(
                item["kind"] == "telegram" for item in public_links):
            missing_public_links.append("verified public Telegram bot URL")
        screenshot = self._screenshot_from_override(name, meta["html_url"])
        if not screenshot:
            screenshot = self._tree_screenshot(meta["html_url"], tree)
            if screenshot:
                screenshot["source_url"] = screenshot["source_url"].format(branch=quote(branch, safe=""))
                screenshot["download_url"] = (
                    f"https://raw.githubusercontent.com/{quote(self.owner, safe='')}/{repo}/"
                    f"{quote(branch, safe='')}/{quote(screenshot['path'], safe='/')}"
                )
        return {"name": name, "url": meta["html_url"], "description": meta.get("description"),
                "files": files, "recent_updates": updates, "updated_at": meta.get("pushed_at"),
                "commit": commits[0]["sha"] if commits else "", "demo_url": demo_url,
                "public_links": public_links, "screenshots": [screenshot] if screenshot else [],
                "missing_public_links": missing_public_links}
