"""LIVE test: calls the real OpenAI image edit API and costs money.

Runs only when STYLE_API_LIVE=1 and OPENAI_API_KEY are set in your shell (never commit the key):

    STYLE_API_LIVE=1 OPENAI_API_KEY=... python -m unittest tests.live.test_openai_live -v

Uses the synthetic demo portrait (assets/demo, fictional adult). Writes the result to
STYLE_API_LIVE_OUT (default: a temp dir) for a human to review identity and style.
"""

import asyncio
import os
import tempfile
import time
import unittest
from pathlib import Path

from styleapi.catalog import build_prompt, load_catalog
from styleapi.config import load_settings
from styleapi.images import finalize_output, prepare_upload
from styleapi.providers import EditRequest, OpenAIImageEditProvider

DEMO = Path(__file__).resolve().parents[4] / "assets" / "demo" / "portrait-original.png"


@unittest.skipUnless(os.environ.get("STYLE_API_LIVE") == "1" and os.environ.get("OPENAI_API_KEY"), "live test: set STYLE_API_LIVE=1 and OPENAI_API_KEY")
class OpenAILiveTest(unittest.TestCase):
    def test_one_style_end_to_end(self) -> None:
        settings = load_settings({**os.environ, "APP_ENV": "development", "RATE_LIMIT_BACKEND": "disabled"})
        assert settings.openai_api_key is not None
        provider = OpenAIImageEditProvider(
            settings.openai_api_key.get_secret_value(),
            model=settings.openai_model,
            quality=settings.openai_quality,
            base_url=settings.openai_base_url,
            timeout_seconds=settings.provider_timeout_seconds,
        )
        style_id = os.environ.get("STYLE_API_LIVE_STYLE", "seventies-film")
        style = load_catalog().style(style_id)
        assert style is not None, style_id
        prepared = prepare_upload(DEMO.read_bytes(), "image/png", max_bytes=4_000_000, max_pixels=16_000_000, min_side=256)
        started = time.perf_counter()
        result = asyncio.run(provider.edit(EditRequest(prepared.png, build_prompt(style, 60), prepared.size)))
        elapsed = time.perf_counter() - started
        jpeg, w, h = finalize_output(result.image)
        out_dir = Path(os.environ.get("STYLE_API_LIVE_OUT") or tempfile.mkdtemp(prefix="style-live-"))
        out = out_dir / f"{style.id}-{result.model}.jpg"
        out.write_bytes(jpeg)
        print(f"\nmodel={result.model} style={style.id} size={w}x{h} seconds={elapsed:.1f} input_tokens={result.input_tokens} output_tokens={result.output_tokens} file={out}")
        self.assertEqual(prepared.size, f"{w}x{h}")


if __name__ == "__main__":
    unittest.main()
