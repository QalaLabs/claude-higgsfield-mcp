"""
Dynamic MCP Resources for Higgsfield AI
Provides higgsfield:// URI handlers for styles, motions, characters, and history.
"""
import json
from typing import Dict, Any, List, Optional

# ---------------------------------------------------------------------------
# Category tags for styles
# ---------------------------------------------------------------------------
_STYLE_CATEGORY_KEYWORDS = {
    "cinematic": ["cinematic", "film", "movie", "dramatic", "dark", "noir", "moody"],
    "portrait": ["portrait", "face", "headshot", "character", "person"],
    "anime": ["anime", "manga", "cartoon", "illustration", "cel"],
    "landscape": ["landscape", "nature", "scenery", "environment", "outdoor"],
    "abstract": ["abstract", "geometric", "surreal", "artistic", "pattern"],
    "photorealistic": ["photo", "realistic", "natural", "documentary", "candid"],
    "fantasy": ["fantasy", "magic", "medieval", "mythical", "dragon"],
    "scifi": ["scifi", "sci-fi", "futuristic", "cyberpunk", "space", "neon"],
}

# ---------------------------------------------------------------------------
# Category tags for motions
# ---------------------------------------------------------------------------
_MOTION_CATEGORY_KEYWORDS = {
    "camera": ["zoom", "pan", "tilt", "dolly", "crane", "track", "orbit"],
    "slow-motion": ["slow", "slow-mo", "slowmo", "smooth"],
    "dynamic": ["fast", "shake", "whip", "snap", "impact"],
    "character": ["walk", "talk", "wave", "dance", "gesture", "move"],
    "ambient": ["ambient", "loop", "breathing", "idle", "static"],
}


def _categorize(items: List[Dict[str, Any]], keywords: Dict[str, list], name_field: str = "name", desc_field: str = "description") -> Dict[str, List[Dict[str, Any]]]:
    buckets: Dict[str, List[Dict[str, Any]]] = {cat: [] for cat in keywords}
    buckets["all"] = items
    for item in items:
        text = f"{item.get(name_field, '')} {item.get(desc_field, '')}".lower()
        for cat, words in keywords.items():
            if any(w in text for w in words):
                buckets[cat].append(item)
    return buckets


# ---------------------------------------------------------------------------
# Resource formatters
# ---------------------------------------------------------------------------

def format_styles(category: Optional[str] = None) -> str:
    """Return JSON-formatted style list, optionally filtered by category."""
    from .core import HiggsfieldClient  # lazy to avoid circular import
    import asyncio

    async def _fetch():
        client = _resource_client()
        raw = await client.list_styles()
        return _categorize(raw, _STYLE_CATEGORY_KEYWORDS, "name", "description")

    categories = asyncio.run(_fetch())
    target = categories.get(category, categories.get("all", [])) if category else categories.get("all", [])

    if category and category not in categories and target:
        pass
    if category:
        target = categories.get(category, [])
        available = list(categories.keys())
        note = f"Category '{category}'"
        if category != "all" and category not in available:
            note = f"Unknown category '{category}'. Available: {', '.join(available)}"
            target = []
    else:
        target = categories.get("all", [])
        note = "All styles"

    formatted = [
        {
            "style_id": s["id"],
            "name": s["name"],
            "description": s["description"],
            "preview_url": s.get("preview_url"),
        }
        for s in target
    ]

    return json.dumps(
        {
            "note": note,
            "count": len(formatted),
            "available_categories": list(_STYLE_CATEGORY_KEYWORDS.keys()),
            "styles": formatted,
            "usage": "Use style_id parameter in generate_image tool",
        },
        indent=2,
    )


def format_motions(category: Optional[str] = None) -> str:
    """Return JSON-formatted motion list, optionally filtered by category."""
    from .core import HiggsfieldClient
    import asyncio

    async def _fetch():
        client = _resource_client()
        raw = await client.list_motions()
        return _categorize(raw, _MOTION_CATEGORY_KEYWORDS, "name", "description")

    categories = asyncio.run(_fetch())

    if category:
        available = list(_MOTION_CATEGORY_KEYWORDS.keys())
        if category not in available and category != "all":
            return json.dumps(
                {
                    "error": f"Unknown category '{category}'",
                    "available_categories": available,
                },
                indent=2,
            )
        target = categories.get(category, [])
        note = f"Category '{category}'"
    else:
        target = categories.get("all", [])
        note = "All motions"

    formatted = [
        {
            "motion_id": m["id"],
            "name": m["name"],
            "description": m["description"],
            "preview_url": m.get("preview_url"),
            "start_end_frame": m.get("start_end_frame", False),
        }
        for m in target
    ]

    return json.dumps(
        {
            "note": note,
            "count": len(formatted),
            "available_categories": list(_MOTION_CATEGORY_KEYWORDS.keys()),
            "motions": formatted,
            "usage": "Use motion_id parameter in generate_video tool",
        },
        indent=2,
    )


def format_characters() -> str:
    """Return JSON-formatted character references."""
    from .core import HiggsfieldClient
    import asyncio

    async def _fetch():
        client = _resource_client()
        return await client.list_characters(page=1, page_size=100)

    result = asyncio.run(_fetch())

    characters = [
        {
            "character_id": item["id"],
            "name": item["name"],
            "status": item["status"],
            "thumbnail_url": item.get("thumbnail_url"),
            "created_at": item["created_at"],
        }
        for item in result.get("items", [])
    ]

    return json.dumps(
        {
            "total_characters": result.get("total", 0),
            "characters": characters,
            "usage": "Use character_id parameter in generate_image tool",
        },
        indent=2,
    )


def format_history(page: int = 1, page_size: int = 20) -> str:
    """Return JSON-formatted recent generation jobs."""
    from .core import HiggsfieldClient
    import asyncio

    async def _fetch():
        client = _resource_client()
        return await client.list_jobs(page=page, page_size=page_size)

    result = asyncio.run(_fetch())

    jobs = []
    for item in result.get("items", result.get("jobs", [])):
        job_info = {
            "job_set_id": item["id"],
            "type": item.get("type", "unknown"),
            "status": item.get("status", "unknown"),
            "created_at": item.get("created_at"),
        }
        if item.get("jobs"):
            first_job = item["jobs"][0]
            job_info["latest_status"] = first_job.get("status", "unknown")
            if first_job.get("results"):
                job_info["preview_url"] = first_job["results"].get("min", {}).get("url")
        jobs.append(job_info)

    return json.dumps(
        {
            "total": result.get("total", len(jobs)),
            "page": page,
            "page_size": page_size,
            "jobs": jobs,
            "usage": "Use job_set_id with get_generation_status to retrieve full results",
        },
        indent=2,
    )


def _resource_client() -> "HiggsfieldClient":
    """Create a client from current environment credentials."""
    import os
    from dotenv import load_dotenv
    from .core import HiggsfieldClient

    load_dotenv()
    api_key = os.getenv("HF_API_KEY", "dummy")
    secret = os.getenv("HF_SECRET", "dummy")
    return HiggsfieldClient(api_key=api_key, secret=secret)


# ---------------------------------------------------------------------------
# Prompting guide resource (static — no API call needed)
# ---------------------------------------------------------------------------

_PROMPTING_GUIDE = """# Higgsfield AI Prompt Engineering Guide

## Structure
Use this format for best results with the Soul model:

```
Setting: <location, environment, time of day>
Subject: <who/what is in the scene, appearance details>
Outfit: <clothing, accessories, colors>
Lighting: <direction, quality, color temperature>
Camera: <lens type, angle, depth of field>
Mood: <atmosphere, emotion, tone>
Style: <artistic reference, e.g., "cinematic still", "editorial photography">
```

## Tips
- Be specific about lighting: "golden hour backlighting" > "good lighting"
- Specify camera details: "85mm lens, shallow depth of field" > "close-up"
- Use art references: "Wes Anderson composition", "Blade Runner aesthetic"
- Avoid contradictions: don't mix "bright sunny day" with "dark moody shadows"
- For character consistency, always use the same character_id and keep subject descriptions aligned

## Quality Keywords That Work Well
- "cinematic still", "film grain", "shot on 35mm"
- "editorial photography", "Vogue-style portrait"
- "volumetric lighting", "god rays", "rim lighting"
- "shallow depth of field", "bokeh", "telephoto"
- "National Geographic", "artstation trending", "Unreal Engine 5 render"

## Examples

### Portrait
```
Setting: Minimalist concrete studio with large north-facing windows
Subject: Woman in her 30s with sharp cheekbones, dark curly hair pulled back
Outfit: Oversized ivory linen blazer, gold chain necklace
Lighting: Soft diffused window light, subtle fill from white reflector
Camera: 85mm portrait lens, f/2.8, eye-level
Mood: Confident, contemplative
Style: High-end editorial photography
```

### Landscape
```
Setting: Icelandic highland plateau at dawn, snow-capped mountains in distance
Subject: Lone figure walking along a black sand ridge
Outfit: Red technical parka, dark hiking pants
Lighting: Low-angle sunrise, long shadows, cool blue ambient fill
Camera: 24mm wide angle, f/8, foreground sharp
Mood: Epic, solitary, awe-inspiring
Style: Cinematic landscape photography, Ansel Adams meets modern drone shot
```

### Sci-Fi
```
Setting: Neon-lit Tokyo alleyway at night, rain-slicked streets, holographic billboards
Subject: Cyberpunk hacker with augmented reality visor
Outfit: Black techwear jacket with LED trim, cargo pants
Lighting: Neon pink and cyan reflections, rain droplets catching light
Camera: 50mm, f/1.4, shallow depth focusing on subject
Mood: Gritty, atmospheric, tense
Style: Blade Runner 2049 concept art meets street photography
```

## Negative Prompts
The Soul model responds well to avoiding these:
- Don't use vague terms: "nice", "beautiful", "cool"
- Don't overstuff: 1-2 style references max
- Don't conflict: "daytime" + "moonlight" will confuse the model
"""


def format_prompting_guide() -> str:
    """Return the Higgsfield prompt engineering guide for Claude to reference."""
    return _PROMPTING_GUIDE
