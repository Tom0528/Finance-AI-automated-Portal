"""
Application configuration – loaded from environment variables.
All sensitive values live in .env (never committed).
"""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the directory that contains this file
load_dotenv(Path(__file__).parent / ".env")


class Config:
    # ── Security ────────────────────────────────────────────────────────────────
    SECRET_KEY: str = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

    # ── Database ─────────────────────────────────────────────────────────────────
    # On Railway, mount a volume and set RAILWAY_DATABASE_PATH to the volume path.
    # Locally, defaults to portal.db in the app directory.
    DATABASE_PATH: str = (
        os.environ.get("RAILWAY_DATABASE_PATH")
        or os.environ.get("DATABASE_PATH")
        or str(Path(__file__).parent / "portal.db")
    )

    # ── Canva Connect API ─────────────────────────────────────────────────────────
    # Obtain from https://www.canva.com/developers → Your Integrations → API Keys.
    # Set CANVA_API_KEY in .env to enable the "Export to Canva" feature.
    CANVA_API_KEY: str = os.environ.get("CANVA_API_KEY", "")

    # ── Server ───────────────────────────────────────────────────────────────────
    PORT: int = int(os.environ.get("PORT", 5000))
    DEBUG: bool = os.environ.get("FLASK_ENV", "production") == "development"

    # ── Derived helpers ──────────────────────────────────────────────────────────
    @property
    def canva_enabled(self) -> bool:
        return bool(self.CANVA_API_KEY)
