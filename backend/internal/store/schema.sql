CREATE TABLE IF NOT EXISTS decision_traces (
    trace_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL DEFAULT '',
    agent_id TEXT NOT NULL DEFAULT '',
    agent_version TEXT NOT NULL DEFAULT '',
    framework TEXT NOT NULL DEFAULT '',
    model_id TEXT NOT NULL DEFAULT '',
    model_provider TEXT NOT NULL DEFAULT '',
    model_version TEXT NOT NULL DEFAULT '',
    ai_act_risk_tier TEXT NOT NULL DEFAULT '',
    use_case_category TEXT NOT NULL DEFAULT '',
    environment TEXT NOT NULL DEFAULT '',
    overall_risk_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'OPEN',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS spans (
    span_id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL REFERENCES decision_traces(trace_id) ON DELETE CASCADE,
    parent_span_id TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS spans_trace_idx ON spans(trace_id);
CREATE INDEX IF NOT EXISTS spans_parent_idx ON spans(parent_span_id);

CREATE TABLE IF NOT EXISTS evidence_records (
    id TEXT PRIMARY KEY,
    sequence_id BIGSERIAL UNIQUE,
    trace_id TEXT NOT NULL REFERENCES decision_traces(trace_id) ON DELETE CASCADE,
    span_id TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    field_name TEXT NOT NULL DEFAULT '',
    value JSONB NOT NULL DEFAULT '{}'::jsonb,
    previous_hash TEXT NOT NULL DEFAULT '',
    payload_hash TEXT NOT NULL DEFAULT '',
    chain_hash TEXT NOT NULL DEFAULT '',
    signed_chain_hash TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS evidence_trace_idx ON evidence_records(trace_id, created_at);
ALTER TABLE IF EXISTS evidence_records ADD COLUMN IF NOT EXISTS sequence_id BIGSERIAL;
CREATE INDEX IF NOT EXISTS evidence_trace_sequence_idx ON evidence_records(trace_id, sequence_id);

CREATE TABLE IF NOT EXISTS control_results (
    id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL REFERENCES decision_traces(trace_id) ON DELETE CASCADE,
    span_id TEXT NOT NULL DEFAULT '',
    framework TEXT NOT NULL DEFAULT '',
    control_id TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    citation TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    severity TEXT NOT NULL DEFAULT '',
    priority TEXT NOT NULL DEFAULT '',
    reasoning TEXT NOT NULL DEFAULT '',
    residual_risk TEXT NOT NULL DEFAULT '',
    remediation TEXT NOT NULL DEFAULT '',
    observed_evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS control_results_trace_idx ON control_results(trace_id);
CREATE INDEX IF NOT EXISTS control_results_framework_idx ON control_results(framework);

CREATE TABLE IF NOT EXISTS pre_run_scans (
    scan_id TEXT PRIMARY KEY,
    project_path TEXT NOT NULL DEFAULT '',
    strict_mode BOOLEAN NOT NULL DEFAULT FALSE,
    readiness_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    strict_result TEXT NOT NULL DEFAULT 'advisory',
    frameworks JSONB NOT NULL DEFAULT '[]'::jsonb,
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pre_run_findings (
    id TEXT PRIMARY KEY,
    scan_id TEXT NOT NULL REFERENCES pre_run_scans(scan_id) ON DELETE CASCADE,
    rule_id TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    severity TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    control_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    remediation TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS pre_run_findings_scan_idx ON pre_run_findings(scan_id);

CREATE TABLE IF NOT EXISTS share_links (
    id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL REFERENCES decision_traces(trace_id) ON DELETE CASCADE,
    mode TEXT NOT NULL DEFAULT 'audit_log_only',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'reviewer',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS policy_versions (
    id TEXT PRIMARY KEY,
    framework TEXT NOT NULL,
    version TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    controls_count INTEGER NOT NULL DEFAULT 0,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
