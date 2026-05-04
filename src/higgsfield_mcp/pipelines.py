"""
Pipeline Logic for Multi-Step Higgsfield Workflows
Chains multiple API calls into single operations.
"""
import asyncio
import time
from typing import Optional, Dict, Any, List


class PipelineRunner:
    """Executes multi-step Higgsfield workflows with polling."""

    def __init__(self, client):
        self.client = client

    async def _poll_job(self, job_set_id: str, interval: int = 10, max_wait: int = 300) -> Dict[str, Any]:
        """Poll a job until completion, timeout, or failure."""
        start = time.time()
        while time.time() - start < max_wait:
            result = await self.client.get_job_results(job_set_id)
            jobs = result.get("jobs", [])
            all_done = all(j.get("status") in ("completed", "failed", "nsfw") for j in jobs)
            if all_done:
                return result
            await asyncio.sleep(interval)
        return {"status": "timeout", "job_set_id": job_set_id, "message": f"Timed out after {max_wait}s"}

    async def generate_and_animate(
        self,
        prompt: str,
        motion_id: str,
        quality: str = "1080p",
        video_quality: str = "standard",
        character_id: Optional[str] = None,
        style_id: Optional[str] = None,
        poll_interval: int = 10,
        max_wait: int = 300,
    ) -> Dict[str, Any]:
        """Generate an image, then animate it into a video."""
        # Step 1: Generate image
        image_result = await self.client.generate_image(
            prompt=prompt,
            quality=quality,
            batch_size=1,
            custom_reference_id=character_id,
            style_id=style_id,
        )
        image_job_id = image_result["id"]

        # Step 2: Wait for image to complete
        image_status = await self._poll_job(image_job_id, interval=poll_interval, max_wait=max_wait)
        if image_status.get("status") == "timeout":
            return {
                "success": False,
                "phase": "image_generation",
                "message": "Image generation timed out",
                "job_set_id": image_job_id,
            }

        # Extract image URL from results
        jobs = image_status.get("jobs", [])
        if not jobs or jobs[0].get("status") != "completed":
            return {
                "success": False,
                "phase": "image_generation",
                "message": "Image generation failed",
                "job_set_id": image_job_id,
                "status": jobs[0].get("status") if jobs else "unknown",
            }

        image_url = jobs[0]["results"]["raw"]["url"]

        # Step 3: Generate video from image
        model_map = {"lite": "dop-lite", "turbo": "dop-turbo", "standard": "dop-preview"}
        video_result = await self.client.generate_video(
            image_url=image_url,
            motion_id=motion_id,
            prompt=prompt,
            model=model_map.get(video_quality, "dop-preview"),
        )

        return {
            "success": True,
            "image": {
                "job_set_id": image_job_id,
                "url": image_url,
            },
            "video": {
                "job_set_id": video_result["id"],
                "message": "Video generation started - poll with get_generation_status",
            },
        }

    async def text_to_talking_head(
        self,
        prompt: str,
        audio_url: str,
        quality: str = "1080p",
        head_quality: str = "high",
        duration: int = 5,
        character_id: Optional[str] = None,
        style_id: Optional[str] = None,
        poll_interval: int = 10,
        max_wait: int = 300,
    ) -> Dict[str, Any]:
        """Generate an image, then create a talking head video."""
        # Step 1: Generate image
        image_result = await self.client.generate_image(
            prompt=prompt,
            quality=quality,
            batch_size=1,
            custom_reference_id=character_id,
            style_id=style_id,
        )
        image_job_id = image_result["id"]

        # Step 2: Wait for image
        image_status = await self._poll_job(image_job_id, interval=poll_interval, max_wait=max_wait)
        if image_status.get("status") == "timeout":
            return {
                "success": False,
                "phase": "image_generation",
                "message": "Image generation timed out",
                "job_set_id": image_job_id,
            }

        jobs = image_status.get("jobs", [])
        if not jobs or jobs[0].get("status") != "completed":
            return {
                "success": False,
                "phase": "image_generation",
                "message": "Image generation failed",
                "job_set_id": image_job_id,
                "status": jobs[0].get("status") if jobs else "unknown",
            }

        image_url = jobs[0]["results"]["raw"]["url"]

        # Step 3: Generate talking head
        th_result = await self.client.generate_talking_head(
            image_url=image_url,
            audio_url=audio_url,
            prompt=prompt,
            quality=head_quality,
            duration=duration,
        )

        return {
            "success": True,
            "image": {
                "job_set_id": image_job_id,
                "url": image_url,
            },
            "talking_head": {
                "job_set_id": th_result["id"],
                "duration": duration,
                "message": "Talking head generation started - poll with get_generation_status",
            },
        }

    async def batch_generate(
        self,
        items: List[Dict[str, Any]],
        job_type: str = "image",
    ) -> List[Dict[str, Any]]:
        """Queue multiple generation jobs at once.

        Each item in `items` should contain the kwargs for the corresponding tool.
        job_type: "image", "video", or "talking_head"
        """
        results = []
        for item in items:
            try:
                if job_type == "image":
                    res = await self.client.generate_image(**item)
                elif job_type == "video":
                    res = await self.client.generate_video(**item)
                elif job_type == "talking_head":
                    res = await self.client.generate_talking_head(**item)
                else:
                    res = {"error": f"Unknown job_type: {job_type}"}
                results.append({"success": True, "job_set_id": res.get("id"), "params": item})
            except Exception as e:
                results.append({"success": False, "error": str(e), "params": item})
        return results
