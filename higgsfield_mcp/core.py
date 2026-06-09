"""
Higgsfield AI API Client
Async wrapper for the Higgsfield AI platform API
"""
import httpx
from typing import Optional, List, Dict, Any


class HiggsfieldClient:
    """Async client for Higgsfield AI API"""

    def __init__(self, api_key: str, secret: str, base_url: str = "https://platform.higgsfield.ai"):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Key {api_key}:{secret}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "higgsfield-server-js/2.0",
        }

    # ------------------------------------------------------------------
    # Image generation
    # ------------------------------------------------------------------

    async def generate_image(
        self,
        prompt: str,
        quality: str = "1080p",
        batch_size: int = 1,
        custom_reference_id: Optional[str] = None,
        style_id: Optional[str] = None,
        width_and_height: str = "2048x1152",
        enhance_prompt: bool = False,
        webhook_url: Optional[str] = None,
        webhook_secret: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "prompt": prompt,
            "width_and_height": width_and_height,
            "enhance_prompt": enhance_prompt,
            "quality": quality,
            "batch_size": batch_size,
        }
        if custom_reference_id:
            params["custom_reference_id"] = custom_reference_id
        if style_id:
            params["style_id"] = style_id

        body: Dict[str, Any] = {"params": params}
        if webhook_url:
            body["webhook"] = {"url": webhook_url, "secret": webhook_secret or ""}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/v1/text2image/soul",
                headers=self.headers,
                json=body,
            )
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Video generation
    # ------------------------------------------------------------------

    async def generate_video(
        self,
        image_url: str,
        motion_id: str,
        prompt: str = "",
        model: str = "dop-preview",
        webhook_url: Optional[str] = None,
        webhook_secret: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not prompt:
            prompt = "Cinematic video with natural motion"

        params = {
            "model": model,
            "prompt": prompt,
            "input_images": [{"type": "image_url", "image_url": image_url}],
            "motions": [{"id": motion_id, "strength": 0.5}],
        }

        body: Dict[str, Any] = {"params": params}
        if webhook_url:
            body["webhook"] = {"url": webhook_url, "secret": webhook_secret or ""}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/v1/image2video/dop",
                headers=self.headers,
                json=body,
            )
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Talking head (Speak v2)
    # ------------------------------------------------------------------

    async def generate_talking_head(
        self,
        image_url: str,
        audio_url: str,
        prompt: str,
        quality: str = "high",
        duration: int = 5,
        enhance_prompt: bool = False,
        seed: int = 42,
        webhook_url: Optional[str] = None,
        webhook_secret: Optional[str] = None,
    ) -> Dict[str, Any]:
        params = {
            "input_image": {"type": "image_url", "image_url": image_url},
            "input_audio": {"type": "audio_url", "audio_url": audio_url},
            "prompt": prompt,
            "quality": quality,
            "duration": duration,
            "enhance_prompt": enhance_prompt,
            "seed": seed,
        }

        body: Dict[str, Any] = {"params": params}
        if webhook_url:
            body["webhook"] = {"url": webhook_url, "secret": webhook_secret or ""}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/v1/speak/higgsfield",
                headers=self.headers,
                json=body,
            )
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Character references (full CRUD)
    # ------------------------------------------------------------------

    async def create_character(self, name: str, image_urls: List[str]) -> Dict[str, Any]:
        payload = {
            "name": name,
            "input_images": [{"type": "image_url", "image_url": url} for url in image_urls],
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/v1/custom-references",
                headers=self.headers,
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    async def update_character(
        self, character_id: str, name: Optional[str] = None, image_urls: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if image_urls is not None:
            payload["input_images"] = [
                {"type": "image_url", "image_url": url} for url in image_urls
            ]
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.put(
                f"{self.base_url}/v1/custom-references/{character_id}",
                headers=self.headers,
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_character(self, character_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/v1/custom-references/{character_id}",
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def delete_character(self, character_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(
                f"{self.base_url}/v1/custom-references/{character_id}",
                headers=self.headers,
            )
            resp.raise_for_status()
            return {"success": True, "character_id": character_id}

    async def list_characters(
        self, page: int = 1, page_size: int = 20
    ) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/v1/custom-references/list",
                headers=self.headers,
                params={"page": page, "page_size": page_size},
            )
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Job management
    # ------------------------------------------------------------------

    async def get_job_results(self, job_set_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/v1/job-sets/{job_set_id}",
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def list_jobs(
        self, page: int = 1, page_size: int = 20
    ) -> Dict[str, Any]:
        """List recent jobs for history / iteration."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/v1/job-sets",
                headers=self.headers,
                params={"page": page, "page_size": page_size},
            )
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Browsable data (styles, motions)
    # ------------------------------------------------------------------

    async def list_styles(self) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/v1/text2image/soul-styles",
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def list_motions(self) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/v1/motions",
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Usage / billing
    # ------------------------------------------------------------------

    async def get_usage_stats(self) -> Dict[str, Any]:
        """Fetch credit balance and recent usage from billing endpoint."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/v1/billing/credits",
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Upscale / Enhance
    # ------------------------------------------------------------------

    async def upscale_media(
        self,
        media_url: str,
        model: str = "soul-pro",
    ) -> Dict[str, Any]:
        """Upscale/enhance existing media via dedicated endpoint.

        Args:
            media_url: Publicly accessible URL of the image to upscale
            model: Upscale model — "soul-pro" (default) or "nano-banana-pro"

        Returns:
            Job set response with job_set_id for polling
        """
        params = {
            "input_image": {"type": "image_url", "image_url": media_url},
            "model": model,
        }
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            resp = await http_client.post(
                f"{self.base_url}/v1/upscale",
                headers=self.headers,
                json={"params": params},
            )
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Asset validation (client-side checks)
    # ------------------------------------------------------------------

    async def validate_url(self, url: str, expected_content_type: Optional[str] = None) -> Dict[str, Any]:
        """Check that a URL is publicly reachable and optionally matches a content type."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.head(url, follow_redirects=True)
                info: Dict[str, Any] = {
                    "url": url,
                    "accessible": resp.status_code < 400,
                    "status_code": resp.status_code,
                    "content_type": resp.headers.get("content-type", "unknown"),
                    "content_length": resp.headers.get("content-length", "unknown"),
                }
                if expected_content_type and resp.headers.get("content-type", ""):
                    ct = resp.headers["content-type"].lower()
                    info["content_type_matches"] = expected_content_type.lower() in ct
                return info
        except Exception as e:
            return {
                "url": url,
                "accessible": False,
                "error": str(e),
            }
