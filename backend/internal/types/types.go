package types

import "time"

type RuntimeEvent struct {
	TraceID      string                 `json:"trace_id"`
	SpanID       string                 `json:"span_id"`
	ParentSpanID string                 `json:"parent_span_id"`
	SessionID    string                 `json:"session_id"`
	AgentID      string                 `json:"agent_id"`
	AgentVersion string                 `json:"agent_version"`
	Name         string                 `json:"name"`
	EventType    string                 `json:"event_type"`
	Status       string                 `json:"status"`
	StartTime    time.Time              `json:"start_time"`
	EndTime      time.Time              `json:"end_time"`
	Attributes   map[string]interface{} `json:"attributes"`
}

type PreRunFinding struct {
	ID          string                 `json:"id"`
	RuleID      string                 `json:"rule_id"`
	Title       string                 `json:"title"`
	Severity    string                 `json:"severity"`
	Status      string                 `json:"status"`
	ControlRefs []string               `json:"control_refs"`
	Evidence    map[string]interface{} `json:"evidence"`
	Remediation string                 `json:"remediation"`
}

type PreRunScan struct {
	ScanID         string                 `json:"scan_id"`
	ProjectPath    string                 `json:"project_path"`
	StrictMode     bool                   `json:"strict_mode"`
	ReadinessScore float64                `json:"readiness_score"`
	StrictResult   string                 `json:"strict_result"`
	Frameworks     []string               `json:"frameworks"`
	Summary        map[string]interface{} `json:"summary"`
	Findings       []PreRunFinding        `json:"findings"`
	CreatedAt      time.Time              `json:"created_at"`
}

type TraceSummary struct {
	TraceID          string                 `json:"trace_id"`
	SessionID        string                 `json:"session_id"`
	AgentID          string                 `json:"agent_id"`
	AgentVersion     string                 `json:"agent_version"`
	Framework        string                 `json:"framework"`
	ModelID          string                 `json:"model_id"`
	ModelProvider    string                 `json:"model_provider"`
	ModelVersion     string                 `json:"model_version"`
	AIActRiskTier    string                 `json:"ai_act_risk_tier"`
	UseCaseCategory  string                 `json:"use_case_category"`
	Environment      string                 `json:"environment"`
	OverallRiskScore float64                `json:"overall_risk_score"`
	Status           string                 `json:"status"`
	CreatedAt        time.Time              `json:"created_at"`
	UpdatedAt        time.Time              `json:"updated_at"`
	Metadata         map[string]interface{} `json:"metadata"`
	SpanCount        int                    `json:"span_count"`
}

type Span struct {
	SpanID       string                 `json:"span_id"`
	TraceID      string                 `json:"trace_id"`
	ParentSpanID string                 `json:"parent_span_id"`
	Name         string                 `json:"name"`
	EventType    string                 `json:"event_type"`
	Status       string                 `json:"status"`
	StartTime    time.Time              `json:"start_time"`
	EndTime      time.Time              `json:"end_time"`
	Payload      map[string]interface{} `json:"payload"`
}

type EvidenceRecord struct {
	ID              string                 `json:"id"`
	TraceID         string                 `json:"trace_id"`
	SpanID          string                 `json:"span_id"`
	Source          string                 `json:"source"`
	FieldName       string                 `json:"field_name"`
	Value           map[string]interface{} `json:"value"`
	PreviousHash    string                 `json:"previous_hash"`
	PayloadHash     string                 `json:"payload_hash"`
	ChainHash       string                 `json:"chain_hash"`
	SignedChainHash string                 `json:"signed_chain_hash"`
	CreatedAt       time.Time              `json:"created_at"`
}

type ControlResult struct {
	ID               string                 `json:"id"`
	TraceID          string                 `json:"trace_id"`
	SpanID           string                 `json:"span_id,omitempty"`
	Framework        string                 `json:"framework"`
	ControlID        string                 `json:"control_id"`
	Title            string                 `json:"title"`
	Citation         string                 `json:"citation"`
	Status           string                 `json:"status"`
	Severity         string                 `json:"severity"`
	Priority         string                 `json:"priority"`
	Reasoning        string                 `json:"reasoning"`
	ResidualRisk     string                 `json:"residual_risk"`
	Remediation      string                 `json:"remediation"`
	ObservedEvidence map[string]interface{} `json:"observed_evidence"`
	CreatedAt        time.Time              `json:"created_at"`
}

type TraceDetail struct {
	Trace          TraceSummary     `json:"trace"`
	Spans          []Span           `json:"spans"`
	Evidence       []EvidenceRecord `json:"evidence"`
	Findings       []ControlResult  `json:"findings"`
	ControlSummary map[string]int   `json:"control_summary"`
}

type AuthUser struct {
	ID    string `json:"id"`
	Email string `json:"email"`
	Role  string `json:"role"`
}

type ShareDetail struct {
	ShareID  string      `json:"share_id"`
	Mode     string      `json:"mode"`
	Trace    TraceDetail `json:"trace"`
	ReadOnly bool        `json:"read_only"`
}
