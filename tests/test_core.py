"""Schema validation tests — ensure FastMCP server tools accept correct input types."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestToolInputValidation:
    """Verify that tools properly reject invalid inputs before hitting the API."""

    def test_generate_image_requires_prompt(self):
        """generate_image should fail without a prompt parameter."""
        from higgsfield_mcp.server import generate_image
        with pytest.raises(TypeError):
            # Missing required 'prompt' arg
            import asyncio
            asyncio.get_event_loop().run_until_complete(generate_image())

    def test_generate_video_requires_image_and_motion(self):
        """generate_video should require both image_url and motion_id."""
        from higgsfield_mcp.server import generate_video
        import asyncio
        with pytest.raises(TypeError):
            asyncio.get_event_loop().run_until_complete(generate_video(image_url="http://x.com/img.jpg"))
        with pytest.raises(TypeError):
            asyncio.get_event_loop().run_until_complete(generate_video(motion_id="m-1"))

    def test_create_character_requires_name_and_urls(self):
        """create_character should require both name and image_urls."""
        from higgsfield_mcp.server import create_character
        import asyncio
        with pytest.raises(TypeError):
            asyncio.get_event_loop().run_until_complete(create_character(name="test"))
        with pytest.raises(TypeError):
            asyncio.get_event_loop().run_until_complete(create_character(image_urls=["http://x.com"]))

    def test_upscale_requires_url(self):
        """upscale_media should require media_url."""
        from higgsfield_mcp.server import upscale_media
        import asyncio
        with pytest.raises(TypeError):
            asyncio.get_event_loop().run_until_complete(upscale_media())


class TestClientSchema:
    """Verify the API client builds correct request structures."""

    @pytest.mark.asyncio
    async def test_generate_image_payload_structure(self):
        """Ensure generate_image sends correct payload format."""
        from higgsfield_mcp.core import HiggsfieldClient

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": "j1", "type": "text2image", "jobs": []}
        mock_resp.raise_for_status = MagicMock()

        client = HiggsfieldClient(api_key="test", secret="test")

        with patch("higgsfield_mcp.core.httpx.AsyncClient") as MockClient:
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=ctx)
            ctx.post = AsyncMock(return_value=mock_resp)
            MockClient.return_value = ctx

            await client.generate_image(prompt="a cat", quality="720p", batch_size=4)

            call_kwargs = ctx.post.call_args.kwargs
            body = call_kwargs["json"]
            assert "params" in body
            assert body["params"]["prompt"] == "a cat"
            assert body["params"]["quality"] == "720p"
            assert body["params"]["batch_size"] == 4

    @pytest.mark.asyncio
    async def test_generate_video_payload_structure(self):
        """Ensure generate_video uses input_images array format."""
        from higgsfield_mcp.core import HiggsfieldClient

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": "j1", "type": "image2video", "jobs": []}
        mock_resp.raise_for_status = MagicMock()

        client = HiggsfieldClient(api_key="test", secret="test")

        with patch("higgsfield_mcp.core.httpx.AsyncClient") as MockClient:
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=ctx)
            ctx.post = AsyncMock(return_value=mock_resp)
            MockClient.return_value = ctx

            await client.generate_video(
                image_url="https://example.com/img.png",
                motion_id="m-1",
                prompt="a scene",
            )

            call_kwargs = ctx.post.call_args.kwargs
            body = call_kwargs["json"]
            assert "params" in body
            assert body["params"]["input_images"] == [{"type": "image_url", "image_url": "https://example.com/img.png"}]
            assert body["params"]["motions"] == [{"id": "m-1", "strength": 0.5}]


class TestConnection:
    """Lightweight connection / credential tests."""

    @pytest.mark.asyncio
    async def test_debug_credentials_returns_json(self):
        """debug_credentials tool should return valid JSON."""
        import json
        from higgsfield_mcp.server import debug_credentials

        result = await debug_credentials()
        parsed = json.loads(result)
        assert "api_key_configured" in parsed
        assert "secret_configured" in parsed
        assert "base_url" in parsed
