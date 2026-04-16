from __future__ import annotations

from app.config import DATABASE_PATH, EVIDENCE_DIR
from app.services.audit_service import AuditService
from app.storage.repository import AuditRepository


repository = AuditRepository(DATABASE_PATH, EVIDENCE_DIR)
service = AuditService(repository)


def get_audit_service() -> AuditService:
    return service
