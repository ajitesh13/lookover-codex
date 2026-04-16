from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_audit_service
from app.models import (
    AuditIngestRequest,
    FindingStatus,
    InvalidAuditIdentifier,
    LegalHoldRequest,
    RetrievalQuery,
    Severity,
)
from app.services.audit_service import AuditService


router = APIRouter(prefix="/api", tags=["api"])


@router.post("/audits")
def create_audit(payload: AuditIngestRequest, service: AuditService = Depends(get_audit_service)):
    try:
        return service.ingest_audit(payload)
    except InvalidAuditIdentifier as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/audits/{call_id}")
def get_audit(
    call_id: str,
    tenant: str = Query(...),
    service: AuditService = Depends(get_audit_service),
):
    try:
        record = service.get_audit(tenant, call_id)
    except InvalidAuditIdentifier as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not record:
        raise HTTPException(status_code=404, detail="Audit not found")
    return record


@router.get("/audits/{call_id}/bundle")
def get_bundle(
    call_id: str,
    tenant: str = Query(...),
    service: AuditService = Depends(get_audit_service),
):
    try:
        bundle = service.get_bundle(tenant, call_id)
    except InvalidAuditIdentifier as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not bundle:
        raise HTTPException(status_code=404, detail="Audit not found")
    return bundle


@router.post("/audits/{call_id}/reanalyse")
def reanalyse(
    call_id: str,
    tenant: str = Query(...),
    service: AuditService = Depends(get_audit_service),
):
    try:
        record = service.reanalyse(tenant, call_id)
    except InvalidAuditIdentifier as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not record:
        raise HTTPException(status_code=404, detail="Audit not found")
    return record


@router.post("/audits/{call_id}/legal-hold")
def update_legal_hold(
    call_id: str,
    payload: LegalHoldRequest,
    tenant: str = Query(...),
    service: AuditService = Depends(get_audit_service),
):
    try:
        record = service.set_legal_hold(tenant, call_id, payload)
    except InvalidAuditIdentifier as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not record:
        raise HTTPException(status_code=404, detail="Audit not found")
    return record


@router.get("/findings")
def list_findings(
    article: str | None = None,
    status: FindingStatus | None = None,
    severity: Severity | None = None,
    tenant: str | None = None,
    agent_version: str | None = None,
    policy_version: str | None = None,
    high_risk_flag: bool | None = None,
    emotion_or_biometric_features: bool | None = None,
    human_handoff: bool | None = None,
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    service: AuditService = Depends(get_audit_service),
):
    query = RetrievalQuery(
        article=article,
        status=status,
        severity=severity,
        tenant=tenant,
        agent_version=agent_version,
        policy_version=policy_version,
        high_risk_flag=high_risk_flag,
        emotion_or_biometric_features=emotion_or_biometric_features,
        human_handoff=human_handoff,
        date_from=date_from,
        date_to=date_to,
    )
    return service.list_findings(query)
