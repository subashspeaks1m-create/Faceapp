"""LIVE test: calls the configured real provider (OpenAI or Gemini) and costs money.

Runs only when STYLE_API_LIVE=1 and the provider's key is set in your own shell (never commit it):

    STYLE_API_LIVE=1 OPENAI_API_KEY=... python -m unittest tests.live.test_provider_live -v
    STYLE_API_LIVE=1 IMAGE_PROVIDER=gemini GEMINI_API_KEY=... python -m unittest tests.live.test_provider_live -v

Uses the synthetic demo portrait (assets/demo, fictional adult). Writes the result to
STYLE_API_LIVE_OUT (default: a temp dir) for a human to review identity and style.
"""

import asyncio
import os
import tempfile
import time
import unittest
from pathlib import Path

from styleapi.app import _make_provider
from styleapi.catalog import build_prompt, load_catalog
from styleapi.config import load_settings
from styleapi.images import finalize_output, prepare_upload
from styleapi.providers import EditRequest

DEMO = Path(__file__).resolve().parents[4] / "assets" / "demo" / "portrait-original.png"
LIVE = os.environ.get("STYLE_API_LIVE") == "1" and bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("GEMINI_API_KEY"))


@unittest.skipUnless(LIVE, "live test: set STYLE_API_LIVE=1 and OPENAI_API_KEY or GEMINI_API_KEY")
class ProviderLiveTest(unittest.TestCase):
    def test_one_style_end_to_end(self) -> None:
        settings = load_settings({**os.environ, "APP_ENV": "development", "RATE_LIMIT_BACKEND": "disabled"})
        provider = _make_provider(settings)
        assert provider is not None, "the selected provider has no key"
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
        print(f"\nprovider={provider.name} model={result.model} style={style.id} size={w}x{h} seconds={elapsed:.1f} "
              f"input_tokens={result.input_tokens} output_tokens={result.output_tokens} file={out}")
        rw, rh = (int(x) for x in prepared.size.split("x"))
        # Output keeps the requested orientation (exact pixels differ by provider).
        self.assertAlmostEqual(w / h, rw / rh, delta=0.05)


if __name__ == "__main__":
    unittest.main()
