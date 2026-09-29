"""Vercel Python serverless entrypoint. Vercel's Python runtime detects the
module-level `app` ASGI application and wraps it; all requests to /api/** are
routed here per vercel.json.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _app.main import app  # noqa: E402,F401
