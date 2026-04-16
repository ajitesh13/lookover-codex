from __future__ import annotations

import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from app.config import BASE_DIR, SAMPLE_PAYLOAD_DIR
from app.dependencies import get_audit_service
from app.models import AuditIngestRequest, GovernanceLink, InvalidAuditIdentifier, SourceEvidence, TranscriptTurn
from app.services.audit_service import AuditService


router = APIRouter(tags=["html"])
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _load_samples() -> list[dict[str, object]]:
    samples: list[dict[str, object]] = []
    for path in sorted(SAMPLE_PAYLOAD_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        samples.append({"name": path.stem, "payload": payload})
    return samples


@router.get("/")
def home(request: Request, service: AuditService = Depends(get_audit_service)):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"samples": _load_samples(), "audits": service.list_audits()},
    )


@router.post("/submit")
def submit_form(
    request: Request,
    call_id: str = Form(...),
    tenant: str = Form(...),
    deployer: str = Form(...),
    transcript: str = Form(...),
    synthetic_audio_used: bool = Form(False),
    synthetic_audio_marked: bool = Form(False),
    deepfake_like_content_flag: bool = Form(False),
    emotion_recognition_used: bool = Form(False),
    biometric_categorisation_used: bool = Form(False),
    decision_support_flag: bool = Form(False),
    human_oversight_path_present: bool = Form(False),
    high_risk_flag: bool = Form(False),
    service: AuditService = Depends(get_audit_service),
):
    now = datetime.utcnow()
    turns = [
        TranscriptTurn(speaker="agent" if index % 2 == 0 else "customer", text=line.strip(), timestamp_seconds=index * 8.0)
        for index, line in enumerate(transcript.splitlines())
        if line.strip()
    ]
    try:
        payload = AuditIngestRequest(
            call_id=call_id,
            tenant=tenant,
            deployer=deployer,
            started_at=now,
            ended_at=now + timedelta(minutes=3),
            source_evidence=SourceEvidence(
                raw_audio_uri=f"file:///{call_id}.wav",
                synthetic_audio_used=synthetic_audio_used,
                synthetic_audio_marked=synthetic_audio_marked,
                deepfake_like_content_flag=deepfake_like_content_flag,
            ),
            transcript_turns=turns,
            governance_links=[
                GovernanceLink(document_type="provider_instructions", reference="provider-instructions.pdf"),
                GovernanceLink(document_type="logging_policy", reference="logging-policy.pdf"),
            ],
            emotion_recognition_used=emotion_recognition_used,
            biometric_categorisation_used=biometric_categorisation_used,
            decision_support_flag=decision_support_flag,
            human_oversight_path_present=human_oversight_path_present,
            high_risk_flag=high_risk_flag,
        )
        record = service.ingest_audit(payload)
    except (InvalidAuditIdentifier, ValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url=f"/audits/{record.call_id}?tenant={record.tenant}", status_code=303)


@router.get("/audits")
def audits_page(request: Request, service: AuditService = Depends(get_audit_service)):
    return templates.TemplateResponse(request, "audits.html", {"audits": service.list_audits()})


@router.get("/audits/{call_id}")
def audit_detail(
    call_id: str,
    request: Request,
    tenant: str = Query(...),
    service: AuditService = Depends(get_audit_service),
):
    try:
        record = service.get_audit(tenant, call_id)
        access_history = service.get_access_history(tenant, call_id) if record else []
    except InvalidAuditIdentifier as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return templates.TemplateResponse(
        request,
        "audit_detail.html",
        {"record": record, "access_history": access_history, "tenant": tenant},
    )
