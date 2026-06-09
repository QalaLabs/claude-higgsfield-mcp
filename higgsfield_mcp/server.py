"""
Higgsfield AI MCP Server
FastMCP server exposing Higgsfield AI capabilities to LLMs (Claude, etc.)
"""
import os
import json
import sys
import argparse
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from fastmcp import FastMCP

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from higgsfield_mcp.core import HiggsfieldClient
    from higgsfield_mcp.pipelines import PipelineRunner
    from higgsfield_mcp.resources import (
        format_styles,
        format_motions,
        format_characters,
        format_history,
        format_prompting_guide,
    )
    from higgsfield_mcp.auth import ClerkSession
    from higgsfield_mcp.consumer import HiggsfieldConsumerClient
except ImportError:
    from .core import HiggsfieldClient
    from .pipelines import PipelineRunner
    from .resources import (
        format_styles,
        format_motions,
        format_characters,
        format_history,
        format_prompting_guide,
    )
    from .auth import ClerkSession
    from .consumer import HiggsfieldConsumerClient

# ---------------------------------------------------------------------------
# Credential resolution — supports API key mode AND Clerk (email/password) mode
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="Higgsfield AI MCP Server")
parser.add_argument("--api-key", type=str, help="Higgsfield API key (API key mode)")
parser.add_argument("--secret", type=str, help="Higgsfield secret key (API key mode)")
parser.add_argument("--email", type=str, help="Higgsfield account email (Clerk mode)")
parser.add_argument("--password", type=str, help="Higgsfield account password (Clerk mode)")
args, unknown = parser.parse_known_args()

load_dotenv()

api_key = args.api_key or os.getenv("HF_API_KEY", "")
secret = args.secret or os.getenv("HF_SECRET", "")
email = args.email or os.getenv("HF_EMAIL", "")
password = args.password or os.getenv("HF_PASSWORD", "")

# Clerk mode (email/password) takes priority when both are present
if email and password:
    clerk_session = ClerkSession()
    if clerk_session.login(email, password):
        client = None
        consumer = HiggsfieldConsumerClient(clerk_session)
        pipelines = None
        auth_mode = "clerk"
    else:
        print("Warning: Clerk login failed. Falling back to API key mode.")
        clerk_session = None
        consumer = None
        auth_mode = "fallback"
        api_key = api_key or "dummy-api-key-for-inspection"
        secret = secret or "dummy-secret-for-inspection"
        client = HiggsfieldClient(api_key=api_key, secret=secret)
        pipelines = PipelineRunner(client)
else:
    clerk_session = None
    consumer = None
    auth_mode = "api_key"
    if not api_key or not secret:
        api_key = api_key or "dummy-api-key-for-inspection"
        secret = secret or "dummy-secret-for-inspection"
        import warnings
        warnings.warn(
            "Missing HF_API_KEY/HF_SECRET or HF_EMAIL/HF_PASSWORD. "
            "Provide one set via CLI args or .env file.",
            RuntimeWarning,
        )
    client = HiggsfieldClient(api_key=api_key, secret=secret)
    pipelines = PipelineRunner(client)

# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    name="Higgsfield AI",
    instructions="""
    This server provides access to Higgsfield AI's cinematic-grade image and video generation.

    Two auth modes supported:
    - API key mode: Uses platform.higgsfield.ai (official API, key+secret auth)
    - Clerk mode: Uses fnf.higgsfield.ai (consumer backend, email/password auth, more models)

    API key mode capabilities:
    - Generate images from text prompts (Soul model) with style presets and character consistency
    - Convert images to cinematic videos with motion presets (DoP model)
    - Create talking head videos from image + audio (Speak v2 model)
    - Upscale/enhance existing images via dedicated endpoint
    - Full character reference CRUD (create, read, update, delete)
    - Batch generation for queuing multiple jobs
    - Pipeline workflows: generate_and_animate, text_to_talking_head
    - Browse styles, motions, characters, and generation history via resources
    - Monitor usage stats and validate asset URLs

    Clerk mode capabilities:
    - Generate images with multiple consumer models (z-image, soul, flux-2, gpt, nano-banana-2, seedream)
    - Generate videos with multiple models (kling3_0, veo3, sora2-video, etc.)
    - Job polling and history

    All generation is asynchronous — poll with get_generation_status to retrieve results.
    Results are retained for 7 days.

    For prompt engineering tips, read the higgsfield://docs/prompting resource.
    """,
    version="1.0.0",
)

# ===================================================================
# Helpers
# ===================================================================

def _require_api_mode() -> bool:
    """Check if API key mode is active; return False if not."""
    global client
    return client is not None

def _require_clerk_mode() -> bool:
    """Check if Clerk mode is active; return False if not."""
    global consumer
    return consumer is not None

# ===================================================================
# TOOLS — Core Generation (API key mode only)
# ===================================================================

@mcp.tool
async def generate_image(
    prompt: str,
    quality: str = "1080p",
    character_id: Optional[str] = None,
    style_id: Optional[str] = None,
    batch_size: int = 1,
    dimensions: str = "2048x1152",
) -> str:
    """Generate high-quality images from text prompts using the Soul model.

    Args:
        prompt: Detailed text description of the image
        quality: "720p" or "1080p" (default: "1080p")
        character_id: Optional character reference ID for consistent generation
        style_id: Optional style preset ID (browse with higgsfield://styles)
        batch_size: Number of images to generate (1 or 4)
        dimensions: Image dimensions, default "2048x1152"

    Returns:
        Job info with job_set_id for polling
    """
    if not client:
        return json.dumps({"success": False, "error": "Not available in Clerk mode. Use consumer_generate_image instead."}, indent=2)
    try:
        result = await client.generate_image(
            prompt=prompt,
            quality=quality,
            batch_size=batch_size,
            custom_reference_id=character_id,
            style_id=style_id,
            width_and_height=dimensions,
        )
        return json.dumps({
            "success": True,
            "job_set_id": result["id"],
            "job_type": result["type"],
            "status": "Job started — poll with get_generation_status",
            "created_at": result.get("created_at"),
            "jobs": result.get("jobs", []),
        }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


@mcp.tool
async def generate_video(
    image_url: str,
    motion_id: str,
    prompt: Optional[str] = None,
    quality: str = "standard",
) -> str:
    """Convert an image to a 5-second cinematic video using the DoP model.

    Args:
        image_url: Publicly accessible HTTPS URL of source image
        motion_id: Motion preset ID (browse with higgsfield://motions)
        prompt: Optional description of the scene (auto-generated if omitted)
        quality: "lite" (cheapest), "turbo" (2x speed), or "standard" (default)

    Returns:
        Job info with job_set_id for polling
    """
    if not client:
        return json.dumps({"success": False, "error": "Not available in Clerk mode. Use consumer_generate_video instead."}, indent=2)
    try:
        model_map = {"lite": "dop-lite", "turbo": "dop-turbo", "standard": "dop-preview"}
        result = await client.generate_video(
            image_url=image_url,
            motion_id=motion_id,
            prompt=prompt or "",
            model=model_map.get(quality, "dop-preview"),
        )
        return json.dumps({
            "success": True,
            "job_set_id": result["id"],
            "job_type": result["type"],
            "status": "Job started — poll with get_generation_status",
            "created_at": result.get("created_at"),
            "model": model_map.get(quality, "dop-preview"),
        }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


@mcp.tool
async def generate_talking_head(
    image_url: str,
    audio_url: str,
    prompt: str,
    quality: str = "high",
    duration: int = 5,
    seed: int = 42,
) -> str:
    """Generate a talking head video from an image + audio using Speak v2.

    Args:
        image_url: Portrait image URL (must be publicly accessible)
        audio_url: Audio file URL in WAV format (must be publicly accessible)
        prompt: Description of the image/scene
        quality: "high" or "mid" (default: "high")
        duration: Video length — 5, 10, or 15 seconds (default: 5)
        seed: Random seed for reproducibility (1–1000000)

    Returns:
        Job info with job_set_id for polling
    """
    if not client:
        return json.dumps({"success": False, "error": "Not available in Clerk mode."}, indent=2)
    try:
        result = await client.generate_talking_head(
            image_url=image_url,
            audio_url=audio_url,
            prompt=prompt,
            quality=quality,
            duration=duration,
            seed=seed,
        )
        return json.dumps({
            "success": True,
            "job_set_id": result["id"],
            "job_type": result["type"],
            "status": "Job started — poll with get_generation_status",
            "duration": duration,
            "quality": quality,
        }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


# ===================================================================
# TOOLS — Upscale / Enhance
# ===================================================================

@mcp.tool
async def upscale_media(
    media_url: str,
    model: str = "soul-pro",
) -> str:
    """Upscale or enhance an existing image via the dedicated Higgsfield endpoint.

    If no media_url is available, use generate_image with higher quality instead.

    Args:
        media_url: Publicly accessible URL of the image to upscale
        model: Upscale model — "soul-pro" (default, highest quality) or "nano-banana-pro"

    Returns:
        Job info with job_set_id for polling
    """
    if not client:
        return json.dumps({"success": False, "error": "Not available in Clerk mode."}, indent=2)
    try:
        result = await client.upscale_media(media_url=media_url, model=model)
        return json.dumps({
            "success": True,
            "job_set_id": result["id"],
            "job_type": "upscale",
            "status": "Upscale job started — poll with get_generation_status",
            "model": model,
        }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


# ===================================================================
# TOOLS — Batch & Pipelines
# ===================================================================

@mcp.tool
async def batch_generate(items: list, job_type: str = "image") -> str:
    """Queue multiple generation jobs at once.

    Args:
        items: List of dicts, each containing kwargs for the generation call.
            For "image": {prompt, quality, character_id, style_id, ...}
            For "video": {image_url, motion_id, prompt, quality, ...}
            For "talking_head": {image_url, audio_url, prompt, quality, ...}
        job_type: "image", "video", or "talking_head"

    Returns:
        List of job_set_ids or errors for each item
    """
    if not pipelines:
        return json.dumps({"success": False, "error": "Not available in Clerk mode."}, indent=2)
    try:
        results = await pipelines.batch_generate(items, job_type=job_type)
        return json.dumps({"success": True, "results": results}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


@mcp.tool
async def generate_and_animate(
    prompt: str,
    motion_id: str,
    quality: str = "1080p",
    video_quality: str = "standard",
    character_id: Optional[str] = None,
    style_id: Optional[str] = None,
) -> str:
    """Pipeline: Generate an image from text, then animate it into a video.

    Args:
        prompt: Text description for the image
        motion_id: Motion preset to apply
        quality: Image quality ("720p" or "1080p")
        video_quality: Video quality ("lite", "turbo", or "standard")
        character_id: Optional character reference for the image
        style_id: Optional style preset for the image

    Returns:
        Image URL and video job_set_id
    """
    if not pipelines:
        return json.dumps({"success": False, "error": "Not available in Clerk mode."}, indent=2)
    try:
        result = await pipelines.generate_and_animate(
            prompt=prompt,
            motion_id=motion_id,
            quality=quality,
            video_quality=video_quality,
            character_id=character_id,
            style_id=style_id,
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


@mcp.tool
async def text_to_talking_head(
    prompt: str,
    audio_url: str,
    quality: str = "1080p",
    head_quality: str = "high",
    duration: int = 5,
    character_id: Optional[str] = None,
    style_id: Optional[str] = None,
) -> str:
    """Pipeline: Generate an image from text, then create a talking head video.

    Args:
        prompt: Text description for the image
        audio_url: WAV audio URL (must be publicly accessible)
        quality: Image quality ("720p" or "1080p")
        head_quality: Talking head quality ("high" or "mid")
        duration: Video length — 5, 10, or 15 seconds
        character_id: Optional character reference
        style_id: Optional style preset

    Returns:
        Image URL and talking head job_set_id
    """
    if not pipelines:
        return json.dumps({"success": False, "error": "Not available in Clerk mode."}, indent=2)
    try:
        result = await pipelines.text_to_talking_head(
            prompt=prompt,
            audio_url=audio_url,
            quality=quality,
            head_quality=head_quality,
            duration=duration,
            character_id=character_id,
            style_id=style_id,
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


# ===================================================================
# TOOLS — Character CRUD
# ===================================================================

@mcp.tool
async def create_character(name: str, image_urls: list) -> str:
    """Create a reusable character reference for consistent generation.

    Provide 1–5 clear face images. Costs 40 credits ($2.50).

    Args:
        name: Descriptive name for this character
        image_urls: List of 1–5 publicly accessible image URLs

    Returns:
        Character reference with ID
    """
    if not client:
        return json.dumps({"success": False, "error": "Not available in Clerk mode."}, indent=2)
    try:
        result = await client.create_character(name=name, image_urls=image_urls)
        return json.dumps({
            "success": True,
            "character_id": result["id"],
            "name": result["name"],
            "status": result["status"],
            "message": "Character creation started — poll with get_generation_status",
        }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


@mcp.tool
async def list_characters() -> str:
    """List all character references you have created."""
    if not client:
        return json.dumps({"success": False, "error": "Not available in Clerk mode."}, indent=2)
    try:
        result = await client.list_characters(page=1, page_size=50)
        chars = [
            {
                "character_id": c["id"],
                "name": c["name"],
                "status": c["status"],
                "thumbnail_url": c.get("thumbnail_url"),
                "created_at": c["created_at"],
            }
            for c in result.get("items", [])
        ]
        return json.dumps({
            "success": True,
            "total": result.get("total", 0),
            "characters": chars,
        }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


@mcp.tool
async def update_character(character_id: str, name: Optional[str] = None, image_urls: Optional[list] = None) -> str:
    """Update a character reference's name or source images.

    Args:
        character_id: ID of the character to update
        name: New name (optional)
        image_urls: New list of 1–5 image URLs (optional)

    Returns:
        Updated character info
    """
    if not client:
        return json.dumps({"success": False, "error": "Not available in Clerk mode."}, indent=2)
    try:
        result = await client.update_character(character_id, name=name, image_urls=image_urls)
        return json.dumps({"success": True, "character": result}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


@mcp.tool
async def delete_character(character_id: str) -> str:
    """Delete a character reference permanently.

    Args:
        character_id: ID of the character to delete

    Returns:
        Confirmation of deletion
    """
    if not client:
        return json.dumps({"success": False, "error": "Not available in Clerk mode."}, indent=2)
    try:
        result = await client.delete_character(character_id)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


# ===================================================================
# TOOLS — Creative Utilities
# ===================================================================

@mcp.tool
async def get_prompt_guide() -> str:
    """Return the Higgsfield prompt engineering guide.

    Read this resource to learn how to structure prompts for the Soul model.
    It covers: Setting/Subject/Outfit/Lighting/Camera/Mood/Style format,
    quality keywords, and examples for portrait, landscape, and sci-fi.

    Returns:
        Full prompt engineering guide with tips and examples
    """
    return format_prompting_guide()


@mcp.tool
async def extract_style_from_image(image_url: str) -> str:
    """Analyze an image URL and find matching Higgsfield styles.

    This returns the full list of available styles with descriptions.
    Use your vision capabilities to compare the image against the style
    descriptions and pick the best matching style_id.

    Args:
        image_url: URL of the reference image to analyze

    Returns:
        Available styles with IDs and descriptions for matching
    """
    try:
        styles = await client.list_styles()
    except Exception as e:
        return json.dumps({"error": str(e), "message": "Could not fetch styles"}, indent=2)

    formatted = [
        {
            "style_id": s["id"],
            "name": s["name"],
            "description": s["description"],
            "preview_url": s.get("preview_url"),
        }
        for s in styles
    ]

    return json.dumps({
        "image_url": image_url,
        "instruction": "Use your vision capabilities to examine this image and compare against the style descriptions below. Return the style_id that best matches the visual style.",
        "styles": formatted,
    }, indent=2)


@mcp.tool
async def search_motions(query: str) -> str:
    """Search motion presets by keyword.

    Args:
        query: Keywords like "zoom", "slow-motion", "dance", "pan"

    Returns:
        Matching motion presets
    """
    try:
        motions = await client.list_motions()
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)

    query_lower = query.lower()
    matches = []
    for m in motions:
        text = f"{m.get('name', '')} {m.get('description', '')}".lower()
        if any(term in text for term in query_lower.split()):
            matches.append({
                "motion_id": m["id"],
                "name": m["name"],
                "description": m["description"],
                "preview_url": m.get("preview_url"),
                "start_end_frame": m.get("start_end_frame", False),
            })

    return json.dumps({
        "query": query,
        "total_matches": len(matches),
        "motions": matches,
        "usage": "Use motion_id parameter in generate_video tool",
    }, indent=2)


# ===================================================================
# TOOLS — Monitoring & Validation
# ===================================================================

@mcp.tool
async def get_generation_status(job_set_id: str) -> str:
    """Check the status of an async generation job.

    Statuses: queued, in_progress, completed, failed, nsfw.
    Results are retained for 7 days.

    Args:
        job_set_id: ID returned from any generation tool

    Returns:
        Current status and results (if completed)
    """
    if not client:
        if consumer:
            return await consumer_get_status(job_set_id)
        return json.dumps({"success": False, "error": "No API client available."}, indent=2)
    try:
        result = await client.get_job_results(job_set_id)
        response = {
            "success": True,
            "job_set_id": result["id"],
            "type": result["type"],
            "created_at": result["created_at"],
            "jobs": [],
        }
        for job in result.get("jobs", []):
            job_info = {"job_id": job["id"], "status": job["status"]}
            if job.get("results"):
                job_info["results"] = {
                    "preview_url": job["results"]["min"]["url"],
                    "full_quality_url": job["results"]["raw"]["url"],
                    "type": job["results"]["raw"]["type"],
                }
            response["jobs"].append(job_info)

        statuses = [j["status"] for j in result.get("jobs", [])]
        if all(s == "completed" for s in statuses):
            response["message"] = "Generation complete — download URLs above."
        elif any(s == "failed" for s in statuses):
            response["message"] = "One or more jobs failed."
        elif any(s == "nsfw" for s in statuses):
            response["message"] = "Content filter triggered — try a different prompt."
        else:
            response["message"] = "Still processing — check again in a few seconds."

        return json.dumps(response, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


@mcp.tool
async def get_usage_stats() -> str:
    """Check your Higgsfield credit balance and usage stats."""
    if not client:
        if consumer:
            return await consumer_get_usage_stats()
        return json.dumps({"success": False, "error": "No API client available."}, indent=2)
    try:
        result = await client.get_usage_stats()
        balance = result.get("credits", result.get("balance", "unknown"))
        response = {"success": True, "credits_remaining": balance, "raw": result}
        if isinstance(balance, (int, float)) and balance < 50:
            response["warning"] = "Low credit balance — top up at https://cloud.higgsfield.ai/credits"
        return json.dumps(response, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "note": "Usage stats endpoint may not be available. Check https://cloud.higgsfield.ai/credits",
        }, indent=2)


@mcp.tool
async def validate_assets(urls: list, expected_type: Optional[str] = None) -> str:
    """Validate that asset URLs are publicly accessible before sending to the API.

    Checks that each URL returns a successful HTTP response and optionally
    matches the expected content type (e.g., 'image/png', 'audio/wav').

    Args:
        urls: List of HTTPS URLs to validate
        expected_type: Optional MIME type to check against (e.g., "image/", "audio/wav")

    Returns:
        Validation report per URL
    """
    if not client:
        return json.dumps({"success": False, "error": "Not available in Clerk mode."}, indent=2)
    results = []
    for url in urls:
        info = await client.validate_url(url, expected_content_type=expected_type)
        results.append(info)
    return json.dumps({"assets": results}, indent=2)


# ===================================================================
# TOOLS — Debug
# ===================================================================

@mcp.tool
async def debug_credentials() -> str:
    """Debug tool to verify API credentials are configured correctly."""
    info = {"auth_mode": auth_mode}
    if auth_mode == "api_key":
        auth = client.headers.get("Authorization", "NOT SET")
        info.update({
            "auth_configured": auth != "NOT SET",
            "auth_preview": auth[:20] + "..." if auth != "NOT SET" else "NOT SET",
            "base_url": client.base_url,
            "headers_keys": list(client.headers.keys()),
        })
    elif auth_mode == "clerk":
        info.update({
            "authenticated": bool(clerk_session.jwt),
            "email": clerk_session.email,
            "has_session_id": bool(clerk_session.session_id),
            "jwt_preview": clerk_session.jwt[:20] + "..." if clerk_session.jwt else "NOT SET",
            "api_base": "https://fnf.higgsfield.ai",
        })
    else:
        info.update({"error": "No valid credentials configured"})
    return json.dumps(info, indent=2)


# ===================================================================
# TOOLS — Clerk Mode (email/password auth via fnf.higgsfield.ai)
# ===================================================================

@mcp.tool
async def consumer_generate_image(
    prompt: str,
    model: str = "z-image",
    width: int = 1024,
    height: int = 1024,
    aspect_ratio: str = "1:1",
    seed: Optional[int] = None,
    enhance_prompt: bool = True,
) -> str:
    """Generate an image using the consumer API (Clerk mode). Supports multiple models.

    Args:
        prompt: Text description of the image
        model: Model to use — "z-image" (fast, default), "soul", "flux-2", "gpt", "nano-banana-2", "seedream", "seedream-v4-5"
        width: Image width in pixels (default: 1024)
        height: Image height in pixels (default: 1024)
        aspect_ratio: Aspect ratio like "1:1", "16:9", "9:16", "4:3" (default: "1:1")
        seed: Optional random seed for reproducibility
        enhance_prompt: Auto-enhance the prompt (default: True)

    Returns:
        Job info with job_set_id for polling
    """
    if not consumer:
        return json.dumps({"success": False, "error": "Clerk mode not active. Set HF_EMAIL and HF_PASSWORD."}, indent=2)
    try:
        result = consumer.generate_image(
            prompt=prompt,
            model=model,
            width=width,
            height=height,
            aspect_ratio=aspect_ratio,
            seed=seed,
            enhance_prompt=enhance_prompt,
        )
        job_set_id = result.get("id", result.get("job_sets", [{}])[0].get("id") if result.get("job_sets") else None)
        return json.dumps({
            "success": True,
            "job_set_id": job_set_id,
            "model": model,
            "status": "Job started — poll with get_generation_status",
            "raw": result,
        }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


@mcp.tool
async def consumer_generate_video(
    prompt: str,
    model: str = "kling3_0",
    aspect_ratio: str = "16:9",
    duration: int = 5,
    sound: str = "on",
    enhance_prompt: bool = True,
) -> str:
    """Generate a video using the consumer API (Clerk mode). Supports multiple video models.

    Args:
        prompt: Text description of the video
        model: Video model — "kling3_0" (default), "kling", "veo3", "wan2-5-video", "minimax-hailuo", "sora2-video", "seedance", "image2video"
        aspect_ratio: Aspect ratio like "16:9", "9:16", "1:1" (default: "16:9")
        duration: Video duration in seconds (default: 5)
        sound: "on" or "off" (default: "on")
        enhance_prompt: Auto-enhance the prompt (default: True)

    Returns:
        Job info with job_set_id for polling
    """
    if not consumer:
        return json.dumps({"success": False, "error": "Clerk mode not active. Set HF_EMAIL and HF_PASSWORD."}, indent=2)
    try:
        result = consumer.generate_video(
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            duration=duration,
            sound=sound,
            enhance_prompt=enhance_prompt,
        )
        job_set_id = result.get("id", result.get("job_sets", [{}])[0].get("id") if result.get("job_sets") else None)
        return json.dumps({
            "success": True,
            "job_set_id": job_set_id,
            "model": model,
            "status": "Job started — poll with get_generation_status",
        }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def consumer_get_status(job_set_id: str) -> str:
    """Poll job status on the consumer API."""
    if not consumer:
        return json.dumps({"success": False, "error": "Clerk mode not active."}, indent=2)
    try:
        result = consumer.get_job_results(job_set_id)
        response = {
            "success": True,
            "job_set_id": job_set_id,
            "status": result.get("status", "unknown"),
            "jobs": result.get("jobs", []),
        }
        return json.dumps(response, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def consumer_get_usage_stats() -> str:
    """Get account info and credit balance from consumer API."""
    if not consumer:
        return json.dumps({"success": False, "error": "Clerk mode not active."}, indent=2)
    try:
        info = consumer.get_account_info()
        return json.dumps({
            "success": True,
            "credits": info.get("credits", "unknown"),
            "email": clerk_session.email,
            "raw": info,
        }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


@mcp.tool
async def consumer_list_models() -> str:
    """List all available image and video models for Clerk mode."""
    from .consumer import IMAGE_MODELS, VIDEO_MODELS
    return json.dumps({
        "image_models": {k: v for k, v in IMAGE_MODELS.items()},
        "video_models": {k: v for k, v in VIDEO_MODELS.items()},
    }, indent=2)


@mcp.tool
async def clerk_login(email: str, password: str) -> str:
    """Login to Higgsfield with email/password (for Clerk mode).

    If 2FA verification is required, call clerk_verify with the code from your email.

    Args:
        email: Higgsfield account email
        password: Higgsfield account password

    Returns:
        Login result or verification required message
    """
    global clerk_session, consumer, auth_mode
    try:
        s = ClerkSession()
        if s.login(email, password):
            clerk_session = s
            consumer = HiggsfieldConsumerClient(s)
            auth_mode = "clerk"
            return json.dumps({"success": True, "email": email, "message": "Logged in successfully"}, indent=2)

        # Check if verification is needed
        if s.session_id:
            clerk_session = s
            return json.dumps({
                "success": True,
                "verification_required": True,
                "message": "Verification code sent to your email. Call clerk_verify with the 6-digit code.",
            }, indent=2)
        return json.dumps({"success": False, "error": "Login failed"}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


@mcp.tool
async def clerk_verify(code: str) -> str:
    """Complete email verification for Clerk login.

    Args:
        code: 6-digit verification code from email

    Returns:
        Login result
    """
    global clerk_session, consumer, auth_mode
    if not clerk_session:
        return json.dumps({"success": False, "error": "No pending login. Call clerk_login first."}, indent=2)
    try:
        if clerk_session.complete_verification(code):
            consumer = HiggsfieldConsumerClient(clerk_session)
            auth_mode = "clerk"
            return json.dumps({"success": True, "email": clerk_session.email, "message": "Verification complete, logged in"}, indent=2)
        return json.dumps({"success": False, "error": "Verification failed. Check the code and try again."}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


# ===================================================================
# RESOURCES
# ===================================================================

@mcp.resource("higgsfield://styles")
async def resource_styles() -> str:
    """Browse all available Soul image style presets."""
    return format_styles()


@mcp.resource("higgsfield://styles/{category}")
async def resource_styles_category(category: str) -> str:
    """Browse styles filtered by category."""
    return format_styles(category=category)


@mcp.resource("higgsfield://motions")
async def resource_motions() -> str:
    """Browse all available video motion presets."""
    return format_motions()


@mcp.resource("higgsfield://motions/{category}")
async def resource_motions_category(category: str) -> str:
    """Browse motions filtered by category."""
    return format_motions(category=category)


@mcp.resource("higgsfield://characters")
async def resource_characters() -> str:
    """Browse your created character references."""
    return format_characters()


@mcp.resource("higgsfield://history")
async def resource_history() -> str:
    """Browse your recent generation history (last 20 jobs)."""
    return format_history()


@mcp.resource("higgsfield://docs/prompting")
async def resource_prompting() -> str:
    """Higgsfield AI prompt engineering guide — read this before writing prompts."""
    return format_prompting_guide()


# ===================================================================
# Entry point
# ===================================================================

def main():
    import os as _os

    transport = _os.getenv("MCP_TRANSPORT", "stdio")

    if transport == "http":
        host = _os.getenv("MCP_HOST", "0.0.0.0")
        port = int(_os.getenv("MCP_PORT", "8000"))
        path = _os.getenv("MCP_PATH", "/mcp")
        print(f"Starting MCP server on {host}:{port}{path}")
        mcp.run(transport="streamable-http", host=host, port=port, path=path)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
