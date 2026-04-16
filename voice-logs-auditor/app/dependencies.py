from __future__ import annotations

from app.config import DATABASE_PATH, EVIDENCE_DIR, REPORT_PATH
from app.services.audit_service import AuditService
from app.services.report_service import ReportService
from app.storage.repository import AuditRepository


repository = AuditRepository(DATABASE_PATH, EVIDENCE_DIR)
service = AuditService(repository)
report_service = ReportService(REPORT_PATH)


def get_audit_service() -> AuditService:
    return service


def get_report_service() -> ReportService:
    return report_service
