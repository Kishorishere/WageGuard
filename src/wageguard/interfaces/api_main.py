"""Uvicorn entry point for the FastAPI app."""

from __future__ import annotations

import uvicorn

from wageguard.config import Settings
from wageguard.interfaces.api import create_app


def main() -> None:
    settings = Settings()
    app = create_app(settings)
    uvicorn.run(
        app, host=settings.api_host, port=settings.api_port, log_level=settings.log_level.lower()
    )


if __name__ == "__main__":
    main()
