"""Standalone Desktop Entry Point for Prompt Compiler FastAPI Backend.

This module provides a production entry point when packaged as a standalone
executable (e.g. via PyInstaller for Tauri sidecar integration).
It starts the uvicorn server directly on the configured desktop host and port,
without requiring an external Python interpreter or reloading process.
"""

import argparse
import os
import sys
import uvicorn

# Ensure backend root is on sys.path if running as script
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from app.config import settings
from app.main import app


def parse_args() -> argparse.Namespace:
    """Parse optional command line arguments."""
    parser = argparse.ArgumentParser(description="Prompt Compiler Desktop Backend Server")
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Host address to bind to (defaults to DESKTOP_BACKEND_HOST or 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port number to bind to (defaults to DESKTOP_BACKEND_PORT or 8000)",
    )
    return parser.parse_args()


def main() -> None:
    """Launch the FastAPI application server."""
    args = parse_args()

    # Host resolution: CLI arg > environment/settings
    host = args.host or settings.desktop_backend_host
    if host not in ("127.0.0.1", "localhost", "::1") and settings.desktop_mode:
        host = "127.0.0.1"

    # Port resolution: CLI arg > environment/settings
    port = args.port or settings.desktop_backend_port

    print(f"[Desktop Backend] Starting Prompt Compiler backend on http://{host}:{port}", flush=True)
    print(f"[Desktop Backend] Data Directory: {settings.app_data_dir or 'local development'}", flush=True)
    print(f"[Desktop Backend] Database: {settings.database_url}", flush=True)

    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info",
        access_log=False,
        loop="asyncio",
    )
    server = uvicorn.Server(config)
    server.run()


if __name__ == "__main__":
    main()
