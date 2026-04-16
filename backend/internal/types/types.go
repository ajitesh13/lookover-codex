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

type VoiceTranscriptTurn struct {
	Speaker          string  `json:"speaker"`
	Text             string  `json:"text"`
	TimestampSeconds float64 `json:"timestamp_seconds"`
}

type VoiceTimelineEvent struct {
	Event            string  `json:"event"`
	TimestampSeconds float64 `json:"timestamp_seconds"`
}

type VoiceFinding struct {
	Article                        string  `json:"article"`
	Status                         string  `json:"status"`
	Severity                       string  `json:"severity"`
	Reason                         string  `json:"reason"`
	EvidenceSpan                   string  `json:"evidence_span"`
	EvidenceType                   string  `json:"evidence_type"`
	Confidence                     float64 `json:"confidence"`
	ManualReviewRequired           bool    `json:"manual_review_required"`
	LinkedExternalEvidenceRequired bool    `json:"linked_external_evidence_required"`
	Owner                          string  `json:"owner"`
	RemediationDueAt               string  `json:"remediation_due_at"`
}

type VoiceRunCreateRequest struct {
	Transcript                    string `json:"transcript"`
	CallID                        string `json:"call_id"`
	Tenant                        string `json:"tenant"`
	Deployer                      string `json:"deployer"`
	Language                      string `json:"language"`
	AgentVersion                  string `json:"agent_version"`
	PolicyVersion                 string `json:"policy_version"`
	RawAudioURI                   string `json:"raw_audio_uri"`
	SyntheticAudioUsed            bool   `json:"synthetic_audio_used"`
	SyntheticAudioMarked          bool   `json:"synthetic_audio_marked"`
	DeepfakeLikeContentFlag       bool   `json:"deepfake_like_content_flag"`
	EmotionRecognitionUsed        bool   `json:"emotion_recognition_used"`
	BiometricCategorisationUsed   bool   `json:"biometric_categorisation_used"`
	DecisionSupportFlag           bool   `json:"decision_support_flag"`
	HumanOversightPathPresent     bool   `json:"human_oversight_path_present"`
	NoticeToAffectedPersonPresent bool   `json:"notice_to_affected_person_present"`
	HighRiskFlag                  bool   `json:"high_risk_flag"`
}

type VoiceRunQuery struct {
	Query                      string
	Status                     string
	Disposition                string
	Tenant                     string
	Deployer                   string
	Applicability              string
	AIDisclosureStatus         string
	Article                    string
	Severity                   string
	DateFrom                   *time.Time
	DateTo                     *time.Time
	HighRiskFlag               *bool
	EmotionOrBiometricFeatures *bool
	HumanHandoff               *bool
	Page                       int
	PageSize                   int
}

type VoiceRunSummary struct {
	Total       int `json:"total"`
	HardFail    int `json:"hard_fail"`
	NeedsReview int `json:"needs_review"`
	Pass        int `json:"pass"`
}

type VoiceRunRecord struct {
	VoiceRunID                 string                 `json:"voice_run_id"`
	CallID                     string                 `json:"call_id"`
	Tenant                     string                 `json:"tenant"`
	Deployer                   string                 `json:"deployer"`
	Status                     string                 `json:"status"`
	Disposition                string                 `json:"disposition"`
	Applicability              string                 `json:"applicability"`
	AIDisclosureStatus         string                 `json:"ai_disclosure_status"`
	DisclosureTimestamp        *float64               `json:"disclosure_timestamp,omitempty"`
	HighRiskFlag               bool                   `json:"high_risk_flag"`
	EmotionOrBiometricFeatures bool                   `json:"emotion_or_biometric_features"`
	HumanHandoff               bool                   `json:"human_handoff"`
	AgentVersion               string                 `json:"agent_version"`
	PolicyVersion              string                 `json:"policy_version"`
	TranscriptText             string                 `json:"transcript_text"`
	TranscriptTurns            []VoiceTranscriptTurn  `json:"transcript_turns"`
	TranscriptPreview          []VoiceTranscriptTurn  `json:"transcript_preview"`
	Timeline                   []VoiceTimelineEvent   `json:"timeline"`
	Findings                   []VoiceFinding         `json:"findings"`
	FindingCount               int                    `json:"finding_count"`
	FailingFindingCount        int                    `json:"failing_finding_count"`
	NeedsReviewFindingCount    int                    `json:"needs_review_finding_count"`
	Error                      string                 `json:"error"`
	AuditorReport              map[string]interface{} `json:"auditor_report,omitempty"`
	CreatedAt                  time.Time              `json:"created_at"`
	UpdatedAt                  time.Time              `json:"updated_at"`
	AuditedAt                  *time.Time             `json:"audited_at,omitempty"`
}

type VoiceRunListResponse struct {
	Items   []VoiceRunRecord `json:"items"`
	Total   int              `json:"total"`
	Summary VoiceRunSummary  `json:"summary"`
}

type VoiceAuditorComplianceEvidence struct {
	AIDisclosureStatus          string   `json:"ai_disclosure_status"`
	DisclosureTimestamp         *float64 `json:"disclosure_timestamp"`
	EmotionRecognitionUsed      bool     `json:"emotion_recognition_used"`
	BiometricCategorisationUsed bool     `json:"biometric_categorisation_used"`
	HumanOversightPathPresent   bool     `json:"human_oversight_path_present"`
	HighRiskFlag                bool     `json:"high_risk_flag"`
}

type VoiceAuditorRecord struct {
	CallID             string                         `json:"call_id"`
	Tenant             string                         `json:"tenant"`
	Deployer           string                         `json:"deployer"`
	AgentVersion       string                         `json:"agent_version"`
	PolicyVersion      string                         `json:"policy_version"`
	TranscriptTurns    []VoiceTranscriptTurn          `json:"transcript_turns"`
	EventTimeline      []VoiceTimelineEvent           `json:"event_timeline"`
	Findings           []VoiceFinding                 `json:"findings"`
	ComplianceEvidence VoiceAuditorComplianceEvidence `json:"compliance_evidence"`
	Applicability      string                         `json:"applicability"`
	Disposition        string                         `json:"disposition"`
}

type VoiceAuditorResponse struct {
	Record          VoiceAuditorRecord    `json:"record"`
	TranscriptTurns []VoiceTranscriptTurn `json:"transcript_turns"`
}
