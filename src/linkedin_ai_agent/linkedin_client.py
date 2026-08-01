from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from .config import AgentConfig
from .models import DraftPost, VisualAsset


LINKEDIN_API = "https://api.linkedin.com/rest"
LINKEDIN_OAUTH = "https://www.linkedin.com/oauth/v2"


@dataclass
class LinkedInClient:
    access_token: str
    config: AgentConfig

    @classmethod
    def from_env(cls, config: AgentConfig, require_owner: bool = True) -> "LinkedInClient":
        token = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
        if not token:
            raise RuntimeError("LINKEDIN_ACCESS_TOKEN is required for live publishing.")
        if require_owner and not config.linkedin_owner_urn:
            raise RuntimeError("linkedin.owner_urn must be set in config for live publishing.")
        return cls(access_token=token, config=config)

    def headers(self, content_type: str | None = "application/json") -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Linkedin-Version": self.config.linkedin_version,
        }
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def initialize_image_upload(self) -> tuple[str, str]:
        payload = {"initializeUploadRequest": {"owner": self.config.linkedin_owner_urn}}
        response = _request_with_retries(
            "POST",
            f"{LINKEDIN_API}/images?action=initializeUpload",
            headers=self.headers(),
            json=payload,
        )
        value = response.json().get("value", {})
        upload_url = value.get("uploadUrl")
        image_urn = value.get("image")
        if not upload_url or not image_urn:
            raise RuntimeError(f"LinkedIn image initialization failed: {response.text[:500]}")
        return upload_url, image_urn

    def upload_image(self, visual: VisualAsset) -> str:
        upload_url, image_urn = self.initialize_image_upload()
        data = Path(visual.path).read_bytes()
        _request_with_retries(
            "PUT",
            upload_url,
            headers={"Authorization": f"Bearer {self.access_token}", "Content-Type": visual.mime_type},
            data=data,
        )
        return image_urn

    def publish_post(self, draft: DraftPost, image_urn: str) -> str:
        commentary = draft.body.strip()
        if draft.primary_source_url and draft.primary_source_url not in commentary:
            commentary += f"\n\nSource: {draft.primary_source_url}"
        if draft.hashtags:
            commentary += "\n\n" + " ".join(draft.hashtags)
        payload: dict[str, Any] = {
            "author": self.config.linkedin_owner_urn,
            "commentary": commentary,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "content": {"media": {"id": image_urn, "title": draft.topic[:200]}},
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        response = _request_with_retries(
            "POST",
            f"{LINKEDIN_API}/posts",
            headers=self.headers(),
            json=payload,
            expected=(201,),
        )
        post_urn = response.headers.get("x-restli-id") or response.headers.get("X-RestLi-Id")
        if not post_urn:
            try:
                post_urn = response.json().get("id", "")
            except ValueError:
                post_urn = ""
        if not post_urn:
            raise RuntimeError("LinkedIn returned success without a post URN.")
        return post_urn

    def userinfo(self) -> dict[str, Any]:
        response = _request_with_retries(
            "GET",
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        data = response.json()
        if "sub" in data:
            data["owner_urn"] = f"urn:li:person:{data['sub']}"
        return data


def exchange_code_for_token(code: str, redirect_uri: str) -> dict[str, Any]:
    client_id = os.environ.get("LINKEDIN_CLIENT_ID", "")
    client_secret = os.environ.get("LINKEDIN_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise RuntimeError("LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET are required.")
    response = requests.post(
        f"{LINKEDIN_OAUTH}/accessToken",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def authorization_url(redirect_uri: str, state: str) -> str:
    client_id = os.environ.get("LINKEDIN_CLIENT_ID", "")
    if not client_id:
        raise RuntimeError("LINKEDIN_CLIENT_ID is required.")
    return (
        f"{LINKEDIN_OAUTH}/authorization?response_type=code"
        f"&client_id={client_id}&redirect_uri={redirect_uri}"
        f"&state={state}&scope=w_member_social%20openid%20profile"
    )


def linkedin_token_expires_at(token_response: dict[str, Any]) -> str:
    from datetime import datetime, timedelta, timezone

    expires_in = int(token_response.get("expires_in", 60 * 60 * 24 * 60))
    return (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat(timespec="seconds").replace("+00:00", "Z")


def _request_with_retries(method: str, url: str, expected: tuple[int, ...] = (200, 201, 202), **kwargs: Any) -> requests.Response:
    retryable = {408, 429, 500, 502, 503, 504}
    last: requests.Response | None = None
    for attempt in range(4):
        response = requests.request(method, url, timeout=60, **kwargs)
        if response.status_code in expected:
            return response
        last = response
        if response.status_code not in retryable:
            break
        time.sleep(2**attempt)
    assert last is not None
    last.raise_for_status()
    return last
