from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from app.models import (
    AccessAuditEvent,
    EvidenceBundle,
    RetrievalQuery,
    VoiceAuditRecord,
    validate_audit_identifier,
)


class AuditRepository:
    def __init__(self, database_path: Path, evidence_dir: Path) -> None:
        self.database_path = database_path
        self.evidence_dir = evidence_dir
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with closing(self._connect()) as connection:
            self._migrate_schema(connection)
            self._create_tables(connection)
            connection.commit()

    def _migrate_schema(self, connection: sqlite3.Connection) -> None:
        if not self._needs_migration(connection):
            return

        legacy_tables: dict[str, str] = {}
        for table in ("audits", "findings", "access_events"):
            if self._table_exists(connection, table):
                legacy_name = f"{table}_legacy"
                connection.execute(f"ALTER TABLE {table} RENAME TO {legacy_name}")
                legacy_tables[table] = legacy_name

        self._create_tables(connection)

        if "audits" in legacy_tables:
            connection.execute(
                """
                INSERT INTO audits (
                    tenant, call_id, deployer, version, applicability, disposition, agent_version,
                    policy_version, high_risk_flag, emotion_or_biometric_features, human_handoff,
                    started_at, ended_at, created_at, legal_hold, evidence_path
                )
                SELECT
                    tenant, call_id, deployer, version, applicability, disposition, agent_version,
                    policy_version, high_risk_flag, emotion_or_biometric_features, human_handoff,
                    started_at, ended_at, created_at, legal_hold, evidence_path
                FROM audits_legacy
                """
            )

        if "findings" in legacy_tables and "audits" in legacy_tables:
            connection.execute(
                """
                INSERT INTO findings (
                    tenant, call_id, version, article, status, severity, reason,
                    evidence_span, evidence_type, manual_review_required,
                    linked_external_evidence_required
                )
                SELECT
                    a.tenant, f.call_id, f.version, f.article, f.status, f.severity, f.reason,
                    f.evidence_span, f.evidence_type, f.manual_review_required,
                    f.linked_external_evidence_required
                FROM findings_legacy f
                JOIN audits_legacy a ON a.call_id = f.call_id AND a.version = f.version
                """
            )

        if "access_events" in legacy_tables and "audits" in legacy_tables:
            connection.execute(
                """
                INSERT INTO access_events (
                    tenant, call_id, version, action, actor, timestamp, details
                )
                SELECT
                    a.tenant, e.call_id, e.version, e.action, e.actor, e.timestamp, e.details
                FROM access_events_legacy e
                JOIN audits_legacy a ON a.call_id = e.call_id AND a.version = e.version
                """
            )

        for legacy_name in legacy_tables.values():
            connection.execute(f"DROP TABLE {legacy_name}")

    def _needs_migration(self, connection: sqlite3.Connection) -> bool:
        if not self._table_exists(connection, "audits"):
            return False
        if not self._has_expected_unique_index(connection, "audits", ("tenant", "call_id", "version")):
            return True
        if "tenant" not in self._table_columns(connection, "findings"):
            return True
        if "tenant" not in self._table_columns(connection, "access_events"):
            return True
        return False

    def _table_exists(self, connection: sqlite3.Connection, table: str) -> bool:
        row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        return row is not None

    def _table_columns(self, connection: sqlite3.Connection, table: str) -> set[str]:
        if not self._table_exists(connection, table):
            return set()
        rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
        return {str(row["name"]) for row in rows}

    def _has_expected_unique_index(
        self,
        connection: sqlite3.Connection,
        table: str,
        expected_columns: tuple[str, ...],
    ) -> bool:
        for index in connection.execute(f"PRAGMA index_list({table})").fetchall():
            if not index["unique"]:
                continue
            columns = tuple(
                str(row["name"])
                for row in connection.execute(f"PRAGMA index_info({index['name']})").fetchall()
            )
            if columns == expected_columns:
                return True
        return False

    def _create_tables(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS audits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant TEXT NOT NULL,
                call_id TEXT NOT NULL,
                deployer TEXT NOT NULL,
                version INTEGER NOT NULL,
                applicability TEXT NOT NULL,
                disposition TEXT NOT NULL,
                agent_version TEXT NOT NULL,
                policy_version TEXT NOT NULL,
                high_risk_flag INTEGER NOT NULL,
                emotion_or_biometric_features INTEGER NOT NULL,
                human_handoff INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                legal_hold INTEGER NOT NULL,
                evidence_path TEXT NOT NULL,
                UNIQUE(tenant, call_id, version)
            );

            CREATE TABLE IF NOT EXISTS findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant TEXT NOT NULL,
                call_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                article TEXT NOT NULL,
                status TEXT NOT NULL,
                severity TEXT NOT NULL,
                reason TEXT NOT NULL,
                evidence_span TEXT NOT NULL,
                evidence_type TEXT NOT NULL,
                manual_review_required INTEGER NOT NULL,
                linked_external_evidence_required INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS access_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant TEXT NOT NULL,
                call_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                action TEXT NOT NULL,
                actor TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                details TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_audits_scoped_lookup
            ON audits (tenant, call_id, version DESC);

            CREATE INDEX IF NOT EXISTS idx_findings_scoped_lookup
            ON findings (tenant, call_id, version);

            CREATE INDEX IF NOT EXISTS idx_access_events_scoped_lookup
            ON access_events (tenant, call_id, version, timestamp);
            """
        )

    def next_version(self, tenant: str, call_id: str) -> int:
        tenant, call_id = self._scoped_identifiers(tenant, call_id)
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                SELECT COALESCE(MAX(version), 0) AS version
                FROM audits
                WHERE tenant = ? AND call_id = ?
                """,
                (tenant, call_id),
            )
            row = cursor.fetchone()
            return int(row["version"]) + 1 if row else 1

    def save_audit(self, record: VoiceAuditRecord) -> VoiceAuditRecord:
        tenant, call_id = self._scoped_identifiers(record.tenant, record.call_id)
        evidence_path = self._evidence_path(tenant, call_id, record.version)
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")

        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO audits (
                    tenant, call_id, deployer, version, applicability, disposition, agent_version,
                    policy_version, high_risk_flag, emotion_or_biometric_features, human_handoff,
                    started_at, ended_at, created_at, legal_hold, evidence_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tenant,
                    call_id,
                    record.deployer,
                    record.version,
                    record.applicability.value,
                    record.disposition,
                    record.agent_version,
                    record.policy_version,
                    int(record.compliance_evidence.high_risk_flag),
                    int(
                        record.compliance_evidence.emotion_recognition_used
                        or record.compliance_evidence.biometric_categorisation_used
                    ),
                    int(record.compliance_evidence.human_oversight_path_present),
                    record.started_at.isoformat(),
                    record.ended_at.isoformat(),
                    record.created_at.isoformat(),
                    int(record.integrity_privacy.legal_hold),
                    str(evidence_path),
                ),
            )
            connection.executemany(
                """
                INSERT INTO findings (
                    tenant, call_id, version, article, status, severity, reason,
                    evidence_span, evidence_type, manual_review_required,
                    linked_external_evidence_required
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        tenant,
                        call_id,
                        record.version,
                        finding.article,
                        finding.status.value,
                        finding.severity.value,
                        finding.reason,
                        finding.evidence_span,
                        finding.evidence_type.value,
                        int(finding.manual_review_required),
                        int(finding.linked_external_evidence_required),
                    )
                    for finding in record.findings
                ],
            )
            self._insert_access_event(connection, tenant, call_id, record.version, AccessAuditEvent(action="ingested"))
            connection.commit()
        return record

    def get_latest_audit(self, tenant: str, call_id: str) -> VoiceAuditRecord | None:
        tenant, call_id = self._scoped_identifiers(tenant, call_id)
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT evidence_path
                FROM audits
                WHERE tenant = ? AND call_id = ?
                ORDER BY version DESC
                LIMIT 1
                """,
                (tenant, call_id),
            ).fetchone()
        if not row:
            return None
        return self._read_record(Path(row["evidence_path"]))

    def list_audits(self) -> list[VoiceAuditRecord]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT evidence_path
                FROM audits
                WHERE (tenant, call_id, version) IN (
                    SELECT tenant, call_id, MAX(version)
                    FROM audits
                    GROUP BY tenant, call_id
                )
                ORDER BY created_at DESC
                """
            ).fetchall()
        return [self._read_record(Path(row["evidence_path"])) for row in rows]

    def query_findings(self, query: RetrievalQuery) -> list[dict[str, object]]:
        sql = """
            SELECT a.call_id, a.tenant, a.agent_version, a.policy_version, a.high_risk_flag,
                   a.emotion_or_biometric_features, a.human_handoff, a.started_at,
                   f.article, f.status, f.severity, f.reason
            FROM findings f
            JOIN audits a ON a.tenant = f.tenant AND a.call_id = f.call_id AND a.version = f.version
            WHERE 1 = 1
        """
        params: list[object] = []
        filters = {
            "article": ("f.article = ?", query.article),
            "status": ("f.status = ?", query.status.value if query.status else None),
            "severity": ("f.severity = ?", query.severity.value if query.severity else None),
            "tenant": ("a.tenant = ?", query.tenant),
            "agent_version": ("a.agent_version = ?", query.agent_version),
            "policy_version": ("a.policy_version = ?", query.policy_version),
            "high_risk_flag": (
                "a.high_risk_flag = ?",
                int(query.high_risk_flag) if query.high_risk_flag is not None else None,
            ),
            "emotion_or_biometric_features": (
                "a.emotion_or_biometric_features = ?",
                int(query.emotion_or_biometric_features)
                if query.emotion_or_biometric_features is not None
                else None,
            ),
            "human_handoff": (
                "a.human_handoff = ?",
                int(query.human_handoff) if query.human_handoff is not None else None,
            ),
            "date_from": ("a.started_at >= ?", query.date_from.isoformat() if query.date_from else None),
            "date_to": ("a.started_at <= ?", query.date_to.isoformat() if query.date_to else None),
        }
        for clause, value in filters.values():
            if value is not None:
                sql += f" AND {clause}"
                params.append(value)
        sql += " ORDER BY a.started_at DESC, f.article ASC"
        with closing(self._connect()) as connection:
            rows = connection.execute(sql, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def get_bundle(self, tenant: str, call_id: str) -> EvidenceBundle | None:
        record = self.get_latest_audit(tenant, call_id)
        if not record:
            return None
        self.log_access(
            tenant,
            call_id,
            record.version,
            AccessAuditEvent(action="bundle_exported", details="Evidence bundle requested"),
        )
        return EvidenceBundle(record=record, access_history=self.get_access_events(tenant, call_id, record.version))

    def get_access_events(self, tenant: str, call_id: str, version: int) -> list[AccessAuditEvent]:
        tenant, call_id = self._scoped_identifiers(tenant, call_id)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT action, actor, timestamp, details
                FROM access_events
                WHERE tenant = ? AND call_id = ? AND version = ?
                ORDER BY timestamp ASC
                """,
                (tenant, call_id, version),
            ).fetchall()
        return [
            AccessAuditEvent(
                action=row["action"],
                actor=row["actor"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                details=row["details"],
            )
            for row in rows
        ]

    def log_access(self, tenant: str, call_id: str, version: int, event: AccessAuditEvent) -> None:
        tenant, call_id = self._scoped_identifiers(tenant, call_id)
        with closing(self._connect()) as connection:
            self._insert_access_event(connection, tenant, call_id, version, event)
            connection.commit()

    def set_legal_hold(self, tenant: str, call_id: str, enabled: bool) -> VoiceAuditRecord | None:
        tenant, call_id = self._scoped_identifiers(tenant, call_id)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT version, evidence_path
                FROM audits
                WHERE tenant = ? AND call_id = ?
                ORDER BY version ASC
                """,
                (tenant, call_id),
            ).fetchall()
            if not rows:
                return None

            connection.execute(
                "UPDATE audits SET legal_hold = ? WHERE tenant = ? AND call_id = ?",
                (int(enabled), tenant, call_id),
            )
            latest_version = int(rows[-1]["version"])
            self._insert_access_event(
                connection,
                tenant,
                call_id,
                latest_version,
                AccessAuditEvent(action="legal_hold_updated", details=str(enabled)),
            )
            connection.commit()

        for row in rows:
            path = Path(row["evidence_path"])
            record = self._read_record(path)
            record.integrity_privacy.legal_hold = enabled
            path.write_text(record.model_dump_json(indent=2), encoding="utf-8")

        return self.get_latest_audit(tenant, call_id)

    def _insert_access_event(
        self,
        connection: sqlite3.Connection,
        tenant: str,
        call_id: str,
        version: int,
        event: AccessAuditEvent,
    ) -> None:
        connection.execute(
            """
            INSERT INTO access_events (tenant, call_id, version, action, actor, timestamp, details)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (tenant, call_id, version, event.action, event.actor, event.timestamp.isoformat(), event.details),
        )

    def _read_record(self, path: Path) -> VoiceAuditRecord:
        return VoiceAuditRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def _evidence_path(self, tenant: str, call_id: str, version: int) -> Path:
        tenant, call_id = self._scoped_identifiers(tenant, call_id)
        return self.evidence_dir / tenant / call_id / f"v{version}.json"

    def _scoped_identifiers(self, tenant: str, call_id: str) -> tuple[str, str]:
        return (
            validate_audit_identifier(tenant, "tenant"),
            validate_audit_identifier(call_id, "call_id"),
        )
