package store

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"database/sql"
	_ "embed"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/ajitesh/lookover-codex/backend/internal/controls"
	"github.com/ajitesh/lookover-codex/backend/internal/types"
	_ "github.com/jackc/pgx/v5/stdlib"
	"golang.org/x/crypto/bcrypt"
)

//go:embed schema.sql
var schemaSQL string

type Store struct {
	db *sql.DB
}

func New(databaseURL string) (*Store, error) {
	db, err := sql.Open("pgx", databaseURL)
	if err != nil {
		return nil, fmt.Errorf("open db: %w", err)
	}
	db.SetMaxOpenConns(10)
	db.SetMaxIdleConns(10)
	db.SetConnMaxLifetime(30 * time.Minute)

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err = db.PingContext(ctx); err != nil {
		return nil, fmt.Errorf("ping db: %w", err)
	}
	return &Store{db: db}, nil
}

func (s *Store) Close() error {
	return s.db.Close()
}

func (s *Store) Migrate(ctx context.Context) error {
	if _, err := s.db.ExecContext(ctx, schemaSQL); err != nil {
		return fmt.Errorf("migrate schema: %w", err)
	}
	return nil
}

func (s *Store) UpsertPolicyVersion(ctx context.Context, manifest controls.Manifest) error {
	id := fmt.Sprintf("%s-v%d", strings.ToLower(manifest.Framework), manifest.Version)
	_, err := s.db.ExecContext(ctx, `
		INSERT INTO policy_versions (id, framework, version, description, controls_count, loaded_at)
		VALUES ($1, $2, $3, $4, $5, NOW())
		ON CONFLICT (id) DO UPDATE SET
			description = EXCLUDED.description,
			controls_count = EXCLUDED.controls_count,
			loaded_at = NOW()
	`, id, manifest.Framework, fmt.Sprintf("%d", manifest.Version), manifest.Description, len(manifest.Controls))
	if err != nil {
		return fmt.Errorf("upsert policy version: %w", err)
	}
	return nil
}

func (s *Store) UpsertRuntimeEvent(ctx context.Context, event types.RuntimeEvent) error {
	traceMeta := cloneMap(event.Attributes)
	traceMeta["trace_id"] = event.TraceID
	traceMeta["session_id"] = event.SessionID
	traceMeta["agent_id"] = event.AgentID
	traceMeta["agent_version"] = event.AgentVersion
	traceMeta["event_type"] = event.EventType
	traceMeta["status"] = event.Status

	payloadBytes, err := json.Marshal(traceMeta)
	if err != nil {
		return fmt.Errorf("marshal runtime metadata: %w", err)
	}

	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("begin tx: %w", err)
	}
	defer func() {
		if err != nil {
			_ = tx.Rollback()
		}
	}()

	_, err = tx.ExecContext(ctx, `
		INSERT INTO decision_traces (
			trace_id, session_id, agent_id, agent_version, framework, model_id,
			model_provider, model_version, ai_act_risk_tier, use_case_category,
			environment, metadata, created_at, updated_at
		)
		VALUES (
			$1, $2, $3, $4, $5, $6,
			$7, $8, $9, $10,
			$11, $12::jsonb, NOW(), NOW()
		)
		ON CONFLICT (trace_id) DO UPDATE SET
			session_id = COALESCE(NULLIF(EXCLUDED.session_id, ''), decision_traces.session_id),
			agent_id = COALESCE(NULLIF(EXCLUDED.agent_id, ''), decision_traces.agent_id),
			agent_version = COALESCE(NULLIF(EXCLUDED.agent_version, ''), decision_traces.agent_version),
			framework = COALESCE(NULLIF(EXCLUDED.framework, ''), decision_traces.framework),
			model_id = COALESCE(NULLIF(EXCLUDED.model_id, ''), decision_traces.model_id),
			model_provider = COALESCE(NULLIF(EXCLUDED.model_provider, ''), decision_traces.model_provider),
			model_version = COALESCE(NULLIF(EXCLUDED.model_version, ''), decision_traces.model_version),
			ai_act_risk_tier = COALESCE(NULLIF(EXCLUDED.ai_act_risk_tier, ''), decision_traces.ai_act_risk_tier),
			use_case_category = COALESCE(NULLIF(EXCLUDED.use_case_category, ''), decision_traces.use_case_category),
			environment = COALESCE(NULLIF(EXCLUDED.environment, ''), decision_traces.environment),
			metadata = decision_traces.metadata || EXCLUDED.metadata,
			updated_at = NOW()
	`,
		event.TraceID,
		event.SessionID,
		event.AgentID,
		event.AgentVersion,
		asString(event.Attributes["framework"]),
		asString(event.Attributes["model_id"]),
		asString(event.Attributes["model_provider"]),
		asString(event.Attributes["model_version"]),
		asString(event.Attributes["ai_act_risk_tier"]),
		asString(event.Attributes["use_case_category"]),
		asString(event.Attributes["environment"]),
		string(payloadBytes),
	)
	if err != nil {
		return fmt.Errorf("upsert trace: %w", err)
	}

	prevHash, prevErr := s.previousChainHash(ctx, tx, event.TraceID)
	if prevErr != nil {
		err = fmt.Errorf("load previous chain hash: %w", prevErr)
		return err
	}

	payload := cloneMap(traceMeta)
	payload["span_id"] = event.SpanID
	payload["parent_span_id"] = event.ParentSpanID
	payload["name"] = event.Name
	payload["start_time"] = event.StartTime
	payload["end_time"] = event.EndTime

	payloadHash := digestJSON(payload)
	chainHash := digestString(prevHash + payloadHash)
	signedChainHash := digestString("signed:" + chainHash)

	payload["payload_hash"] = payloadHash
	payload["chain_hash"] = chainHash
	payload["signed_chain_hash"] = signedChainHash
	payload["previous_hash"] = prevHash

	spanPayload, marshalErr := json.Marshal(payload)
	if marshalErr != nil {
		err = fmt.Errorf("marshal span payload: %w", marshalErr)
		return err
	}

	_, err = tx.ExecContext(ctx, `
		INSERT INTO spans (
			span_id, trace_id, parent_span_id, name, event_type, status,
			start_time, end_time, payload, created_at
		)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, NOW())
		ON CONFLICT (span_id) DO UPDATE SET
			parent_span_id = EXCLUDED.parent_span_id,
			name = EXCLUDED.name,
			event_type = EXCLUDED.event_type,
			status = EXCLUDED.status,
			start_time = LEAST(spans.start_time, EXCLUDED.start_time),
			end_time = GREATEST(spans.end_time, EXCLUDED.end_time),
			payload = spans.payload || EXCLUDED.payload
	`, event.SpanID, event.TraceID, event.ParentSpanID, event.Name, event.EventType, event.Status, event.StartTime, event.EndTime, string(spanPayload))
	if err != nil {
		return fmt.Errorf("upsert span: %w", err)
	}

	evidenceValue, evidenceErr := json.Marshal(payload)
	if evidenceErr != nil {
		err = fmt.Errorf("marshal evidence: %w", evidenceErr)
		return err
	}
	_, err = tx.ExecContext(ctx, `
		INSERT INTO evidence_records (
			id, trace_id, span_id, source, field_name, value,
			previous_hash, payload_hash, chain_hash, signed_chain_hash, created_at
		)
		VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10, NOW())
	`, newID("ev"), event.TraceID, event.SpanID, "runtime_event", "event_payload", string(evidenceValue), prevHash, payloadHash, chainHash, signedChainHash)
	if err != nil {
		return fmt.Errorf("insert evidence: %w", err)
	}

	if commitErr := tx.Commit(); commitErr != nil {
		return fmt.Errorf("commit runtime event: %w", commitErr)
	}
	return nil
}

func (s *Store) SavePreRunScan(ctx context.Context, scan types.PreRunScan) error {
	frameworks, err := json.Marshal(scan.Frameworks)
	if err != nil {
		return fmt.Errorf("marshal scan frameworks: %w", err)
	}
	summary, err := json.Marshal(scan.Summary)
	if err != nil {
		return fmt.Errorf("marshal scan summary: %w", err)
	}

	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("begin scan tx: %w", err)
	}
	defer func() {
		if err != nil {
			_ = tx.Rollback()
		}
	}()

	if scan.ScanID == "" {
		scan.ScanID = newID("scan")
	}

	_, err = tx.ExecContext(ctx, `
		INSERT INTO pre_run_scans (scan_id, project_path, strict_mode, readiness_score, strict_result, frameworks, summary, created_at)
		VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, NOW())
		ON CONFLICT (scan_id) DO UPDATE SET
			project_path = EXCLUDED.project_path,
			strict_mode = EXCLUDED.strict_mode,
			readiness_score = EXCLUDED.readiness_score,
			strict_result = EXCLUDED.strict_result,
			frameworks = EXCLUDED.frameworks,
			summary = EXCLUDED.summary
	`, scan.ScanID, scan.ProjectPath, scan.StrictMode, scan.ReadinessScore, scan.StrictResult, string(frameworks), string(summary))
	if err != nil {
		return fmt.Errorf("upsert pre-run scan: %w", err)
	}

	if _, err = tx.ExecContext(ctx, `DELETE FROM pre_run_findings WHERE scan_id = $1`, scan.ScanID); err != nil {
		return fmt.Errorf("clear findings: %w", err)
	}

	for _, finding := range scan.Findings {
		if finding.ID == "" {
			finding.ID = newID("prf")
		}
		controlRefs, marshalErr := json.Marshal(finding.ControlRefs)
		if marshalErr != nil {
			err = fmt.Errorf("marshal finding control refs: %w", marshalErr)
			return err
		}
		evidence, marshalErr := json.Marshal(finding.Evidence)
		if marshalErr != nil {
			err = fmt.Errorf("marshal finding evidence: %w", marshalErr)
			return err
		}
		_, err = tx.ExecContext(ctx, `
			INSERT INTO pre_run_findings (id, scan_id, rule_id, title, severity, status, control_refs, evidence, remediation, created_at)
			VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9, NOW())
		`, finding.ID, scan.ScanID, finding.RuleID, finding.Title, finding.Severity, finding.Status, string(controlRefs), string(evidence), finding.Remediation)
		if err != nil {
			return fmt.Errorf("insert pre-run finding: %w", err)
		}
	}

	if commitErr := tx.Commit(); commitErr != nil {
		return fmt.Errorf("commit pre-run scan: %w", commitErr)
	}
	return nil
}

func (s *Store) ListPreRunScans(ctx context.Context) ([]types.PreRunScan, error) {
	rows, err := s.db.QueryContext(ctx, `
		SELECT scan_id, project_path, strict_mode, readiness_score, strict_result, frameworks, summary, created_at
		FROM pre_run_scans
		ORDER BY created_at DESC
		LIMIT 20
	`)
	if err != nil {
		return nil, fmt.Errorf("list pre-run scans: %w", err)
	}
	defer rows.Close()

	var scans []types.PreRunScan
	for rows.Next() {
		var scan types.PreRunScan
		var frameworksRaw, summaryRaw []byte
		if err = rows.Scan(&scan.ScanID, &scan.ProjectPath, &scan.StrictMode, &scan.ReadinessScore, &scan.StrictResult, &frameworksRaw, &summaryRaw, &scan.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan pre-run row: %w", err)
		}
		if err = json.Unmarshal(frameworksRaw, &scan.Frameworks); err != nil {
			return nil, fmt.Errorf("unmarshal pre-run scan frameworks: %w", err)
		}
		if err = json.Unmarshal(summaryRaw, &scan.Summary); err != nil {
			return nil, fmt.Errorf("unmarshal pre-run scan summary: %w", err)
		}
		scans = append(scans, scan)
	}
	return scans, rows.Err()
}

func (s *Store) GetPreRunScan(ctx context.Context, scanID string) (types.PreRunScan, error) {
	var scan types.PreRunScan
	var frameworksRaw, summaryRaw []byte
	err := s.db.QueryRowContext(ctx, `
		SELECT scan_id, project_path, strict_mode, readiness_score, strict_result, frameworks, summary, created_at
		FROM pre_run_scans
		WHERE scan_id = $1
	`, scanID).Scan(&scan.ScanID, &scan.ProjectPath, &scan.StrictMode, &scan.ReadinessScore, &scan.StrictResult, &frameworksRaw, &summaryRaw, &scan.CreatedAt)
	if err != nil {
		return types.PreRunScan{}, fmt.Errorf("get pre-run scan: %w", err)
	}
	if err = json.Unmarshal(frameworksRaw, &scan.Frameworks); err != nil {
		return types.PreRunScan{}, fmt.Errorf("unmarshal pre-run scan frameworks: %w", err)
	}
	if err = json.Unmarshal(summaryRaw, &scan.Summary); err != nil {
		return types.PreRunScan{}, fmt.Errorf("unmarshal pre-run scan summary: %w", err)
	}

	rows, err := s.db.QueryContext(ctx, `
		SELECT id, rule_id, title, severity, status, control_refs, evidence, remediation
		FROM pre_run_findings
		WHERE scan_id = $1
		ORDER BY created_at ASC
	`, scanID)
	if err != nil {
		return types.PreRunScan{}, fmt.Errorf("get pre-run findings: %w", err)
	}
	defer rows.Close()

	for rows.Next() {
		var finding types.PreRunFinding
		var controlRefsRaw, evidenceRaw []byte
		if err = rows.Scan(&finding.ID, &finding.RuleID, &finding.Title, &finding.Severity, &finding.Status, &controlRefsRaw, &evidenceRaw, &finding.Remediation); err != nil {
			return types.PreRunScan{}, fmt.Errorf("scan pre-run finding: %w", err)
		}
		if err = json.Unmarshal(controlRefsRaw, &finding.ControlRefs); err != nil {
			return types.PreRunScan{}, fmt.Errorf("unmarshal pre-run finding control refs: %w", err)
		}
		if err = json.Unmarshal(evidenceRaw, &finding.Evidence); err != nil {
			return types.PreRunScan{}, fmt.Errorf("unmarshal pre-run finding evidence: %w", err)
		}
		scan.Findings = append(scan.Findings, finding)
	}
	return scan, rows.Err()
}

func (s *Store) ListTraces(ctx context.Context) ([]types.TraceSummary, error) {
	rows, err := s.db.QueryContext(ctx, `
		SELECT trace_id, session_id, agent_id, agent_version, framework, model_id, model_provider, model_version,
		       ai_act_risk_tier, use_case_category, environment, overall_risk_score, status, created_at, updated_at, metadata,
		       (SELECT COUNT(*) FROM spans WHERE spans.trace_id = decision_traces.trace_id) AS span_count
		FROM decision_traces
		ORDER BY updated_at DESC
		LIMIT 50
	`)
	if err != nil {
		return nil, fmt.Errorf("list traces: %w", err)
	}
	defer rows.Close()

	var traces []types.TraceSummary
	for rows.Next() {
		var trace types.TraceSummary
		var metadataRaw []byte
		if err = rows.Scan(
			&trace.TraceID, &trace.SessionID, &trace.AgentID, &trace.AgentVersion, &trace.Framework,
			&trace.ModelID, &trace.ModelProvider, &trace.ModelVersion, &trace.AIActRiskTier,
			&trace.UseCaseCategory, &trace.Environment, &trace.OverallRiskScore, &trace.Status,
			&trace.CreatedAt, &trace.UpdatedAt, &metadataRaw, &trace.SpanCount,
		); err != nil {
			return nil, fmt.Errorf("scan trace summary: %w", err)
		}
		if err = json.Unmarshal(metadataRaw, &trace.Metadata); err != nil {
			return nil, fmt.Errorf("unmarshal trace metadata: %w", err)
		}
		traces = append(traces, trace)
	}
	return traces, rows.Err()
}

func (s *Store) GetTraceDetail(ctx context.Context, traceID string) (types.TraceDetail, error) {
	var detail types.TraceDetail
	var metadataRaw []byte
	err := s.db.QueryRowContext(ctx, `
		SELECT trace_id, session_id, agent_id, agent_version, framework, model_id, model_provider, model_version,
		       ai_act_risk_tier, use_case_category, environment, overall_risk_score, status, created_at, updated_at, metadata
		FROM decision_traces
		WHERE trace_id = $1
	`, traceID).Scan(
		&detail.Trace.TraceID, &detail.Trace.SessionID, &detail.Trace.AgentID, &detail.Trace.AgentVersion,
		&detail.Trace.Framework, &detail.Trace.ModelID, &detail.Trace.ModelProvider, &detail.Trace.ModelVersion,
		&detail.Trace.AIActRiskTier, &detail.Trace.UseCaseCategory, &detail.Trace.Environment, &detail.Trace.OverallRiskScore,
		&detail.Trace.Status, &detail.Trace.CreatedAt, &detail.Trace.UpdatedAt, &metadataRaw,
	)
	if err != nil {
		return types.TraceDetail{}, fmt.Errorf("get trace: %w", err)
	}
	if err = json.Unmarshal(metadataRaw, &detail.Trace.Metadata); err != nil {
		return types.TraceDetail{}, fmt.Errorf("unmarshal trace metadata: %w", err)
	}

	spanRows, err := s.db.QueryContext(ctx, `
		SELECT span_id, trace_id, parent_span_id, name, event_type, status, start_time, end_time, payload
		FROM spans
		WHERE trace_id = $1
		ORDER BY start_time ASC, created_at ASC
	`, traceID)
	if err != nil {
		return types.TraceDetail{}, fmt.Errorf("query spans: %w", err)
	}
	defer spanRows.Close()

	for spanRows.Next() {
		var span types.Span
		var payloadRaw []byte
		if err = spanRows.Scan(&span.SpanID, &span.TraceID, &span.ParentSpanID, &span.Name, &span.EventType, &span.Status, &span.StartTime, &span.EndTime, &payloadRaw); err != nil {
			return types.TraceDetail{}, fmt.Errorf("scan span: %w", err)
		}
		if err = json.Unmarshal(payloadRaw, &span.Payload); err != nil {
			return types.TraceDetail{}, fmt.Errorf("unmarshal span payload: %w", err)
		}
		detail.Spans = append(detail.Spans, span)
	}
	if err = spanRows.Err(); err != nil {
		return types.TraceDetail{}, err
	}

	evidenceRows, err := s.db.QueryContext(ctx, `
		SELECT id, trace_id, span_id, source, field_name, value, previous_hash, payload_hash, chain_hash, signed_chain_hash, created_at
		FROM evidence_records
		WHERE trace_id = $1
		ORDER BY sequence_id ASC
	`, traceID)
	if err != nil {
		return types.TraceDetail{}, fmt.Errorf("query evidence: %w", err)
	}
	defer evidenceRows.Close()

	for evidenceRows.Next() {
		var record types.EvidenceRecord
		var valueRaw []byte
		if err = evidenceRows.Scan(&record.ID, &record.TraceID, &record.SpanID, &record.Source, &record.FieldName, &valueRaw, &record.PreviousHash, &record.PayloadHash, &record.ChainHash, &record.SignedChainHash, &record.CreatedAt); err != nil {
			return types.TraceDetail{}, fmt.Errorf("scan evidence: %w", err)
		}
		if err = json.Unmarshal(valueRaw, &record.Value); err != nil {
			return types.TraceDetail{}, fmt.Errorf("unmarshal evidence value: %w", err)
		}
		detail.Evidence = append(detail.Evidence, record)
	}
	if err = evidenceRows.Err(); err != nil {
		return types.TraceDetail{}, err
	}

	findingRows, err := s.db.QueryContext(ctx, `
		SELECT id, trace_id, span_id, framework, control_id, title, citation, status, severity, priority, reasoning, residual_risk, remediation, observed_evidence, created_at
		FROM control_results
		WHERE trace_id = $1
		ORDER BY severity DESC, framework ASC, control_id ASC
	`, traceID)
	if err != nil {
		return types.TraceDetail{}, fmt.Errorf("query control results: %w", err)
	}
	defer findingRows.Close()

	detail.ControlSummary = map[string]int{
		"Violations": 0,
		"Gaps":       0,
		"Covered":    0,
	}
	for findingRows.Next() {
		var result types.ControlResult
		var evidenceRaw []byte
		if err = findingRows.Scan(&result.ID, &result.TraceID, &result.SpanID, &result.Framework, &result.ControlID, &result.Title, &result.Citation, &result.Status, &result.Severity, &result.Priority, &result.Reasoning, &result.ResidualRisk, &result.Remediation, &evidenceRaw, &result.CreatedAt); err != nil {
			return types.TraceDetail{}, fmt.Errorf("scan control result: %w", err)
		}
		if err = json.Unmarshal(evidenceRaw, &result.ObservedEvidence); err != nil {
			return types.TraceDetail{}, fmt.Errorf("unmarshal control result evidence: %w", err)
		}
		switch result.Status {
		case "VIOLATION":
			detail.ControlSummary["Violations"]++
		case "GAP":
			detail.ControlSummary["Gaps"]++
		case "COVERED":
			detail.ControlSummary["Covered"]++
		}
		detail.Findings = append(detail.Findings, result)
	}
	return detail, findingRows.Err()
}

func (s *Store) ReplaceControlResults(ctx context.Context, traceID string, results []types.ControlResult, overallRisk float64, status string) error {
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("begin control results tx: %w", err)
	}
	defer func() {
		if err != nil {
			_ = tx.Rollback()
		}
	}()

	if _, err = tx.ExecContext(ctx, `DELETE FROM control_results WHERE trace_id = $1`, traceID); err != nil {
		return fmt.Errorf("clear control results: %w", err)
	}

	for _, result := range results {
		if result.ID == "" {
			result.ID = newID("cr")
		}
		if result.TraceID == "" {
			result.TraceID = traceID
		}
		evidenceRaw, marshalErr := json.Marshal(result.ObservedEvidence)
		if marshalErr != nil {
			err = fmt.Errorf("marshal control result evidence: %w", marshalErr)
			return err
		}
		if _, err = tx.ExecContext(ctx, `
			INSERT INTO control_results (
				id, trace_id, span_id, framework, control_id, title, citation,
				status, severity, priority, reasoning, residual_risk, remediation, observed_evidence, created_at
			)
			VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14::jsonb, NOW())
		`, result.ID, result.TraceID, result.SpanID, result.Framework, result.ControlID, result.Title, result.Citation, result.Status, result.Severity, result.Priority, result.Reasoning, result.ResidualRisk, result.Remediation, string(evidenceRaw)); err != nil {
			return fmt.Errorf("insert control result: %w", err)
		}
	}

	if _, err = tx.ExecContext(ctx, `
		UPDATE decision_traces
		SET overall_risk_score = $2, status = $3, updated_at = NOW()
		WHERE trace_id = $1
	`, traceID, overallRisk, status); err != nil {
		return fmt.Errorf("update trace evaluation: %w", err)
	}

	if commitErr := tx.Commit(); commitErr != nil {
		return fmt.Errorf("commit control results: %w", commitErr)
	}
	return nil
}

func (s *Store) MergeTraceMetadata(ctx context.Context, traceID string, metadata map[string]interface{}) error {
	metadataRaw, err := json.Marshal(metadata)
	if err != nil {
		return fmt.Errorf("marshal trace metadata: %w", err)
	}
	_, err = s.db.ExecContext(ctx, `
		UPDATE decision_traces
		SET metadata = metadata || $2::jsonb,
		    updated_at = NOW()
		WHERE trace_id = $1
	`, traceID, string(metadataRaw))
	if err != nil {
		return fmt.Errorf("merge trace metadata: %w", err)
	}
	return nil
}

func (s *Store) CreateShareLink(ctx context.Context, traceID, mode string) (string, error) {
	shareID := newID("share")
	_, err := s.db.ExecContext(ctx, `
		INSERT INTO share_links (id, trace_id, mode, created_at)
		VALUES ($1, $2, $3, NOW())
	`, shareID, traceID, mode)
	if err != nil {
		return "", fmt.Errorf("create share link: %w", err)
	}
	return shareID, nil
}

func (s *Store) GetShareDetail(ctx context.Context, shareID string) (types.ShareDetail, error) {
	var detail types.ShareDetail
	var traceID string
	err := s.db.QueryRowContext(ctx, `
		SELECT id, trace_id, mode
		FROM share_links
		WHERE id = $1
	`, shareID).Scan(&detail.ShareID, &traceID, &detail.Mode)
	if err != nil {
		return types.ShareDetail{}, fmt.Errorf("get share: %w", err)
	}
	traceDetail, err := s.GetTraceDetail(ctx, traceID)
	if err != nil {
		return types.ShareDetail{}, err
	}
	if detail.Mode == "audit_log_only" {
		traceDetail.Findings = nil
		traceDetail.ControlSummary = map[string]int{}
	}
	detail.Trace = traceDetail
	detail.ReadOnly = true
	return detail, nil
}

func (s *Store) SeedUser(ctx context.Context, email, password string) error {
	if email == "" || password == "" {
		return nil
	}
	var existing string
	err := s.db.QueryRowContext(ctx, `SELECT id FROM users WHERE email = $1`, email).Scan(&existing)
	if err == nil {
		return nil
	}
	if err != sql.ErrNoRows {
		return fmt.Errorf("lookup user: %w", err)
	}
	passwordHash, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	if err != nil {
		return fmt.Errorf("hash password: %w", err)
	}
	_, err = s.db.ExecContext(ctx, `
		INSERT INTO users (id, email, password_hash, role, created_at)
		VALUES ($1, $2, $3, 'reviewer', NOW())
	`, newID("usr"), email, string(passwordHash))
	if err != nil {
		return fmt.Errorf("insert user: %w", err)
	}
	return nil
}

func (s *Store) AuthenticateUser(ctx context.Context, email, password string) (types.AuthUser, string, error) {
	var user types.AuthUser
	var passwordHash string
	err := s.db.QueryRowContext(ctx, `
		SELECT id, email, role, password_hash
		FROM users
		WHERE email = $1
	`, email).Scan(&user.ID, &user.Email, &user.Role, &passwordHash)
	if err != nil {
		return types.AuthUser{}, "", fmt.Errorf("load user: %w", err)
	}
	if compareErr := bcrypt.CompareHashAndPassword([]byte(passwordHash), []byte(password)); compareErr != nil {
		return types.AuthUser{}, "", fmt.Errorf("invalid credentials")
	}
	token := newID("sess")
	_, err = s.db.ExecContext(ctx, `
		INSERT INTO auth_sessions (token, user_id, created_at, expires_at)
		VALUES ($1, $2, NOW(), NOW() + INTERVAL '24 hours')
	`, token, user.ID)
	if err != nil {
		return types.AuthUser{}, "", fmt.Errorf("insert auth session: %w", err)
	}
	return user, token, nil
}

func (s *Store) ValidateSession(ctx context.Context, token string) (types.AuthUser, error) {
	var user types.AuthUser
	err := s.db.QueryRowContext(ctx, `
		SELECT users.id, users.email, users.role
		FROM auth_sessions
		INNER JOIN users ON users.id = auth_sessions.user_id
		WHERE auth_sessions.token = $1 AND auth_sessions.expires_at > NOW()
	`, token).Scan(&user.ID, &user.Email, &user.Role)
	if err != nil {
		return types.AuthUser{}, fmt.Errorf("validate session: %w", err)
	}
	return user, nil
}

func (s *Store) CountTraces(ctx context.Context) (int, error) {
	var count int
	if err := s.db.QueryRowContext(ctx, `SELECT COUNT(*) FROM decision_traces`).Scan(&count); err != nil {
		return 0, fmt.Errorf("count traces: %w", err)
	}
	return count, nil
}

func (s *Store) CountPreRunScans(ctx context.Context) (int, error) {
	var count int
	if err := s.db.QueryRowContext(ctx, `SELECT COUNT(*) FROM pre_run_scans`).Scan(&count); err != nil {
		return 0, fmt.Errorf("count pre-run scans: %w", err)
	}
	return count, nil
}

func (s *Store) previousChainHash(ctx context.Context, tx *sql.Tx, traceID string) (string, error) {
	var chainHash string
	err := tx.QueryRowContext(ctx, `
		SELECT chain_hash
		FROM evidence_records
		WHERE trace_id = $1
		ORDER BY sequence_id DESC
		LIMIT 1
	`, traceID).Scan(&chainHash)
	if err == sql.ErrNoRows {
		return "", nil
	}
	if err != nil {
		return "", err
	}
	return chainHash, nil
}

func cloneMap(input map[string]interface{}) map[string]interface{} {
	if input == nil {
		return map[string]interface{}{}
	}
	output := make(map[string]interface{}, len(input))
	for key, value := range input {
		output[key] = value
	}
	return output
}

func asString(value interface{}) string {
	switch typed := value.(type) {
	case string:
		return typed
	case fmt.Stringer:
		return typed.String()
	case float64:
		return fmt.Sprintf("%g", typed)
	case int:
		return fmt.Sprintf("%d", typed)
	case bool:
		if typed {
			return "true"
		}
		return "false"
	default:
		return ""
	}
}

func digestJSON(payload map[string]interface{}) string {
	raw, _ := json.Marshal(payload)
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:])
}

func digestString(value string) string {
	sum := sha256.Sum256([]byte(value))
	return hex.EncodeToString(sum[:])
}

func newID(prefix string) string {
	buf := make([]byte, 12)
	_, _ = rand.Read(buf)
	return fmt.Sprintf("%s_%s", prefix, hex.EncodeToString(buf))
}
