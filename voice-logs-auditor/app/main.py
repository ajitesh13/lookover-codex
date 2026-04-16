from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR, ensure_runtime_dirs
from app.dependencies import get_audit_service
from app.routes.api import router as api_router
from app.routes.html import router as html_router


ensure_runtime_dirs()


app = FastAPI(title="Voice Logs Auditor", version="0.1.0")


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.include_router(api_router)
app.include_router(html_router)
