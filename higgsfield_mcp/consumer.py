"""
Higgsfield Consumer API Client
Accesses the fnf.higgsfield.ai backend via Clerk JWT auth (email/password login)
"""
import time
from typing import Optional, List, Dict, Any

from .auth import ClerkSession, requests

API_BASE = "https://fnf.higgsfield.ai"

# Models available on the consumer backend
IMAGE_MODELS = {
    "z-image": "/jobs/z-image",
    "soul": "/jobs/text2image-soul",
    "flux-2": "/jobs/flux-2",
    "flux2": "/jobs/flux-2",
    "gpt": "/jobs/text2image-gpt",
    "nano-banana-2": "/jobs/nano-banana-2",
    "nano-banana-2-static": "/jobs/nano-banana-2-static",
    "seedream": "/jobs/seedream",
    "seedream-v4-5": "/jobs/seedream-v4-5",
}

VIDEO_MODELS = {
    "kling3_0": "/jobs/v2/kling3_0",
    "kling": "/jobs/kling",
    "veo3": "/jobs/veo3",
    "wan2-5-video": "/jobs/wan2-5-video",
    "minimax-hailuo": "/jobs/minimax-hailuo",
    "sora2-video": "/jobs/sora2-video",
    "seedance": "/jobs/seedance",
    "image2video": "/jobs/image2video",
}


class HiggsfieldConsumerClient:
    """Async-compatible client for Higgsfield consumer API (fnf.higgsfield.ai)"""

    def __init__(self, auth: ClerkSession):
        self.auth = auth

    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Make an authenticated request to the consumer API."""
        self.auth._warmup_cloudflare()
        if not self.auth.ensure_auth():
            raise RuntimeError("Not authenticated. Run login first or check credentials.")

        headers = self.auth.get_auth_header()
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        resp = self.auth._session.request(
            method,
            f"{API_BASE}{path}",
            headers=headers,
            **kwargs,
        )

        if resp.status_code == 200:
            return resp.json()
        raise RuntimeError(f"API error {resp.status_code}: {resp.text}")

    def generate_image(
        self,
        prompt: str,
        model: str = "z-image",
        width: int = 1024,
        height: int = 1024,
        aspect_ratio: str = "1:1",
        batch_size: int = 1,
        seed: Optional[int] = None,
        enhance_prompt: bool = True,
    ) -> Dict[str, Any]:
        endpoint = IMAGE_MODELS.get(model)
        if not endpoint:
            raise ValueError(f"Unknown image model: {model}. Available: {list(IMAGE_MODELS.keys())}")

        params: Dict[str, Any] = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "aspect_ratio": aspect_ratio,
            "batch_size": batch_size,
            "enhance_prompt": enhance_prompt,
        }
        if seed is not None:
            params["seed"] = seed

        return self._request("POST", endpoint, json={"params": params})

    def generate_video(
        self,
        prompt: str,
        model: str = "kling3_0",
        aspect_ratio: str = "16:9",
        duration: int = 5,
        sound: str = "on",
        enhance_prompt: bool = True,
    ) -> Dict[str, Any]:
        endpoint = VIDEO_MODELS.get(model)
        if not endpoint:
            raise ValueError(f"Unknown video model: {model}. Available: {list(VIDEO_MODELS.keys())}")

        params: Dict[str, Any] = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "duration": duration,
            "sound": sound,
            "enhance_prompt": enhance_prompt,
        }

        return self._request("POST", endpoint, json={"params": params})

    def get_job_results(self, job_set_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/job-sets/{job_set_id}")

    def get_account_info(self) -> Dict[str, Any]:
        return self._request("GET", "/users/me")

    def get_history(self, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        return self._request("GET", "/jobs", params={"page": page, "page_size": page_size})
