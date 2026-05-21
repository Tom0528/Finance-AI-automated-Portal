"""
Modal deployment for AW Client Report Portal.

Setup:
    pip install modal
    modal setup              # authenticate (opens browser)
    modal deploy modal_app.py

Your live URL will be printed after deploy, e.g.:
    https://<your-org>--aw-client-portal-serve.modal.run
"""
import modal
from pathlib import Path

APP_DIR = Path(__file__).parent / "app"

# ── Container image ───────────────────────────────────────────────────────────
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install_from_requirements(str(APP_DIR / "requirements.txt"))
    .add_local_dir(str(APP_DIR), remote_path="/app")
)

# ── Persistent SQLite volume ──────────────────────────────────────────────────
db_volume = modal.Volume.from_name("aw-portal-db", create_if_missing=True)

# ── Modal app ─────────────────────────────────────────────────────────────────
app = modal.App("aw-client-portal")


@app.function(
    image=image,
    volumes={"/data": db_volume},
    # Once you create a secret named 'aw-portal-secrets' in modal.com → Secrets,
    # replace the line below with: secrets=[modal.Secret.from_name("aw-portal-secrets")]
    secrets=[],
    min_containers=1,   # keep one warm container — no cold starts during demo
)
@modal.concurrent(max_inputs=20)
@modal.wsgi_app()
def serve():
    import os
    import sys

    sys.path.insert(0, "/app")
    os.environ.setdefault("DATABASE_PATH", "/data/portal.db")
    os.environ.setdefault("FLASK_ENV", "production")
    os.environ.setdefault("SECRET_KEY", "change-me-set-in-modal-secrets")

    from wsgi import application  # noqa: E402
    return application
