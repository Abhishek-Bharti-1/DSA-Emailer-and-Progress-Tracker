"""
Cloud Run HTTP Entry Point for DSA Problems Daily Emailer.
Receives authenticated triggers from Google Cloud Scheduler or HTTP calls.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse

# Ensure root directory is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.main import handle_daily, handle_weekly, handle_refresh
from src.state import StateManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("api")

app = FastAPI(
    title="DSA Problems Daily Emailer Cloud Service",
    description="Automated AI-curated DSA problems emailer running on Google Cloud Run",
    version="1.0.0",
)


@app.get("/")
def index():
    state_mgr = StateManager()
    progress = state_mgr.get_progress()
    return {
        "service": "DSA Problems Daily Emailer",
        "status": "healthy",
        "mode": "firestore" if os.environ.get("USE_FIRESTORE") == "true" else "local_json",
        "streak_days": progress.get("streak_days", 0),
        "total_sent": progress.get("total_sent", 0),
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/jobs/daily", status_code=status.HTTP_200_OK)
def trigger_daily():
    logger.info("Received trigger for daily DSA email job")
    try:
        exit_code = handle_daily()
        if exit_code != 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Daily problem routine failed. Check Cloud Run logs for details.",
            )
        return {"status": "success", "message": "Daily DSA email dispatched successfully"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in /jobs/daily: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/jobs/weekly", status_code=status.HTTP_200_OK)
def trigger_weekly():
    logger.info("Received trigger for weekly DSA progress report job")
    try:
        exit_code = handle_weekly()
        if exit_code != 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Weekly report routine failed. Check Cloud Run logs for details.",
            )
        return {"status": "success", "message": "Weekly progress report dispatched successfully"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in /jobs/weekly: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/jobs/refresh", status_code=status.HTTP_200_OK)
def trigger_refresh():
    logger.info("Received trigger for cache refresh job")
    try:
        exit_code = handle_refresh()
        if exit_code != 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Cache refresh routine failed.",
            )
        return {"status": "success", "message": "Cache refreshed successfully"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in /jobs/refresh: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("app:app", host="0.0.0.0", port=port, log_level="info")
