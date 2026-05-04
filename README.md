# Claude × Higgsfield MCP

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that bridges **Claude** with [Higgsfield AI](https://higgsfield.ai)'s cinematic-grade image and video generation capabilities.

Built with [FastMCP](https://github.com/jlowin/fastmcp).

## Features

| Category | Tools |
|----------|-------|
| **Image Generation** | `generate_image`, `upscale_media` |
| **Video Generation** | `generate_video`, `generate_talking_head` |
| **Pipelines** | `generate_and_animate`, `text_to_talking_head`, `batch_generate` |
| **Character CRUD** | `create_character`, `list_characters`, `update_character`, `delete_character` |
| **Creative Utilities** | `get_prompt_guide`, `extract_style_from_image`, `search_motions` |
| **Monitoring** | `get_generation_status`, `get_usage_stats`, `validate_assets` |
| **Debug** | `debug_credentials` |

**Resources** (browsable via `higgsfield://` URIs):
- `higgsfield://styles` — All Soul image style presets (with category filtering)
- `higgsfield://styles/{category}` — Styles by category: cinematic, portrait, anime, landscape, abstract, photorealistic, fantasy, scifi
- `higgsfield://motions` — All video motion presets (with category filtering)
- `higgsfield://motions/{category}` — Motions by category: camera, slow-motion, dynamic, character, ambient
- `higgsfield://characters` — Your created character references
- `higgsfield://history` — Recent generation history
- `higgsfield://docs/prompting` — Prompt engineering guide with Higgsfield-specific tips

## Installation

### Prerequisites

- Python 3.10+
- Higgsfield AI account ([Sign up](https://cloud.higgsfield.ai))

### Setup

```bash
# Clone the repository
git clone https://github.com/QalaLabs/claude-higgsfield-mcp.git
cd claude-higgsfield-mcp

# Install dependencies
pip install -r requirements.txt

# Configure credentials
cp .env.example .env
# Edit .env with your HF_API_KEY and HF_SECRET
```

Get your API keys from: [https://cloud.higgsfield.ai/api-keys](https://cloud.higgsfield.ai/api-keys)

## Claude Desktop Integration

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "higgsfield": {
      "command": "python",
      "args": ["-m", "higgsfield_mcp.server"],
      "cwd": "/absolute/path/to/claude-higgsfield-mcp",
      "env": {
        "HF_API_KEY": "${HF_API_KEY}",
        "HF_SECRET": "${HF_SECRET}"
      }
    }
  }
}
```

Restart Claude Desktop after configuring.

## Usage Examples

### Generate an Image

```
Generate an image: "A woman with sharp eyes sitting on a minimalist bench in a desert garden, wearing a sand-colored suit, late afternoon sunlight"
```

### Browse Styles, Then Generate

```
Show me the available styles → higgsfield://styles
Now generate with the "cinematic" style
```

### Create a Character, Then Use It

```
Create a character named "Jane" from these images: [url1], [url2]
Now generate an image of Jane in a coffee shop
```

### Full Pipeline: Text → Image → Video

```
Generate an image of a cyberpunk city at night, then animate it with a zoom motion
```

(Claude will use `generate_and_animate` automatically)

### Get Prompt Suggestions

```
I want to create a portrait of a musician. Suggest some prompts.
```

(Claude reads `higgsfield://docs/prompting` and generates optimized prompts)

## Tool Reference

### generate_image
Generate high-quality images from text prompts using the Soul model.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| prompt | string | required | Detailed text description |
| quality | string | "1080p" | "720p" or "1080p" |
| character_id | string | null | Character reference ID |
| style_id | string | null | Style preset ID |
| batch_size | int | 1 | Number of images (1 or 4) |
| dimensions | string | "2048x1152" | Image dimensions |

### generate_video
Convert an image to a 5-second cinematic video using the DoP model.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| image_url | string | required | Publicly accessible HTTPS URL |
| motion_id | string | required | Motion preset ID |
| prompt | string | auto-generated | Scene description |
| quality | string | "standard" | "lite", "turbo", or "standard" |

### generate_talking_head
Generate a talking head video from image + audio using Speak v2.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| image_url | string | required | Portrait image URL |
| audio_url | string | required | WAV audio URL |
| prompt | string | required | Scene description |
| quality | string | "high" | "high" or "mid" |
| duration | int | 5 | 5, 10, or 15 seconds |
| seed | int | 42 | Random seed (1–1000000) |

### upscale_media
Upscale or enhance an existing image.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| media_url | string | required | Image URL to upscale |
| model | string | "soul-pro" | "soul-pro" or "nano-banana-pro" |

### generate_and_animate (Pipeline)
Generate an image and animate it in one call.

### text_to_talking_head (Pipeline)
Generate an image and create a talking head video in one call.

### batch_generate
Queue multiple generation jobs at once.

### Character Tools
- `create_character(name, image_urls)` — Create a character reference (40 credits)
- `list_characters()` — List all characters
- `update_character(character_id, name?, image_urls?)` — Update a character
- `delete_character(character_id)` — Delete a character

### Creative Utilities
- `get_prompt_guide()` — Read the prompt engineering guide
- `extract_style_from_image(image_url)` — Find matching styles for an image
- `search_motions(query)` — Search motion presets by keyword

### Monitoring
- `get_generation_status(job_set_id)` — Check async job status
- `get_usage_stats()` — Check credit balance
- `validate_assets(urls, expected_type?)` — Validate URLs before sending

## Pricing

Credits are charged only on successful generation:

| Feature | Cost |
|---------|------|
| Image 720p | 1.5 credits ($0.09) |
| Image 1080p | 3 credits ($0.19) |
| Image 1080p (first 1000) | 1 credit ($0.06) |
| Video Lite | 2 credits ($0.125) |
| Video Turbo | 6.5 credits ($0.406) |
| Video Standard | 9 credits ($0.563) |
| Talking Head | varies |
| Character Creation | 40 credits ($2.50) |
| Upscale | varies |

Rate: $1 = 16 credits. Top up at: [https://cloud.higgsfield.ai/credits](https://cloud.higgsfield.ai/credits)

## Troubleshooting

### "Missing required environment variables"
- Ensure `.env` file exists with `HF_API_KEY` and `HF_SECRET`
- Or set environment variables in your shell or Claude Desktop config

### "401 Unauthorized"
- Verify your API key and secret are correct

### "402 Payment Required"
- Add credits at: [https://cloud.higgsfield.ai/credits](https://cloud.higgsfield.ai/credits)

### Server not appearing in Claude Desktop
- Check `cwd` is an absolute path (no `~` expansion)
- Restart Claude Desktop after config changes

### Generation stuck in "queued"
- Wait and poll again with `get_generation_status`
- Check your account has sufficient credits

## Project Structure

```
claude-higgsfield-mcp/
├── src/higgsfield_mcp/
│   ├── __init__.py          # Package init
│   ├── core.py              # Higgsfield API client (all endpoints)
│   ├── pipelines.py         # Multi-step workflow logic
│   ├── resources.py         # higgsfield:// URI handlers
│   └── server.py            # FastMCP wrapper (tools + resources)
├── tests/
│   └── test_core.py         # Schema & connection tests
├── pyproject.toml           # Poetry config
├── requirements.txt         # pip dependencies
├── .env.example             # Credential template
├── .mcp.json                # Claude Desktop config
└── README.md
```

## Development

```bash
# Install with Poetry
poetry install

# Run directly
python -m higgsfield_mcp.server

# Run in dev mode with FastMCP
fastmcp dev src/higgsfield_mcp/server.py

# Run tests
poetry run pytest
```

## Resources

- [Higgsfield AI Platform](https://higgsfield.ai)
- [Higgsfield API Documentation](https://platform.higgsfield.ai/docs)
- [Model Context Protocol](https://modelcontextprotocol.io)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)

## License

MIT — See [LICENSE](LICENSE) file for details.
