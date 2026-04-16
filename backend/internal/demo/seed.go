package demo

import (
	"context"
	"fmt"
	"time"

	"github.com/ajitesh/lookover-codex/backend/internal/evaluator"
	"github.com/ajitesh/lookover-codex/backend/internal/reporting"
	"github.com/ajitesh/lookover-codex/backend/internal/store"
	"github.com/ajitesh/lookover-codex/backend/internal/types"
)

func Seed(ctx context.Context, db *store.Store, engine *evaluator.Engine, reportsDir string) error {
	traceCount, err := db.CountTraces(ctx)
	if err != nil {
		return err
	}
	if traceCount == 0 {
		if err = seedTrace(ctx, db, engine, reportsDir); err != nil {
			return err
		}
	}

	preRunCount, err := db.CountPreRunScans(ctx)
	if err != nil {
		return err
	}
	if preRunCount == 0 {
		if err = seedPreRun(ctx, db); err != nil {
			return err
		}
	}
	return nil
}

func seedTrace(ctx context.Context, db *store.Store, engine *evaluator.Engine, reportsDir string) error {
	traceID := "trace_demo_employment"
	sessionID := "session_demo_20260416"
	base := time.Now().Add(-2 * time.Hour).UTC()

	events := []types.RuntimeEvent{
		{
			TraceID:      traceID,
			SpanID:       "span_start",
			SessionID:    sessionID,
			AgentID:      "hiring-agent",
			AgentVersion: "2026.04.16",
			Name:         "Session Started",
			EventType:    "USER_INTERACTION",
			Status:       "completed",
			StartTime:    base,
			EndTime:      base.Add(5 * time.Second),
			Attributes: map[string]interface{}{
				"framework":                     "langgraph",
				"model_id":                      "gpt-5.4",
				"model_provider":                "openai",
				"model_version":                 "2026-04-01",
				"ai_act_risk_tier":              "high",
				"use_case_category":             "employment",
				"environment":                   "production",
				"lawful_basis":                  "consent",
				"retention_class":               "CRITICAL",
				"privacy_notice_shown":          true,
				"disclosure_shown":              true,
				"override_available":            true,
				"agent_policy_version":          "sec-2026.2",
				"security_policy_ref":           "SEC-POL-12",
				"ai_policy_ref":                 "AI-POL-3",
				"ai_risk_assessment_ref":        "aira-001",
				"ai_risk_assessment_updated_at": base.AddDate(0, -4, 0).Format(time.RFC3339),
				"risk_assessment_ref":           "risk-2025-12",
				"risk_assessment_updated_at":    base.AddDate(0, -5, 0).Format(time.RFC3339),
				"data_sources": []map[string]interface{}{
					{"name": "candidate_profiles", "version": "2026.04", "provenance": "hris"},
				},
				"bias_check_result":              "pass",
				"usage_policy_version":           "u-3.2",
				"health_metrics":                 map[string]interface{}{"signing_queue_depth": 4, "event_ingest_lag_seconds": 1},
				"cloud_security_ref":             "cloud-sec-4",
				"business_continuity_ref":        "bcp-11",
				"vulnerability_scan_ref":         "vas-21",
				"secure_development_ref":         "sdl-8",
				"information_classification":     "confidential",
				"data_encrypted":                 true,
				"encryption_standard":            "AES-256",
				"tls_in_transit":                 true,
				"subject_export_supported":       true,
				"privacy_by_design":              true,
				"agent_registration_ref":         "agent-reg-12",
				"anomaly_monitoring_enabled":     true,
				"tool_provider":                  "internal",
				"tools_declared_scope":           []string{"ats_lookup", "scorecard_write"},
				"tools_invoked_scope":            []string{"ats_lookup", "send_email"},
				"threat_intel_version":           "intel-2026.04",
				"retrieval_source_validated":     true,
				"embedding_provenance":           "text-embedding-4@2026-04-01",
				"system_prompt_hash":             "9f1e5777785e7ec3a0e4",
				"system_prompt_exposed":          false,
				"token_count":                    48000,
				"cost_usd":                       14.2,
				"loop_detected":                  false,
				"accuracy_metric":                0.88,
				"error_rate":                     0.08,
				"grounding_score":                0.73,
				"output_pii_detected":            false,
				"output_secrets_scan":            "pass",
				"output_validation_result":       "pass",
				"data_source_verified":           true,
				"processing_restricted":          false,
				"data_subjects":                  []string{"f3ed720e4f377dd85d5c91f9fc0deefd"},
				"special_category_flag":          false,
				"user_role":                      "reviewer",
				"audit_package_ready":            false,
				"external_audit_package_ready":   false,
				"recovery_procedure_ref":         "recovery-4",
				"availability_checked_at":        base.Format(time.RFC3339),
				"health_status":                  "green",
				"pipeline_status":                "complete",
				"processing_error_count":         0,
				"reviewer_certification_ref":     "cert-hr-22",
				"deployment_approval":            false,
				"consent_ref":                    "",
				"dpia_ref":                       "",
				"transfer_mechanism":             "",
				"data_transfer_destination":      "US",
				"special_category_justification": "",
			},
		},
		{
			TraceID:      traceID,
			SpanID:       "span_model_1",
			ParentSpanID: "span_start",
			SessionID:    sessionID,
			AgentID:      "hiring-agent",
			AgentVersion: "2026.04.16",
			Name:         "Resume Screening",
			EventType:    "MODEL_INFERENCE",
			Status:       "completed",
			StartTime:    base.Add(10 * time.Second),
			EndTime:      base.Add(18 * time.Second),
			Attributes: map[string]interface{}{
				"framework":                "langgraph",
				"injection_scan_result":    0.84,
				"data_fields_accessed":     []string{"email", "salary"},
				"purpose":                  "screen candidates",
				"lawful_basis":             "consent",
				"output_validation_result": "pass",
				"output_pii_detected":      false,
				"output_secrets_scan":      "pass",
				"system_prompt_hash":       "9f1e5777785e7ec3a0e4",
				"system_prompt_exposed":    false,
				"token_count":              22000,
				"cost_usd":                 4.5,
			},
		},
		{
			TraceID:      traceID,
			SpanID:       "span_tool_1",
			ParentSpanID: "span_model_1",
			SessionID:    sessionID,
			AgentID:      "hiring-agent",
			AgentVersion: "2026.04.16",
			Name:         "Write Scorecard",
			EventType:    "TOOL_CALL",
			Status:       "completed",
			StartTime:    base.Add(20 * time.Second),
			EndTime:      base.Add(30 * time.Second),
			Attributes: map[string]interface{}{
				"framework":                "langgraph",
				"tool_name":                "send_email",
				"tools_declared_scope":     []string{"ats_lookup", "scorecard_write"},
				"tools_invoked_scope":      []string{"ats_lookup", "send_email"},
				"output_validation_result": "fail",
				"data_fields_accessed":     []string{"email"},
				"purpose":                  "notify recruiter",
				"lawful_basis":             "consent",
			},
		},
		{
			TraceID:      traceID,
			SpanID:       "span_decision",
			ParentSpanID: "span_model_1",
			SessionID:    sessionID,
			AgentID:      "hiring-agent",
			AgentVersion: "2026.04.16",
			Name:         "Candidate Recommendation",
			EventType:    "DECISION",
			Status:       "completed",
			StartTime:    base.Add(35 * time.Second),
			EndTime:      base.Add(40 * time.Second),
			Attributes: map[string]interface{}{
				"framework":       "langgraph",
				"pii_flags":       true,
				"data_subjects":   []string{"f3ed720e4f377dd85d5c91f9fc0deefd"},
				"grounding_score": 0.54,
			},
		},
		{
			TraceID:      traceID,
			SpanID:       "span_handoff",
			ParentSpanID: "span_decision",
			SessionID:    sessionID,
			AgentID:      "hiring-agent",
			AgentVersion: "2026.04.16",
			Name:         "Human Review",
			EventType:    "HUMAN_HANDOFF",
			Status:       "completed",
			StartTime:    base.Add(45 * time.Second),
			EndTime:      base.Add(52 * time.Second),
			Attributes: map[string]interface{}{
				"framework":                  "langgraph",
				"disclosure_shown":           true,
				"reviewer_certification_ref": "cert-hr-22",
			},
		},
		{
			TraceID:      traceID,
			SpanID:       "span_override",
			ParentSpanID: "span_decision",
			SessionID:    sessionID,
			AgentID:      "hiring-agent",
			AgentVersion: "2026.04.16",
			Name:         "Human Override",
			EventType:    "HUMAN_OVERRIDE",
			Status:       "completed",
			StartTime:    base.Add(58 * time.Second),
			EndTime:      base.Add(59 * time.Second),
			Attributes: map[string]interface{}{
				"framework": "langgraph",
			},
		},
		{
			TraceID:      traceID,
			SpanID:       "span_output",
			ParentSpanID: "span_handoff",
			SessionID:    sessionID,
			AgentID:      "hiring-agent",
			AgentVersion: "2026.04.16",
			Name:         "Final Output",
			EventType:    "OUTPUT",
			Status:       "completed",
			StartTime:    base.Add(65 * time.Second),
			EndTime:      base.Add(66 * time.Second),
			Attributes: map[string]interface{}{
				"framework":                "langgraph",
				"content_type":             "synthetic",
				"output_pii_detected":      false,
				"output_secrets_scan":      "pass",
				"output_validation_result": "pass",
			},
		},
		{
			TraceID:      traceID,
			SpanID:       "span_anomaly",
			ParentSpanID: "span_output",
			SessionID:    sessionID,
			AgentID:      "hiring-agent",
			AgentVersion: "2026.04.16",
			Name:         "Anomaly Detected",
			EventType:    "ANOMALY_DETECTED",
			Status:       "completed",
			StartTime:    base.Add(80 * time.Second),
			EndTime:      base.Add(82 * time.Second),
			Attributes: map[string]interface{}{
				"framework": "langgraph",
			},
		},
	}

	for _, event := range events {
		if err := db.UpsertRuntimeEvent(ctx, event); err != nil {
			return fmt.Errorf("seed runtime event %s: %w", event.SpanID, err)
		}
	}

	detail, err := db.GetTraceDetail(ctx, traceID)
	if err != nil {
		return err
	}
	results, overallRisk := engine.Evaluate(detail)
	if err = db.ReplaceControlResults(ctx, traceID, results, overallRisk, "CLOSED"); err != nil {
		return err
	}

	detail, err = db.GetTraceDetail(ctx, traceID)
	if err != nil {
		return err
	}
	reportPath, err := reporting.WriteTraceReport(reportsDir, detail)
	if err != nil {
		return err
	}

	return db.MergeTraceMetadata(ctx, traceID, map[string]interface{}{
		"ruleset_version":              engine.RulesetVersion(),
		"overall_risk_score":           overallRisk,
		"compliance_trend_score":       overallRisk,
		"audit_package_ready":          true,
		"external_audit_package_ready": true,
		"report_path":                  reportPath,
	})
}

func seedPreRun(ctx context.Context, db *store.Store) error {
	scan := types.PreRunScan{
		ScanID:         "scan_demo_python_langgraph",
		ProjectPath:    "/demo/hiring-agent",
		StrictMode:     true,
		ReadinessScore: 61,
		StrictResult:   "block",
		Frameworks:     []string{"langgraph", "langchain"},
		Summary: map[string]interface{}{
			"project_type":      "langgraph",
			"strict_mode":       true,
			"blocking_findings": 3,
			"advisory_findings": 4,
			"controls_mapped":   19,
		},
		Findings: []types.PreRunFinding{
			{
				ID:          "prf_demo_1",
				RuleID:      "metadata.ai_act_risk_tier",
				Title:       "AI Act risk tier missing from project metadata",
				Severity:    "CRITICAL",
				Status:      "VIOLATION",
				ControlRefs: []string{"EU-AIA-ART6-7-RISK-TIER"},
				Evidence: map[string]interface{}{
					"file":  "agents/hiring_agent.py",
					"field": "ai_act_risk_tier",
				},
				Remediation: "Add explicit AI Act risk tier metadata to the agent config.",
			},
			{
				ID:          "prf_demo_2",
				RuleID:      "privacy.lawful_basis",
				Title:       "Lawful basis missing from data access path",
				Severity:    "CRITICAL",
				Status:      "VIOLATION",
				ControlRefs: []string{"GDPR-ART5-1A-LAWFUL-BASIS", "GDPR-ART6-LAWFUL-BASIS-CONSENT"},
				Evidence: map[string]interface{}{
					"file":  "agents/data_tools.py",
					"field": "lawful_basis",
				},
				Remediation: "Require a lawful basis field in tool configuration before access.",
			},
			{
				ID:          "prf_demo_3",
				RuleID:      "security.output_validation",
				Title:       "Raw model output feeds a tool without validation",
				Severity:    "HIGH",
				Status:      "GAP",
				ControlRefs: []string{"OWASP-LLM05-OUTPUT-HANDLING", "SOC2-CC6-6-SCOPE"},
				Evidence: map[string]interface{}{
					"file":  "graphs/hiring_flow.py",
					"match": "tool.invoke(model_output)",
				},
				Remediation: "Add an output validation and sanitization step before tool invocation.",
			},
		},
	}
	return db.SavePreRunScan(ctx, scan)
}
