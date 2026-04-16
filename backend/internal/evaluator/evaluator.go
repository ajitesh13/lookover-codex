package evaluator

import (
	"fmt"
	"math"
	"strings"
	"time"

	"github.com/ajitesh/lookover-codex/backend/internal/controls"
	"github.com/ajitesh/lookover-codex/backend/internal/types"
)

type Engine struct {
	manifests      []controls.Manifest
	rulesetVersion string
}

type outcome struct {
	status       string
	reasoning    string
	spanID       string
	evidence     map[string]interface{}
	residualRisk string
}

func New(manifests []controls.Manifest) *Engine {
	parts := make([]string, 0, len(manifests))
	for _, manifest := range manifests {
		parts = append(parts, fmt.Sprintf("%s:v%d", manifest.Framework, manifest.Version))
	}
	return &Engine{
		manifests:      manifests,
		rulesetVersion: strings.Join(parts, "|"),
	}
}

func (e *Engine) RulesetVersion() string {
	return e.rulesetVersion
}

func (e *Engine) Evaluate(detail types.TraceDetail) ([]types.ControlResult, float64) {
	if detail.Trace.Metadata == nil {
		detail.Trace.Metadata = map[string]interface{}{}
	}
	detail.Trace.Metadata["ruleset_version"] = e.rulesetVersion

	results := e.evaluateOnce(detail)
	overallRisk := e.computeOverallRisk(results)
	detail.Trace.Metadata["overall_risk_score"] = overallRisk
	detail.Trace.Metadata["compliance_trend_score"] = overallRisk
	detail.Trace.OverallRiskScore = overallRisk

	secondPass := e.evaluateOnce(detail)
	replacements := map[string]types.ControlResult{}
	for _, result := range secondPass {
		if derivedScoreControl(result.ControlID) {
			replacements[result.Framework+"|"+result.ControlID] = result
		}
	}
	for index, result := range results {
		if replacement, ok := replacements[result.Framework+"|"+result.ControlID]; ok {
			results[index] = replacement
		}
	}
	return results, overallRisk
}

func (e *Engine) evaluateOnce(detail types.TraceDetail) []types.ControlResult {
	results := make([]types.ControlResult, 0, 64)
	for _, manifest := range e.manifests {
		for _, control := range manifest.Controls {
			if !controlApplies(control, detail) {
				results = append(results, e.toResult(manifest.Framework, control, outcome{
					status:       "NOT_APPLICABLE",
					reasoning:    "Control applicability conditions did not match this trace.",
					evidence:     map[string]interface{}{},
					residualRisk: "No direct obligation was triggered for this trace.",
				}))
				continue
			}

			current := e.runEvaluator(control, detail)
			results = append(results, e.toResult(manifest.Framework, control, current))
		}
	}
	return results
}

func controlApplies(control controls.Control, detail types.TraceDetail) bool {
	if len(control.AppliesTo.RiskTiers) > 0 && !containsAny(control.AppliesTo.RiskTiers, detail.Trace.AIActRiskTier) {
		return false
	}
	if len(control.AppliesTo.EventTypes) > 0 && len(matchingSpans(detail, control.AppliesTo.EventTypes)) == 0 {
		return false
	}
	return true
}

func derivedScoreControl(controlID string) bool {
	switch controlID {
	case "SOC2-CC9-1-RISK-SCORE", "SOC2-P8-1-ENFORCEMENT", "ISO42001-9-1-MONITORING":
		return true
	default:
		return false
	}
}

func (e *Engine) runEvaluator(control controls.Control, detail types.TraceDetail) outcome {
	params := control.Evaluator.Params
	switch control.Evaluator.Kind {
	case "non_empty_field":
		return e.evalNonEmptyField(detail, paramsString(params, "field"))
	case "enum_field":
		return e.evalEnumField(detail, paramsString(params, "field"), paramsStringSlice(params, "allowed"))
	case "annex_category_requires_high_risk":
		return e.evalAnnexCategory(detail, paramsString(params, "field"), paramsStringSlice(params, "annex_categories"))
	case "timestamp_age_max_days":
		field := paramsString(params, "field")
		maxDays, _ := paramsInt(params, "max_days")
		return e.evalTimestampAge(detail, field, maxDays)
	case "approval_before_first_production_event":
		return e.evalApprovalBeforeProduction(detail, paramsString(params, "approval_event_type"), paramsString(params, "production_field"), paramsString(params, "production_value"))
	case "structured_sources_present":
		return e.evalStructuredSources(detail, paramsString(params, "field"), paramsStringSlice(params, "required_keys"))
	case "field_equals":
		return e.evalFieldEquals(findAny(detail, paramsString(params, "field")), paramsString(params, "field"), params["value"])
	case "fields_present_on_every_event":
		return e.evalFieldsPresentOnEveryEvent(detail, paramsStringSlice(params, "fields"))
	case "trace_gap_and_chain":
		maxGap, _ := paramsInt(params, "max_gap_seconds")
		return e.evalTraceGapAndChain(detail, maxGap)
	case "trace_session_fields":
		return e.evalTraceSessionFields(detail, paramsStringSlice(params, "fields"))
	case "retention_policy":
		return e.evalRetention(detail, paramsString(params, "field"))
	case "boolean_true_on_event_types":
		return e.evalBooleanTrueOnEventTypes(detail, paramsString(params, "field"), paramsStringSlice(params, "event_types"))
	case "event_exists_per_session":
		return e.evalEventExists(detail, paramsString(params, "event_type"))
	case "field_present_on_matching_events":
		return e.evalFieldPresentOnEvents(detail, paramsString(params, "field"), paramsStringSlice(params, "event_types"))
	case "flag_and_event_for_version":
		return e.evalFlagAndEvent(detail, paramsString(params, "flag"), paramsString(params, "event_type"))
	case "metric_threshold":
		return e.evalMetricThreshold(detail, params)
	case "model_inference_scan":
		maxScore, _ := paramsFloat(params, "max_score")
		return e.evalModelScan(detail, paramsString(params, "field"), maxScore)
	case "followup_event_within_sla":
		hours, _ := paramsInt(params, "hours")
		return e.evalFollowupEvent(detail, paramsString(params, "source_event_type"), paramsString(params, "followup_event_type"), hours)
	case "synthetic_output_flagged":
		return e.evalSyntheticOutput(detail, paramsString(params, "field"), paramsString(params, "value"))
	case "enum_field_on_personal_data_events":
		return e.evalEnumOnPersonalData(detail, paramsString(params, "field"), paramsStringSlice(params, "allowed"))
	case "non_empty_field_on_personal_data_events":
		return e.evalNonEmptyOnPersonalData(detail, paramsString(params, "field"))
	case "pii_access_requires_purpose_justification":
		return e.evalPIIAccess(detail, paramsStringSlice(params, "pii_fields"))
	case "field_equals_on_event_types":
		return e.evalFieldEqualsOnEventTypes(detail, paramsString(params, "field"), params["value"], paramsStringSlice(params, "event_types"))
	case "deletion_schedule_for_personal_data":
		return e.evalDeletionSchedule(detail, paramsString(params, "deletion_field"))
	case "encryption_and_chain":
		return e.evalEncryptionAndChain(detail, paramsString(params, "encryption_field"))
	case "conditional_required_field":
		return e.evalConditionalRequiredField(detail, paramsString(params, "if_field"), paramsString(params, "equals"), paramsString(params, "required_field"))
	case "reference_resolves":
		return e.evalReference(detail, paramsString(params, "field"), paramsString(params, "prefix"))
	case "special_category_requires_justification":
		return e.evalSpecialCategory(detail, paramsString(params, "flag_field"), paramsString(params, "justification_field"))
	case "first_session_notice":
		return e.evalFirstSessionNotice(detail, paramsString(params, "field"))
	case "indirect_source_disclosure":
		maxDays, _ := paramsInt(params, "max_days")
		return e.evalIndirectDisclosure(detail, paramsString(params, "field"), maxDays)
	case "request_completed_within_days":
		maxDays, _ := paramsInt(params, "max_days")
		return e.evalRequestSLA(detail, paramsString(params, "requested_field"), paramsString(params, "completed_field"), maxDays)
	case "request_event_followed_by_action":
		return e.evalRequestEventFollowed(detail, paramsString(params, "request_event_type"), paramsString(params, "action_event_type"))
	case "objection_halts_processing":
		maxHours, _ := paramsInt(params, "max_hours")
		return e.evalObjectionHalts(detail, paramsString(params, "objection_event_type"), maxHours)
	case "hashed_identifier_list":
		minLength, _ := paramsInt(params, "min_length")
		return e.evalHashedIdentifiers(detail, paramsString(params, "field"), minLength)
	case "restricted_subject_not_used_in_decision":
		return e.evalRestrictedSubjects(detail, paramsString(params, "restriction_field"))
	case "automated_decision_requires_handoff":
		return e.evalAutomatedDecision(detail, paramsString(params, "decision_event_type"), paramsString(params, "handoff_event_type"))
	case "records_of_processing_complete":
		return e.evalProcessingRecords(detail, params)
	case "field_set_and_true":
		return e.evalFieldSetAndTrue(detail, paramsString(params, "string_field"), paramsString(params, "bool_field"))
	case "non_eea_requires_field":
		return e.evalTransfer(detail, paramsString(params, "country_field"), paramsString(params, "required_field"))
	case "health_metrics_within_threshold":
		return e.evalHealthMetrics(detail, params["metrics"])
	case "rbac_enforced":
		return e.evalRBAC(detail, paramsString(params, "role_field"), paramsString(params, "forbidden_event_type"))
	case "subset_field":
		return e.evalSubset(detail, paramsString(params, "superset_field"), paramsString(params, "subset_field"))
	case "hash_chain_valid":
		return e.evalHashChain(detail)
	case "version_change_logged":
		return e.evalVersionChange(detail, paramsString(params, "change_event_type"))
	case "provider_fields_present":
		return e.evalProviderFields(detail, paramsStringSlice(params, "fields"))
	case "non_empty_fields":
		return e.evalNonEmptyFields(detail, paramsStringSlice(params, "fields"))
	case "output_safety_scan":
		return e.evalOutputSafety(detail, paramsString(params, "pii_field"), paramsString(params, "scan_field"))
	case "providers_pinned":
		return e.evalProvidersPinned(detail, paramsStringSlice(params, "fields"))
	case "system_prompt_protected":
		return e.evalSystemPrompt(detail, paramsString(params, "hash_field"), paramsString(params, "exposed_field"))
	case "bounded_consumption":
		maxTokens, _ := paramsInt(params, "max_tokens")
		maxCost, _ := paramsFloat(params, "max_cost_usd")
		return e.evalBoundedConsumption(detail, maxTokens, maxCost)
	case "combined_disclosure_check":
		return e.evalCombinedDisclosure(detail, paramsString(params, "ai_field"), paramsString(params, "capability_event_type"))
	default:
		return outcome{
			status:       "GAP",
			reasoning:    fmt.Sprintf("Unsupported evaluator kind `%s` is not implemented yet.", control.Evaluator.Kind),
			evidence:     map[string]interface{}{"evaluator": control.Evaluator.Kind},
			residualRisk: "The control cannot be proven until the evaluator is implemented.",
		}
	}
}

func (e *Engine) toResult(framework string, control controls.Control, current outcome) types.ControlResult {
	return types.ControlResult{
		ID:               "",
		Framework:        framework,
		ControlID:        control.ID,
		Title:            control.Title,
		Citation:         control.Citation,
		Status:           current.status,
		Severity:         control.Severity,
		Priority:         control.Priority,
		Reasoning:        current.reasoning,
		ResidualRisk:     current.residualRisk,
		Remediation:      control.Remediation,
		ObservedEvidence: current.evidence,
		SpanID:           current.spanID,
	}
}

func (e *Engine) computeOverallRisk(results []types.ControlResult) float64 {
	totalWeight := 0.0
	score := 0.0
	owaspScore := 0.0

	for _, result := range results {
		if result.Status == "NOT_APPLICABLE" {
			continue
		}
		weight := severityWeight(result.Severity)
		totalWeight += weight
		switch result.Status {
		case "VIOLATION":
			score += weight
		case "GAP":
			score += weight * 0.5
		}

		if result.Framework == "OWASP_LLM_TOP_10_2025" && result.Status != "NOT_APPLICABLE" {
			threatWeight := owaspWeight(result.ControlID)
			detection := 0.0
			if result.Status == "VIOLATION" {
				detection = 1.0
			} else if result.Status == "GAP" {
				detection = 0.5
			}
			frequency := 0.1
			if count, ok := asFloat(result.ObservedEvidence["matched_count"]); ok {
				frequency = math.Min(1, count/10)
			}
			owaspScore += threatWeight * detection * frequency
		}
	}

	if totalWeight == 0 {
		return 0
	}
	base := score / totalWeight
	return math.Max(base, math.Min(1, owaspScore))
}

func severityWeight(severity string) float64 {
	switch strings.ToUpper(severity) {
	case "CRITICAL":
		return 1.0
	case "HIGH":
		return 0.7
	case "MEDIUM":
		return 0.4
	default:
		return 0.2
	}
}

func owaspWeight(controlID string) float64 {
	switch {
	case strings.Contains(controlID, "LLM01"), strings.Contains(controlID, "LLM02"), strings.Contains(controlID, "LLM05"), strings.Contains(controlID, "LLM06"):
		return 1.0
	case strings.Contains(controlID, "LLM03"), strings.Contains(controlID, "LLM04"), strings.Contains(controlID, "LLM07"), strings.Contains(controlID, "LLM08"):
		return 0.7
	case strings.Contains(controlID, "LLM10"):
		return 0.6
	default:
		return 0.4
	}
}

func covered(reasoning string, evidence map[string]interface{}, spanID string) outcome {
	return outcome{
		status:       "COVERED",
		reasoning:    reasoning,
		spanID:       spanID,
		evidence:     evidence,
		residualRisk: "Control is evidenced for this trace, but ongoing monitoring remains necessary.",
	}
}

func gap(reasoning string, evidence map[string]interface{}, spanID string) outcome {
	return outcome{
		status:       "GAP",
		reasoning:    reasoning,
		spanID:       spanID,
		evidence:     evidence,
		residualRisk: "Evidence is missing, stale, or incomplete, so compliance cannot be fully proven.",
	}
}

func violation(reasoning string, evidence map[string]interface{}, spanID string) outcome {
	return outcome{
		status:       "VIOLATION",
		reasoning:    reasoning,
		spanID:       spanID,
		evidence:     evidence,
		residualRisk: "Evidence indicates active non-compliance or a forbidden operating condition.",
	}
}

func notApplicable(reasoning string) outcome {
	return outcome{
		status:       "NOT_APPLICABLE",
		reasoning:    reasoning,
		evidence:     map[string]interface{}{},
		residualRisk: "The control did not apply to this trace.",
	}
}

func (e *Engine) evalNonEmptyField(detail types.TraceDetail, field string) outcome {
	value := findAny(detail, field)
	if isEmpty(value) {
		return gap(fmt.Sprintf("Field `%s` is missing.", field), map[string]interface{}{"field": field}, "")
	}
	return covered(fmt.Sprintf("Field `%s` is present.", field), map[string]interface{}{"field": field, "value": value}, "")
}

func (e *Engine) evalEnumField(detail types.TraceDetail, field string, allowed []string) outcome {
	value := nonEmptyString(findAny(detail, field))
	if value == "" {
		return gap(fmt.Sprintf("Field `%s` is missing.", field), map[string]interface{}{"field": field}, "")
	}
	if !containsAny(allowed, value) {
		return violation(fmt.Sprintf("Field `%s` has invalid value `%s`.", field, value), map[string]interface{}{"field": field, "value": value, "allowed": allowed}, "")
	}
	return covered(fmt.Sprintf("Field `%s` is present with allowed value `%s`.", field, value), map[string]interface{}{"field": field, "value": value}, "")
}

func (e *Engine) evalAnnexCategory(detail types.TraceDetail, field string, annexCategories []string) outcome {
	category := nonEmptyString(findAny(detail, field))
	if category == "" {
		return gap("Use case category is missing.", map[string]interface{}{"field": field}, "")
	}
	if !containsAny(annexCategories, category) {
		return notApplicable("The declared use case category does not map to an Annex III high-risk category.")
	}
	if strings.EqualFold(detail.Trace.AIActRiskTier, "high") {
		return covered("Annex III category is present and the agent is classified as high risk.", map[string]interface{}{"use_case_category": category, "ai_act_risk_tier": detail.Trace.AIActRiskTier}, "")
	}
	return violation("Annex III category was detected but the trace is not classified as high risk.", map[string]interface{}{"use_case_category": category, "ai_act_risk_tier": detail.Trace.AIActRiskTier}, "")
}

func (e *Engine) evalTimestampAge(detail types.TraceDetail, field string, maxDays int) outcome {
	value := findAny(detail, field)
	parsed, ok := asTime(value)
	if !ok {
		return gap(fmt.Sprintf("Timestamp field `%s` is missing or invalid.", field), map[string]interface{}{"field": field, "value": value}, "")
	}
	ageDays := int(time.Since(parsed).Hours() / 24)
	if ageDays > maxDays {
		return gap(fmt.Sprintf("Timestamp `%s` is stale at %d days old.", field, ageDays), map[string]interface{}{"field": field, "timestamp": parsed, "age_days": ageDays}, "")
	}
	return covered(fmt.Sprintf("Timestamp `%s` is current at %d days old.", field, ageDays), map[string]interface{}{"field": field, "timestamp": parsed, "age_days": ageDays}, "")
}

func (e *Engine) evalApprovalBeforeProduction(detail types.TraceDetail, approvalEventType, productionField, productionValue string) outcome {
	productionTime := time.Time{}
	for _, span := range detail.Spans {
		if strings.EqualFold(nonEmptyString(spanField(span, productionField)), productionValue) || strings.EqualFold(detail.Trace.Environment, productionValue) {
			if productionTime.IsZero() || span.StartTime.Before(productionTime) {
				productionTime = span.StartTime
			}
		}
	}
	if productionTime.IsZero() {
		return notApplicable("No production activity was detected in this trace.")
	}
	for _, span := range detail.Spans {
		if span.EventType == approvalEventType && !span.StartTime.After(productionTime) {
			approvedAt := span.Payload["approved_at"]
			if isEmpty(approvedAt) {
				approvedAt = span.Payload["start_time"]
			}
			approvedBy := span.Payload["approved_by"]
			if isEmpty(approvedBy) {
				approvedBy = span.Payload["human_reviewer_id"]
			}
			if isEmpty(approvedAt) || isEmpty(approvedBy) {
				return gap("Deployment approval event exists but sign-off identity or timestamp is incomplete.", map[string]interface{}{"approval_span_id": span.SpanID, "approved_at": approvedAt, "approved_by": approvedBy, "production_started_at": productionTime}, span.SpanID)
			}
			return covered("A deployment approval event with human sign-off occurred before production activity.", map[string]interface{}{"approval_span_id": span.SpanID, "approved_at": approvedAt, "approved_by": approvedBy, "production_started_at": productionTime}, span.SpanID)
		}
	}
	return violation("Production activity began before a deployment approval event was recorded.", map[string]interface{}{"production_started_at": productionTime}, "")
}

func (e *Engine) evalStructuredSources(detail types.TraceDetail, field string, requiredKeys []string) outcome {
	sources := asMapSlice(findAny(detail, field))
	if len(sources) == 0 {
		return gap(fmt.Sprintf("Structured `%s` evidence is missing.", field), map[string]interface{}{"field": field}, "")
	}
	for _, source := range sources {
		for _, key := range requiredKeys {
			if isEmpty(source[key]) {
				return gap("At least one data source is missing required provenance keys.", map[string]interface{}{"field": field, "missing_key": key, "source": source}, "")
			}
		}
	}
	return covered("Data sources include the required provenance metadata.", map[string]interface{}{"field": field, "count": len(sources)}, "")
}

func (e *Engine) evalFieldEquals(value interface{}, field string, expected interface{}) outcome {
	actual := nonEmptyString(value)
	if actual == "" {
		return gap(fmt.Sprintf("Field `%s` is missing.", field), map[string]interface{}{"field": field}, "")
	}
	expectedString := nonEmptyString(expected)
	if expectedString == "" && expected != nil {
		expectedString = fmt.Sprintf("%v", expected)
	}
	if !strings.EqualFold(actual, expectedString) {
		return violation(fmt.Sprintf("Field `%s` is `%s` instead of `%s`.", field, actual, expectedString), map[string]interface{}{"field": field, "value": actual, "expected": expectedString}, "")
	}
	return covered(fmt.Sprintf("Field `%s` matches `%s`.", field, expectedString), map[string]interface{}{"field": field, "value": actual}, "")
}

func (e *Engine) evalFieldsPresentOnEveryEvent(detail types.TraceDetail, fields []string) outcome {
	if len(detail.Spans) == 0 {
		return gap("No spans were recorded for this trace.", map[string]interface{}{}, "")
	}
	for _, span := range detail.Spans {
		for _, field := range fields {
			if isEmpty(span.Payload[field]) {
				return gap("At least one required field is missing on a runtime event.", map[string]interface{}{"span_id": span.SpanID, "missing_field": field}, span.SpanID)
			}
		}
	}
	return covered("All required fields are present on every runtime event.", map[string]interface{}{"fields": fields, "matched_count": len(detail.Spans)}, "")
}

func (e *Engine) evalTraceGapAndChain(detail types.TraceDetail, maxGapSeconds int) outcome {
	if len(detail.Evidence) == 0 || len(detail.Spans) == 0 {
		return gap("Trace evidence or spans are missing, so continuity cannot be proven.", map[string]interface{}{}, "")
	}
	for index := 1; index < len(detail.Spans); index++ {
		gapDuration := detail.Spans[index].StartTime.Sub(detail.Spans[index-1].EndTime)
		if gapDuration > time.Duration(maxGapSeconds)*time.Second {
			return violation("Trace contains an unexplained logging gap beyond the allowed threshold.", map[string]interface{}{"previous_span_id": detail.Spans[index-1].SpanID, "next_span_id": detail.Spans[index].SpanID, "gap_seconds": gapDuration.Seconds()}, detail.Spans[index].SpanID)
		}
	}
	return e.evalHashChain(detail)
}

func (e *Engine) evalTraceSessionFields(detail types.TraceDetail, fields []string) outcome {
	for _, field := range fields {
		if isEmpty(findAny(detail, field)) {
			return gap("Trace-level session fields are incomplete.", map[string]interface{}{"missing_field": field}, "")
		}
	}
	if len(detail.Spans) > 0 && detail.Spans[len(detail.Spans)-1].EndTime.Before(detail.Spans[0].StartTime) {
		return violation("Trace timestamps are internally inconsistent.", map[string]interface{}{"first_start": detail.Spans[0].StartTime, "last_end": detail.Spans[len(detail.Spans)-1].EndTime}, "")
	}
	return covered("Session identity and timing fields are present and traceable.", map[string]interface{}{"fields": fields}, "")
}

func (e *Engine) evalRetention(detail types.TraceDetail, field string) outcome {
	retentionClass := strings.ToUpper(nonEmptyString(findAny(detail, field)))
	if retentionClass == "" {
		return gap("Retention class is missing.", map[string]interface{}{"field": field}, "")
	}
	if retentionClass != "CRITICAL" {
		return covered("Retention class is declared for the trace.", map[string]interface{}{"retention_class": retentionClass}, "")
	}
	deletionAt, ok := asTime(findAny(detail, "scheduled_deletion_at"))
	if !ok {
		return gap("Critical retention is declared without a scheduled deletion or retention horizon.", map[string]interface{}{"retention_class": retentionClass}, "")
	}
	if deletionAt.Sub(time.Now()).Hours() < (24 * 365 * 5) {
		return violation("Critical retention does not preserve records for five years.", map[string]interface{}{"retention_class": retentionClass, "scheduled_deletion_at": deletionAt}, "")
	}
	return covered("Critical retention horizon meets the five-year minimum.", map[string]interface{}{"retention_class": retentionClass, "scheduled_deletion_at": deletionAt}, "")
}

func (e *Engine) evalBooleanTrueOnEventTypes(detail types.TraceDetail, field string, eventTypes []string) outcome {
	spans := matchingSpans(detail, eventTypes)
	if len(spans) == 0 {
		return notApplicable("No matching event types were present for this disclosure control.")
	}
	for _, span := range spans {
		value := span.Payload[field]
		if isEmpty(value) {
			return gap(fmt.Sprintf("Field `%s` is missing on a matching event.", field), map[string]interface{}{"span_id": span.SpanID, "event_type": span.EventType}, span.SpanID)
		}
		if !asBool(value) {
			return violation(fmt.Sprintf("Field `%s` is false on a matching event.", field), map[string]interface{}{"span_id": span.SpanID, "event_type": span.EventType, "value": value}, span.SpanID)
		}
	}
	return covered(fmt.Sprintf("Field `%s` is true on all matching events.", field), map[string]interface{}{"field": field, "matched_count": len(spans)}, "")
}

func (e *Engine) evalEventExists(detail types.TraceDetail, eventType string) outcome {
	if isEmpty(detail.Trace.SessionID) {
		return gap("Session context is missing, so per-session evidence cannot be proven.", map[string]interface{}{"event_type": eventType}, "")
	}
	spans := matchingSpans(detail, []string{eventType})
	if len(spans) == 0 {
		return gap(fmt.Sprintf("No `%s` event was recorded.", eventType), map[string]interface{}{"event_type": eventType}, "")
	}
	return covered(fmt.Sprintf("At least one `%s` event was recorded.", eventType), map[string]interface{}{"event_type": eventType, "matched_count": len(spans)}, spans[0].SpanID)
}

func (e *Engine) evalFieldPresentOnEvents(detail types.TraceDetail, field string, eventTypes []string) outcome {
	spans := matchingSpans(detail, eventTypes)
	if len(spans) == 0 {
		return notApplicable("No matching event types were present.")
	}
	for _, span := range spans {
		if isEmpty(span.Payload[field]) {
			return gap(fmt.Sprintf("Field `%s` is missing on a required event.", field), map[string]interface{}{"field": field, "span_id": span.SpanID, "event_type": span.EventType}, span.SpanID)
		}
	}
	return covered(fmt.Sprintf("Field `%s` is present on all matching events.", field), map[string]interface{}{"field": field, "matched_count": len(spans)}, "")
}

func (e *Engine) evalFlagAndEvent(detail types.TraceDetail, flagField, eventType string) outcome {
	flagValue := findAny(detail, flagField)
	if isEmpty(flagValue) {
		return gap(fmt.Sprintf("Flag `%s` is missing.", flagField), map[string]interface{}{"flag": flagField}, "")
	}
	if !asBool(flagValue) {
		return violation(fmt.Sprintf("Flag `%s` is explicitly false.", flagField), map[string]interface{}{"flag": flagField, "value": flagValue}, "")
	}
	spans := matchingSpans(detail, []string{eventType})
	if len(spans) == 0 {
		return gap(fmt.Sprintf("Flag `%s` is true but no `%s` event was recorded.", flagField, eventType), map[string]interface{}{"flag": flagField, "event_type": eventType}, "")
	}
	return covered("Override capability is declared and evidenced by a runtime event.", map[string]interface{}{"flag": flagField, "event_type": eventType, "matched_count": len(spans)}, spans[0].SpanID)
}

func (e *Engine) evalMetricThreshold(detail types.TraceDetail, params map[string]interface{}) outcome {
	minimums, _ := params["minimums"].(map[string]interface{})
	maximums, _ := params["maximums"].(map[string]interface{})
	for field, rawMinimum := range minimums {
		actual, ok := asFloat(findAny(detail, field))
		minimum, _ := asFloat(rawMinimum)
		if !ok {
			return gap(fmt.Sprintf("Metric `%s` is missing.", field), map[string]interface{}{"field": field}, "")
		}
		if actual < minimum {
			return violation(fmt.Sprintf("Metric `%s` is below threshold.", field), map[string]interface{}{"field": field, "actual": actual, "minimum": minimum}, "")
		}
	}
	for field, rawMaximum := range maximums {
		actual, ok := asFloat(findAny(detail, field))
		maximum, _ := asFloat(rawMaximum)
		if !ok {
			return gap(fmt.Sprintf("Metric `%s` is missing.", field), map[string]interface{}{"field": field}, "")
		}
		if actual > maximum {
			return violation(fmt.Sprintf("Metric `%s` exceeds threshold.", field), map[string]interface{}{"field": field, "actual": actual, "maximum": maximum}, "")
		}
	}
	return covered("All configured metrics are present and within threshold.", map[string]interface{}{"minimums": minimums, "maximums": maximums}, "")
}

func (e *Engine) evalModelScan(detail types.TraceDetail, field string, maxScore float64) outcome {
	spans := matchingSpans(detail, []string{"MODEL_INFERENCE"})
	if len(spans) == 0 {
		return notApplicable("No model inference spans were recorded.")
	}
	for _, span := range spans {
		value := span.Payload[field]
		if isEmpty(value) {
			return gap("Model inference scan result is missing.", map[string]interface{}{"span_id": span.SpanID, "field": field}, span.SpanID)
		}
		score, ok := asFloat(value)
		if !ok {
			return gap("Model inference scan result is not numeric.", map[string]interface{}{"span_id": span.SpanID, "field": field, "value": value}, span.SpanID)
		}
		if score > maxScore {
			return violation("Prompt injection score exceeds the allowed threshold.", map[string]interface{}{"span_id": span.SpanID, "score": score, "max_score": maxScore, "matched_count": len(spans)}, span.SpanID)
		}
	}
	return covered("Every model inference span includes an acceptable scan score.", map[string]interface{}{"field": field, "matched_count": len(spans)}, "")
}

func (e *Engine) evalFollowupEvent(detail types.TraceDetail, sourceEventType, followupEventType string, hours int) outcome {
	sources := matchingSpans(detail, []string{sourceEventType})
	if len(sources) == 0 {
		return notApplicable("No source events were recorded for this follow-up SLA.")
	}
	followups := matchingSpans(detail, []string{followupEventType})
	for _, source := range sources {
		found := false
		for _, followup := range followups {
			if !followup.StartTime.Before(source.StartTime) && followup.StartTime.Sub(source.StartTime) <= time.Duration(hours)*time.Hour {
				found = true
				break
			}
		}
		if !found {
			return violation("A required follow-up event was missing or late.", map[string]interface{}{"source_span_id": source.SpanID, "source_event_type": sourceEventType, "followup_event_type": followupEventType, "hours": hours}, source.SpanID)
		}
	}
	return covered("All source events were followed by the required action within SLA.", map[string]interface{}{"source_event_type": sourceEventType, "followup_event_type": followupEventType, "matched_count": len(sources)}, "")
}

func (e *Engine) evalSyntheticOutput(detail types.TraceDetail, field, expected string) outcome {
	spans := matchingSpans(detail, []string{"OUTPUT"})
	if len(spans) == 0 {
		return notApplicable("No output spans were recorded.")
	}
	for _, span := range spans {
		value := nonEmptyString(span.Payload[field])
		if value == "" {
			return gap("Output content type is missing.", map[string]interface{}{"span_id": span.SpanID}, span.SpanID)
		}
		if !strings.EqualFold(value, expected) {
			return violation("Output was not flagged as synthetic.", map[string]interface{}{"span_id": span.SpanID, "value": value, "expected": expected}, span.SpanID)
		}
	}
	return covered("Output spans are flagged as synthetic.", map[string]interface{}{"matched_count": len(spans), "value": expected}, "")
}

func (e *Engine) evalEnumOnPersonalData(detail types.TraceDetail, field string, allowed []string) outcome {
	found := false
	for _, span := range detail.Spans {
		if !personalDataSpan(span) {
			continue
		}
		found = true
		value := nonEmptyString(span.Payload[field])
		if value == "" {
			return gap(fmt.Sprintf("Field `%s` is missing on a personal-data event.", field), map[string]interface{}{"span_id": span.SpanID}, span.SpanID)
		}
		if !containsAny(allowed, value) {
			return violation(fmt.Sprintf("Field `%s` has invalid value `%s` on a personal-data event.", field, value), map[string]interface{}{"span_id": span.SpanID, "value": value, "allowed": allowed}, span.SpanID)
		}
	}
	if !found {
		return notApplicable("No personal-data events were recorded.")
	}
	return covered(fmt.Sprintf("Field `%s` is valid on personal-data events.", field), map[string]interface{}{"field": field}, "")
}

func (e *Engine) evalNonEmptyOnPersonalData(detail types.TraceDetail, field string) outcome {
	found := false
	for _, span := range detail.Spans {
		if !personalDataSpan(span) {
			continue
		}
		found = true
		if isEmpty(span.Payload[field]) {
			return gap(fmt.Sprintf("Field `%s` is missing on a personal-data event.", field), map[string]interface{}{"span_id": span.SpanID}, span.SpanID)
		}
	}
	if !found {
		return notApplicable("No personal-data events were recorded.")
	}
	return covered(fmt.Sprintf("Field `%s` is present on personal-data events.", field), map[string]interface{}{"field": field}, "")
}

func (e *Engine) evalPIIAccess(detail types.TraceDetail, piiFields []string) outcome {
	foundPII := false
	for _, span := range detail.Spans {
		fields := asStringSlice(span.Payload["data_fields_accessed"])
		if len(fields) == 0 {
			continue
		}
		piiUsed := false
		for _, field := range fields {
			if containsAny(piiFields, field) {
				piiUsed = true
				break
			}
		}
		if !piiUsed {
			continue
		}
		foundPII = true
		purpose := nonEmptyString(span.Payload["purpose"])
		justification := nonEmptyString(span.Payload["purpose_justification"])
		if purpose == "" && justification == "" {
			return violation("PII fields were accessed without purpose justification.", map[string]interface{}{"span_id": span.SpanID, "data_fields_accessed": fields}, span.SpanID)
		}
	}
	if !foundPII {
		return notApplicable("No configured PII fields were accessed.")
	}
	return covered("PII access was paired with purpose justification.", map[string]interface{}{"pii_fields": piiFields}, "")
}

func (e *Engine) evalFieldEqualsOnEventTypes(detail types.TraceDetail, field string, expected interface{}, eventTypes []string) outcome {
	spans := matchingSpans(detail, eventTypes)
	if len(spans) == 0 {
		return notApplicable("No matching event types were recorded.")
	}
	expectedString := nonEmptyString(expected)
	for _, span := range spans {
		value := span.Payload[field]
		if isEmpty(value) {
			return gap(fmt.Sprintf("Field `%s` is missing on a matching event.", field), map[string]interface{}{"span_id": span.SpanID, "event_type": span.EventType}, span.SpanID)
		}
		if !strings.EqualFold(nonEmptyString(value), expectedString) {
			return violation(fmt.Sprintf("Field `%s` does not match the expected value.", field), map[string]interface{}{"span_id": span.SpanID, "value": value, "expected": expectedString}, span.SpanID)
		}
	}
	return covered(fmt.Sprintf("Field `%s` matches on all matching events.", field), map[string]interface{}{"field": field, "matched_count": len(spans)}, "")
}

func (e *Engine) evalDeletionSchedule(detail types.TraceDetail, deletionField string) outcome {
	found := false
	for _, span := range detail.Spans {
		if !personalDataSpan(span) {
			continue
		}
		found = true
		if isEmpty(span.Payload[deletionField]) && isEmpty(findAny(detail, deletionField)) {
			return gap("Personal data evidence is missing a deletion schedule.", map[string]interface{}{"span_id": span.SpanID, "field": deletionField}, span.SpanID)
		}
	}
	if !found {
		return notApplicable("No personal-data events were recorded.")
	}
	return covered("Deletion scheduling is present for personal-data evidence.", map[string]interface{}{"field": deletionField}, "")
}

func (e *Engine) evalEncryptionAndChain(detail types.TraceDetail, encryptionField string) outcome {
	found := false
	for _, span := range detail.Spans {
		if !personalDataSpan(span) {
			continue
		}
		found = true
		if !asBool(span.Payload[encryptionField]) && !asBool(findAny(detail, encryptionField)) {
			return violation("Personal data evidence is not marked as encrypted.", map[string]interface{}{"span_id": span.SpanID, "field": encryptionField}, span.SpanID)
		}
	}
	if !found {
		return notApplicable("No personal-data events were recorded.")
	}
	hashOutcome := e.evalHashChain(detail)
	if hashOutcome.status != "COVERED" {
		return hashOutcome
	}
	return covered("Personal data evidence is encrypted and the chain hash is valid.", map[string]interface{}{"field": encryptionField}, "")
}

func (e *Engine) evalConditionalRequiredField(detail types.TraceDetail, ifField, equals, requiredField string) outcome {
	matched := false
	for _, span := range detail.Spans {
		if strings.EqualFold(nonEmptyString(span.Payload[ifField]), equals) {
			matched = true
			if isEmpty(span.Payload[requiredField]) && isEmpty(findAny(detail, requiredField)) {
				return violation(fmt.Sprintf("Field `%s` is required when `%s=%s`.", requiredField, ifField, equals), map[string]interface{}{"span_id": span.SpanID, "if_field": ifField, "required_field": requiredField}, span.SpanID)
			}
		}
	}
	if !matched && strings.EqualFold(nonEmptyString(findAny(detail, ifField)), equals) {
		matched = true
		if isEmpty(findAny(detail, requiredField)) {
			return violation(fmt.Sprintf("Field `%s` is required when `%s=%s`.", requiredField, ifField, equals), map[string]interface{}{"if_field": ifField, "required_field": requiredField}, "")
		}
	}
	if !matched {
		return notApplicable("The triggering condition for the required field was not observed.")
	}
	return covered(fmt.Sprintf("Conditional field `%s` is present when `%s=%s`.", requiredField, ifField, equals), map[string]interface{}{"if_field": ifField, "required_field": requiredField}, "")
}

func (e *Engine) evalReference(detail types.TraceDetail, field, prefix string) outcome {
	value := nonEmptyString(findAny(detail, field))
	if value == "" {
		return gap(fmt.Sprintf("Reference field `%s` is missing.", field), map[string]interface{}{"field": field}, "")
	}
	if prefix != "" && !strings.HasPrefix(value, prefix) {
		return violation(fmt.Sprintf("Reference field `%s` does not resolve to the expected namespace.", field), map[string]interface{}{"field": field, "value": value, "prefix": prefix}, "")
	}
	return covered(fmt.Sprintf("Reference field `%s` resolves to the expected namespace.", field), map[string]interface{}{"field": field, "value": value}, "")
}

func (e *Engine) evalSpecialCategory(detail types.TraceDetail, flagField, justificationField string) outcome {
	found := false
	for _, span := range detail.Spans {
		if !asBool(span.Payload[flagField]) {
			continue
		}
		found = true
		if isEmpty(span.Payload[justificationField]) {
			return violation("Special category processing lacks justification evidence.", map[string]interface{}{"span_id": span.SpanID, "flag_field": flagField}, span.SpanID)
		}
	}
	if !found {
		return notApplicable("No special category processing was recorded.")
	}
	return covered("Special category processing includes safeguard justification.", map[string]interface{}{"flag_field": flagField, "justification_field": justificationField}, "")
}

func (e *Engine) evalFirstSessionNotice(detail types.TraceDetail, field string) outcome {
	candidates := matchingSpans(detail, []string{"USER_INTERACTION", "HUMAN_HANDOFF", "OUTPUT"})
	if len(candidates) == 0 {
		if asBool(findAny(detail, field)) {
			return covered("Notice evidence is present at the trace level.", map[string]interface{}{"field": field, "value": true}, "")
		}
		return gap("Notice evidence is missing for the session.", map[string]interface{}{"field": field}, "")
	}
	first := candidates[0]
	if value, ok := first.Payload[field]; ok {
		if asBool(value) {
			return covered("The earliest user-facing span carries notice evidence.", map[string]interface{}{"field": field, "span_id": first.SpanID}, first.SpanID)
		}
		return violation("The earliest user-facing span explicitly lacks notice evidence.", map[string]interface{}{"field": field, "span_id": first.SpanID, "value": value}, first.SpanID)
	}
	for _, span := range matchingSpans(detail, []string{"PRIVACY_NOTICE"}) {
		if !span.StartTime.After(first.StartTime) {
			return covered("A dedicated privacy notice event precedes the first user-facing span.", map[string]interface{}{"notice_span_id": span.SpanID, "first_user_span_id": first.SpanID}, span.SpanID)
		}
	}
	return gap("No first-session notice evidence was tied to the earliest user-facing activity.", map[string]interface{}{"field": field, "first_user_span_id": first.SpanID}, first.SpanID)
}

func (e *Engine) evalIndirectDisclosure(detail types.TraceDetail, field string, maxDays int) outcome {
	usedIndirect := asBool(findAny(detail, "third_party_data_used")) || asBool(findAny(detail, "indirect_data_used"))
	value := findAny(detail, field)
	if !usedIndirect && isEmpty(value) {
		return notApplicable("No indirect or third-party data collection was declared.")
	}
	disclosedAt, ok := asTime(value)
	if !ok {
		return violation("Indirect data was used without a valid disclosure timestamp.", map[string]interface{}{"field": field, "value": value}, "")
	}
	startedAt := detail.Trace.CreatedAt
	if len(detail.Spans) > 0 {
		startedAt = detail.Spans[0].StartTime
	}
	if disclosedAt.Sub(startedAt) > time.Duration(maxDays)*24*time.Hour {
		return violation("Indirect data disclosure occurred outside the allowed window.", map[string]interface{}{"field": field, "disclosed_at": disclosedAt, "started_at": startedAt, "max_days": maxDays}, "")
	}
	return covered("Indirect data disclosure was recorded within the allowed window.", map[string]interface{}{"field": field, "disclosed_at": disclosedAt}, "")
}

func (e *Engine) evalRequestSLA(detail types.TraceDetail, requestedField, completedField string, maxDays int) outcome {
	requestedAt, ok := asTime(findAny(detail, requestedField))
	if !ok {
		return notApplicable("No request timestamp was recorded for this right-handling control.")
	}
	completedAt, completed := asTime(findAny(detail, completedField))
	if !completed {
		if time.Since(requestedAt) > time.Duration(maxDays)*24*time.Hour {
			return violation("A request remains open beyond the allowed SLA.", map[string]interface{}{"requested_at": requestedAt, "max_days": maxDays}, "")
		}
		return gap("A request is open and completion evidence is missing.", map[string]interface{}{"requested_at": requestedAt, "max_days": maxDays}, "")
	}
	if completedAt.Sub(requestedAt) > time.Duration(maxDays)*24*time.Hour {
		return violation("The request was completed outside the allowed SLA.", map[string]interface{}{"requested_at": requestedAt, "completed_at": completedAt, "max_days": maxDays}, "")
	}
	return covered("The request was completed within the allowed SLA.", map[string]interface{}{"requested_at": requestedAt, "completed_at": completedAt, "max_days": maxDays}, "")
}

func (e *Engine) evalRequestEventFollowed(detail types.TraceDetail, requestEventType, actionEventType string) outcome {
	windowHours := 24 * 30
	if strings.Contains(strings.ToUpper(requestEventType), "INCIDENT") {
		windowHours = 24
	}
	return e.evalFollowupEvent(detail, requestEventType, actionEventType, windowHours)
}

func (e *Engine) evalHashedIdentifiers(detail types.TraceDetail, field string, minLength int) outcome {
	subjects := asStringSlice(findAny(detail, field))
	if len(subjects) == 0 {
		return gap("Data subject identifiers are missing.", map[string]interface{}{"field": field}, "")
	}
	for _, subject := range subjects {
		if strings.Contains(subject, "@") || strings.Contains(subject, " ") || !looksHashed(subject, minLength) {
			return violation("Data subject identifiers do not appear hashed or pseudonymous.", map[string]interface{}{"field": field, "value": subject, "min_length": minLength}, "")
		}
	}
	return covered("Data subject identifiers appear hashed or pseudonymous.", map[string]interface{}{"field": field, "count": len(subjects)}, "")
}

func (e *Engine) evalObjectionHalts(detail types.TraceDetail, objectionEventType string, maxHours int) outcome {
	objections := matchingSpans(detail, []string{objectionEventType})
	if len(objections) == 0 {
		if isEmpty(findAny(detail, "objection_ref")) {
			return notApplicable("No objection event was recorded.")
		}
		return gap("An objection reference exists without a corresponding objection event.", map[string]interface{}{"objection_ref": findAny(detail, "objection_ref")}, "")
	}
	for _, objection := range objections {
		deadline := objection.StartTime.Add(time.Duration(maxHours) * time.Hour)
		halted := false
		for _, span := range detail.Spans {
			if span.StartTime.Before(objection.StartTime) {
				continue
			}
			if span.StartTime.After(deadline) && (span.EventType == "DECISION" || span.EventType == "DATA_ACCESS" || span.EventType == "MODEL_INFERENCE") {
				return violation("Processing continued after the objection halt window.", map[string]interface{}{"objection_span_id": objection.SpanID, "continued_span_id": span.SpanID, "max_hours": maxHours}, span.SpanID)
			}
			if span.StartTime.Before(deadline) && (span.EventType == "PROCESSING_HALTED" || asBool(span.Payload["processing_restricted"])) {
				halted = true
			}
		}
		if !halted {
			return gap("No halt or restriction evidence was recorded within the objection window.", map[string]interface{}{"objection_span_id": objection.SpanID, "max_hours": maxHours}, objection.SpanID)
		}
	}
	return covered("Objection handling shows processing halt or restriction within the required window.", map[string]interface{}{"objection_count": len(objections), "max_hours": maxHours}, objections[0].SpanID)
}

func (e *Engine) evalRestrictedSubjects(detail types.TraceDetail, restrictionField string) outcome {
	restrictedSubjects := map[string]struct{}{}
	for _, span := range detail.Spans {
		if asBool(span.Payload[restrictionField]) {
			for _, subject := range asStringSlice(span.Payload["data_subjects"]) {
				restrictedSubjects[subject] = struct{}{}
			}
		}
	}
	if len(restrictedSubjects) == 0 {
		return notApplicable("No restricted subjects were recorded.")
	}
	for _, span := range matchingSpans(detail, []string{"DECISION"}) {
		for _, subject := range asStringSlice(span.Payload["data_subjects"]) {
			if _, ok := restrictedSubjects[subject]; ok {
				return violation("A restricted subject was used in a decision event.", map[string]interface{}{"span_id": span.SpanID, "subject": subject}, span.SpanID)
			}
		}
	}
	return covered("Restricted subjects were not used in decision events.", map[string]interface{}{"restricted_subject_count": len(restrictedSubjects)}, "")
}

func (e *Engine) evalAutomatedDecision(detail types.TraceDetail, decisionEventType, handoffEventType string) outcome {
	decisions := matchingSpans(detail, []string{decisionEventType})
	if len(decisions) == 0 {
		return notApplicable("No decision events were recorded.")
	}
	handoffs := matchingSpans(detail, []string{handoffEventType})
	for _, decision := range decisions {
		if !personalDataSpan(decision) {
			continue
		}
		for _, handoff := range handoffs {
			if !handoff.StartTime.Before(decision.StartTime) {
				return covered("A human handoff exists after the automated decision.", map[string]interface{}{"decision_span_id": decision.SpanID, "handoff_span_id": handoff.SpanID}, handoff.SpanID)
			}
		}
		return violation("An automated decision involving personal data lacks a human handoff.", map[string]interface{}{"decision_span_id": decision.SpanID}, decision.SpanID)
	}
	return notApplicable("No personal-data decision events were recorded.")
}

func (e *Engine) evalProcessingRecords(detail types.TraceDetail, params map[string]interface{}) outcome {
	for _, field := range paramsStringSlice(params, "required_fields") {
		if isEmpty(findAny(detail, field)) {
			return gap("Processing record fields are incomplete.", map[string]interface{}{"missing_field": field}, "")
		}
	}
	if conditional, ok := params["conditional_fields"].(map[string]interface{}); ok {
		for trigger, requiredField := range conditional {
			if strings.EqualFold(nonEmptyString(findAny(detail, "lawful_basis")), trigger) && isEmpty(findAny(detail, nonEmptyString(requiredField))) {
				return violation("Conditional processing record evidence is missing.", map[string]interface{}{"lawful_basis": trigger, "missing_field": requiredField}, "")
			}
		}
	}
	return covered("Records of processing contain the required identifiers.", map[string]interface{}{"required_fields": paramsStringSlice(params, "required_fields")}, "")
}

func (e *Engine) evalFieldSetAndTrue(detail types.TraceDetail, stringField, boolField string) outcome {
	if isEmpty(findAny(detail, stringField)) {
		return gap(fmt.Sprintf("Field `%s` is missing.", stringField), map[string]interface{}{"field": stringField}, "")
	}
	if !asBool(findAny(detail, boolField)) {
		return violation(fmt.Sprintf("Field `%s` is not true.", boolField), map[string]interface{}{"field": boolField, "value": findAny(detail, boolField)}, "")
	}
	return covered("The required string and boolean fields are both satisfied.", map[string]interface{}{"string_field": stringField, "bool_field": boolField}, "")
}

func (e *Engine) evalTransfer(detail types.TraceDetail, countryField, requiredField string) outcome {
	country := strings.ToUpper(nonEmptyString(findAny(detail, countryField)))
	if country == "" {
		return notApplicable("No transfer destination was recorded.")
	}
	if _, ok := eeaCountries[country]; ok {
		return notApplicable("The transfer destination is inside the EEA.")
	}
	if isEmpty(findAny(detail, requiredField)) {
		return violation("Non-EEA transfer is missing a safeguard mechanism.", map[string]interface{}{"destination": country, "missing_field": requiredField}, "")
	}
	return covered("Non-EEA transfer includes a safeguard mechanism.", map[string]interface{}{"destination": country, "mechanism": findAny(detail, requiredField)}, "")
}

func (e *Engine) evalHealthMetrics(detail types.TraceDetail, metricsValue interface{}) outcome {
	metricsConfig, ok := metricsValue.(map[string]interface{})
	if !ok || len(metricsConfig) == 0 {
		return gap("Health metrics configuration is missing.", map[string]interface{}{}, "")
	}
	metrics, ok := findAny(detail, "health_metrics").(map[string]interface{})
	if !ok {
		return gap("Health metrics evidence is missing.", map[string]interface{}{}, "")
	}
	for metricName, rawConfig := range metricsConfig {
		config, cast := rawConfig.(map[string]interface{})
		if !cast {
			continue
		}
		actual, exists := asFloat(metrics[metricName])
		if !exists {
			return gap("A required health metric is missing.", map[string]interface{}{"metric": metricName}, "")
		}
		if max, exists := asFloat(config["max"]); exists && actual > max {
			return violation("A health metric exceeds the allowed threshold.", map[string]interface{}{"metric": metricName, "actual": actual, "max": max}, "")
		}
	}
	return covered("Health metrics are present and within threshold.", map[string]interface{}{"metrics": metrics}, "")
}

func (e *Engine) evalRBAC(detail types.TraceDetail, roleField, forbiddenEventType string) outcome {
	if isEmpty(findAny(detail, roleField)) {
		return gap("User role evidence is missing.", map[string]interface{}{"field": roleField}, "")
	}
	if len(matchingSpans(detail, []string{forbiddenEventType})) > 0 {
		return violation("A forbidden RBAC event was recorded.", map[string]interface{}{"event_type": forbiddenEventType}, "")
	}
	return covered("Role-based access evidence is present and no forbidden escalation event was recorded.", map[string]interface{}{"field": roleField}, "")
}

func (e *Engine) evalSubset(detail types.TraceDetail, supersetField, subsetField string) outcome {
	superset := asStringSlice(findAny(detail, supersetField))
	subset := asStringSlice(findAny(detail, subsetField))
	if len(superset) == 0 || len(subset) == 0 {
		return gap("Scope declaration or observed usage is missing.", map[string]interface{}{"superset_field": supersetField, "subset_field": subsetField}, "")
	}
	allowed := map[string]struct{}{}
	for _, value := range superset {
		allowed[strings.ToLower(value)] = struct{}{}
	}
	for _, value := range subset {
		if _, ok := allowed[strings.ToLower(value)]; !ok {
			return violation("Observed usage exceeded the declared scope.", map[string]interface{}{"value": value, "declared_scope": superset, "observed_scope": subset}, "")
		}
	}
	return covered("Observed usage stays within the declared scope.", map[string]interface{}{"declared_scope": superset, "observed_scope": subset}, "")
}

func (e *Engine) evalHashChain(detail types.TraceDetail) outcome {
	if len(detail.Evidence) == 0 {
		return gap("No evidence records were available for chain verification.", map[string]interface{}{}, "")
	}
	previous := ""
	for _, record := range detail.Evidence {
		if record.PreviousHash != previous {
			return violation("Evidence chain linkage is broken.", map[string]interface{}{"record_id": record.ID, "expected_previous_hash": previous, "actual_previous_hash": record.PreviousHash}, record.SpanID)
		}
		if record.PayloadHash == "" || record.ChainHash == "" || record.SignedChainHash == "" {
			return gap("Evidence record hashes are incomplete.", map[string]interface{}{"record_id": record.ID}, record.SpanID)
		}
		expectedChain := digestString(previous + record.PayloadHash)
		if record.ChainHash != expectedChain {
			return violation("Evidence chain hash does not recompute correctly.", map[string]interface{}{"record_id": record.ID, "expected_chain_hash": expectedChain, "actual_chain_hash": record.ChainHash}, record.SpanID)
		}
		previous = record.ChainHash
	}
	return covered("Evidence hash chain verifies successfully.", map[string]interface{}{"matched_count": len(detail.Evidence)}, "")
}

func (e *Engine) evalVersionChange(detail types.TraceDetail, changeEventType string) outcome {
	versions := map[string]struct{}{}
	if detail.Trace.AgentVersion != "" {
		versions[detail.Trace.AgentVersion] = struct{}{}
	}
	for _, span := range detail.Spans {
		if version := nonEmptyString(span.Payload["agent_version"]); version != "" {
			versions[version] = struct{}{}
		}
	}
	if len(versions) <= 1 {
		return notApplicable("No version change occurred within this trace.")
	}
	if len(matchingSpans(detail, []string{changeEventType})) == 0 {
		return violation("Agent version changed without an explicit update event.", map[string]interface{}{"versions": versions}, "")
	}
	return covered("Version changes were paired with an explicit update event.", map[string]interface{}{"versions": versions, "change_event_type": changeEventType}, "")
}

func (e *Engine) evalProviderFields(detail types.TraceDetail, fields []string) outcome {
	for _, field := range fields {
		if isEmpty(findAny(detail, field)) {
			return gap("A provider field is missing.", map[string]interface{}{"missing_field": field}, "")
		}
	}
	return covered("Provider identity fields are present.", map[string]interface{}{"fields": fields}, "")
}

func (e *Engine) evalNonEmptyFields(detail types.TraceDetail, fields []string) outcome {
	for _, field := range fields {
		if isEmpty(findAny(detail, field)) {
			return gap("A required field is missing.", map[string]interface{}{"missing_field": field}, "")
		}
	}
	return covered("All required fields are present.", map[string]interface{}{"fields": fields}, "")
}

func (e *Engine) evalOutputSafety(detail types.TraceDetail, piiField, scanField string) outcome {
	spans := matchingSpans(detail, []string{"OUTPUT"})
	if len(spans) == 0 {
		return notApplicable("No output events were recorded.")
	}
	for _, span := range spans {
		if isEmpty(span.Payload[piiField]) || isEmpty(span.Payload[scanField]) {
			return gap("Output safety evidence is incomplete.", map[string]interface{}{"span_id": span.SpanID}, span.SpanID)
		}
		if asBool(span.Payload[piiField]) || !strings.EqualFold(nonEmptyString(span.Payload[scanField]), "pass") {
			return violation("Output safety scanning detected disclosure risk.", map[string]interface{}{"span_id": span.SpanID, "pii_detected": span.Payload[piiField], "scan_result": span.Payload[scanField], "matched_count": len(spans)}, span.SpanID)
		}
	}
	return covered("Output safety scanning passed for all outputs.", map[string]interface{}{"matched_count": len(spans)}, "")
}

func (e *Engine) evalProvidersPinned(detail types.TraceDetail, fields []string) outcome {
	for _, field := range fields {
		value := strings.ToLower(nonEmptyString(findAny(detail, field)))
		if value == "" {
			return gap("A provider or version field is missing.", map[string]interface{}{"missing_field": field}, "")
		}
		if value == "latest" || strings.HasSuffix(value, ":latest") {
			return violation("A provider or model version is not pinned.", map[string]interface{}{"field": field, "value": value}, "")
		}
	}
	return covered("Providers and versions are declared without unpinned `latest` references.", map[string]interface{}{"fields": fields}, "")
}

func (e *Engine) evalSystemPrompt(detail types.TraceDetail, hashField, exposedField string) outcome {
	spans := matchingSpans(detail, []string{"MODEL_INFERENCE", "OUTPUT"})
	if len(spans) == 0 {
		return notApplicable("No model or output spans were recorded.")
	}
	seenHash := false
	for _, span := range spans {
		if value := nonEmptyString(span.Payload[hashField]); value != "" {
			seenHash = true
		}
		if asBool(span.Payload[exposedField]) {
			return violation("System prompt exposure was explicitly recorded.", map[string]interface{}{"span_id": span.SpanID, "exposed": true}, span.SpanID)
		}
	}
	if !seenHash {
		return gap("System prompt hash evidence is missing.", map[string]interface{}{"field": hashField}, "")
	}
	return covered("System prompt hash is present and no exposure was recorded.", map[string]interface{}{"hash_field": hashField}, "")
}

func (e *Engine) evalBoundedConsumption(detail types.TraceDetail, maxTokens int, maxCostUSD float64) outcome {
	tokenCount, tokenOK := asFloat(findAny(detail, "token_count"))
	costUSD, costOK := asFloat(findAny(detail, "cost_usd"))
	loopDetected := asBool(findAny(detail, "loop_detected"))
	if !tokenOK || !costOK || isEmpty(findAny(detail, "loop_detected")) {
		return gap("Consumption control evidence is incomplete.", map[string]interface{}{"token_count": findAny(detail, "token_count"), "cost_usd": findAny(detail, "cost_usd"), "loop_detected": findAny(detail, "loop_detected")}, "")
	}
	if loopDetected || tokenCount > float64(maxTokens) || costUSD > maxCostUSD {
		return violation("Run exceeded token, cost, or loop safety limits.", map[string]interface{}{"token_count": tokenCount, "max_tokens": maxTokens, "cost_usd": costUSD, "max_cost_usd": maxCostUSD, "loop_detected": loopDetected}, "")
	}
	return covered("Token, cost, and loop controls remained within policy.", map[string]interface{}{"token_count": tokenCount, "cost_usd": costUSD, "loop_detected": loopDetected}, "")
}

func (e *Engine) evalCombinedDisclosure(detail types.TraceDetail, aiField, capabilityEventType string) outcome {
	aiDisclosure := asBool(findAny(detail, aiField))
	capabilityEvents := matchingSpans(detail, []string{capabilityEventType})
	if !aiDisclosure && len(capabilityEvents) == 0 {
		return gap("Neither AI disclosure nor capability disclosure evidence is present.", map[string]interface{}{"ai_field": aiField, "capability_event_type": capabilityEventType}, "")
	}
	if !aiDisclosure {
		return violation("Capability disclosure exists but AI interaction disclosure is missing.", map[string]interface{}{"ai_field": aiField, "capability_event_type": capabilityEventType}, "")
	}
	if len(capabilityEvents) == 0 {
		return gap("AI interaction disclosure exists but capability disclosure is missing.", map[string]interface{}{"ai_field": aiField, "capability_event_type": capabilityEventType}, "")
	}
	return covered("Both AI interaction and capability disclosures are present.", map[string]interface{}{"ai_field": aiField, "capability_event_count": len(capabilityEvents)}, capabilityEvents[0].SpanID)
}
