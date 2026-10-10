"""Vercel Python entry point. Vercel serves the ASGI `app` object from this module."""

import logging

from styleapi.app import create_app

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

app = create_app()
