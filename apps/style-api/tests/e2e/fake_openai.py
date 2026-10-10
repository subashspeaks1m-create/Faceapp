"""TEST FIXTURE ONLY: a local stand-in for OpenAI's /v1/images/edits used by the browser e2e test.

It is never imported by the app. It returns the uploaded photo sepia-toned and resized to the
requested size so a test can see that the real request path ran end to end. It is not an AI result.

    python -m tests.e2e.fake_openai --port 8791
"""

from __future__ import annotations

import argparse
import base64
import io
import os

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from PIL import Image, ImageOps

EXPECTED_KEY = os.environ.get("FAKE_OPENAI_KEY", "sk-e2e-fake-key-not-real")

app = FastAPI()
calls = {"count": 0}


@app.post("/v1/images/edits")
async def edits(request: Request) -> JSONResponse:
    if request.headers.get("authorization") != f"Bearer {EXPECTED_KEY}":
        return JSONResponse({"error": {"code": "invalid_api_key", "message": "bad key"}}, status_code=401)
    form = await request.form()
    calls["count"] += 1
    upload = form.get("image")
    raw = await upload.read()  # type: ignore[union-attr]
    w, h = (int(x) for x in str(form.get("size")).split("x"))
    with Image.open(io.BytesIO(raw)) as img:
        toned = ImageOps.colorize(ImageOps.grayscale(img), "#2b1a0e", "#f3d9a4").resize((w, h))
    out = io.BytesIO()
    toned.save(out, format="JPEG", quality=85)
    return JSONResponse({"created": 0, "data": [{"b64_json": base64.b64encode(out.getvalue()).decode()}], "usage": {"input_tokens": 1, "output_tokens": 1}})


@app.get("/calls")
async def count() -> JSONResponse:
    return JSONResponse(calls)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8791)
    uvicorn.run(app, host="127.0.0.1", port=parser.parse_args().port, log_level="warning")
