"""Public, inspectable GitHub evidence for posts about the user's own builds."""
from __future__ import annotations

import base64
import os
import re
from pathlib import PurePosixPath
from urllib.parse import quote

import requests


ANGLES = ("problem", "user-experience", "implementation", "data-quality",
          "validation", "design-decision", "limitation", "next-improvement")


def excluded_material(text: str, terms: list[str]) -> bool:
    compact = re.sub(r"[^a-z0-9]", "", text.casefold())
    return any(re.sub(r"[^a-z0-9]", "", term.casefold()) in compact for term in terms if term.strip())


class GitHubProjects:
    def __init__(self, owner: str, excluded_terms: list[str] | None = None) -> None:
        self.owner = owner
        self.excluded_terms = excluded_terms or []
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
        return {"name": name, "url": meta["html_url"], "description": meta.get("description"),
                "files": files, "recent_updates": updates, "updated_at": meta.get("pushed_at")}
