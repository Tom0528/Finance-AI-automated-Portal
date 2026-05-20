"""
Canva Connect API integration.

Exports a generated PDF into the team's Canva workspace as an editable design.
Requires CANVA_API_KEY to be set in the environment (.env).

Canva Connect API docs: https://www.canva.com/developers/docs/connect/
"""
import logging
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

CANVA_API_BASE = "https://api.canva.com/rest/v1"
_POLL_INTERVAL  = 2    # seconds between status checks
_POLL_MAX_TRIES = 20   # ~40 seconds total before giving up


class CanvaExportError(Exception):
    """Raised when the Canva export fails for any reason."""


def _auth_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
    }


def import_pdf_as_design(
    pdf_bytes: bytes,
    title: str,
    api_key: str,
    timeout: int = 30,
) -> str:
    """
    Upload *pdf_bytes* to Canva and return the edit URL of the new design.

    Steps
    ─────
    1. POST /v1/designs/import  → start an async import job
    2. Poll GET /v1/designs/import/{job_id}  until status == 'success'
    3. Return design['urls']['edit_url']

    Raises
    ──────
    CanvaExportError  on API errors, job failure, or timeout.
    """
    if not api_key:
        raise CanvaExportError(
            "CANVA_API_KEY is not configured. "
            "Add it to your .env file to enable Canva export."
        )

    headers = _auth_headers(api_key)

    # ── Step 1: start import ─────────────────────────────────────────────────
    logger.info("Starting Canva import: %s", title)
    try:
        resp = requests.post(
            f"{CANVA_API_BASE}/designs/import",
            headers=headers,
            files={"document": (f"{title}.pdf", pdf_bytes, "application/pdf")},
            data={"title": title},
            timeout=timeout,
        )
        resp.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        _raise_api_error("import", exc)
    except requests.exceptions.RequestException as exc:
        raise CanvaExportError(f"Network error contacting Canva: {exc}") from exc

    job_id: Optional[str] = resp.json().get("job", {}).get("id")
    if not job_id:
        raise CanvaExportError("Canva import response missing job ID.")

    # ── Step 2: poll for completion ──────────────────────────────────────────
    poll_url = f"{CANVA_API_BASE}/designs/import/{job_id}"
    for attempt in range(1, _POLL_MAX_TRIES + 1):
        time.sleep(_POLL_INTERVAL)
        try:
            poll = requests.get(poll_url, headers=headers, timeout=15)
            poll.raise_for_status()
        except requests.exceptions.RequestException as exc:
            logger.warning("Canva poll attempt %d failed: %s", attempt, exc)
            continue

        job = poll.json().get("job", {})
        status = job.get("status")

        if status == "success":
            edit_url: Optional[str] = (
                job.get("result", {})
                   .get("design", {})
                   .get("urls", {})
                   .get("edit_url")
            )
            if not edit_url:
                raise CanvaExportError("Canva returned success but no edit URL.")
            logger.info("Canva import complete: %s", edit_url)
            return edit_url

        if status == "failed":
            msg = job.get("error", {}).get("message", "unknown error")
            raise CanvaExportError(f"Canva import job failed: {msg}")

        logger.debug("Canva import status [%d/%d]: %s", attempt, _POLL_MAX_TRIES, status)

    raise CanvaExportError(
        f"Canva import did not complete after {_POLL_MAX_TRIES * _POLL_INTERVAL}s."
    )


def _raise_api_error(context: str, exc: requests.exceptions.HTTPError) -> None:
    status = exc.response.status_code if exc.response is not None else "?"
    try:
        detail = exc.response.json().get("message", exc.response.text)
    except Exception:
        detail = str(exc)
    raise CanvaExportError(
        f"Canva API error during {context} (HTTP {status}): {detail}"
    ) from exc
