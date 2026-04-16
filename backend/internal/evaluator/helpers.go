package evaluator

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"slices"
	"strconv"
	"strings"
	"time"
	"unicode"

	"github.com/ajitesh/lookover-codex/backend/internal/types"
)

var eeaCountries = map[string]struct{}{
	"AT": {}, "BE": {}, "BG": {}, "HR": {}, "CY": {}, "CZ": {}, "DK": {}, "EE": {}, "FI": {}, "FR": {},
	"DE": {}, "GR": {}, "HU": {}, "IS": {}, "IE": {}, "IT": {}, "LV": {}, "LI": {}, "LT": {}, "LU": {},
	"MT": {}, "NL": {}, "NO": {}, "PL": {}, "PT": {}, "RO": {}, "SK": {}, "SI": {}, "ES": {}, "SE": {},
}

func traceField(detail types.TraceDetail, field string) interface{} {
	switch field {
	case "trace_id":
		return detail.Trace.TraceID
	case "session_id":
		return detail.Trace.SessionID
	case "agent_id":
		return detail.Trace.AgentID
	case "agent_version":
		return detail.Trace.AgentVersion
	case "framework":
		return detail.Trace.Framework
	case "model_id":
		return detail.Trace.ModelID
	case "model_provider":
		return detail.Trace.ModelProvider
	case "model_version":
		return detail.Trace.ModelVersion
	case "ai_act_risk_tier":
		return detail.Trace.AIActRiskTier
	case "use_case_category":
		return detail.Trace.UseCaseCategory
	case "environment":
		return detail.Trace.Environment
	case "overall_risk_score":
		return detail.Trace.OverallRiskScore
	case "status":
		return detail.Trace.Status
	default:
		return detail.Trace.Metadata[field]
	}
}

func findAny(detail types.TraceDetail, field string) interface{} {
	if value := traceField(detail, field); !isEmpty(value) {
		return value
	}
	for _, span := range detail.Spans {
		if value, ok := span.Payload[field]; ok && !isEmpty(value) {
			return value
		}
	}
	return nil
}

func matchingSpans(detail types.TraceDetail, eventTypes []string) []types.Span {
	if len(eventTypes) == 0 {
		return detail.Spans
	}
	matches := make([]types.Span, 0, len(detail.Spans))
	for _, span := range detail.Spans {
		if slices.Contains(eventTypes, span.EventType) {
			matches = append(matches, span)
		}
	}
	return matches
}

func spanField(span types.Span, field string) interface{} {
	switch field {
	case "span_id":
		return span.SpanID
	case "trace_id":
		return span.TraceID
	case "parent_span_id":
		return span.ParentSpanID
	case "name":
		return span.Name
	case "event_type":
		return span.EventType
	case "status":
		return span.Status
	case "start_time":
		return span.StartTime
	case "end_time":
		return span.EndTime
	default:
		return span.Payload[field]
	}
}

func personalDataSpan(span types.Span) bool {
	if asBool(span.Payload["pii_flags"]) || asBool(span.Payload["special_category_flag"]) {
		return true
	}
	if !isEmpty(span.Payload["lawful_basis"]) || !isEmpty(span.Payload["data_subjects"]) || !isEmpty(span.Payload["data_fields_accessed"]) {
		return true
	}
	return false
}

func nonEmptyString(value interface{}) string {
	switch typed := value.(type) {
	case string:
		return strings.TrimSpace(typed)
	case fmt.Stringer:
		return strings.TrimSpace(typed.String())
	case float64:
		return strconv.FormatFloat(typed, 'f', -1, 64)
	case int:
		return strconv.Itoa(typed)
	case bool:
		if typed {
			return "true"
		}
		return "false"
	default:
		return ""
	}
}

func asFloat(value interface{}) (float64, bool) {
	switch typed := value.(type) {
	case float64:
		return typed, true
	case float32:
		return float64(typed), true
	case int:
		return float64(typed), true
	case int64:
		return float64(typed), true
	case jsonNumber:
		parsed, err := strconv.ParseFloat(string(typed), 64)
		return parsed, err == nil
	case string:
		parsed, err := strconv.ParseFloat(strings.TrimSpace(typed), 64)
		return parsed, err == nil
	case map[string]interface{}:
		if score, ok := typed["score"]; ok {
			return asFloat(score)
		}
	}
	return 0, false
}

type jsonNumber string

func asBool(value interface{}) bool {
	switch typed := value.(type) {
	case bool:
		return typed
	case string:
		return strings.EqualFold(strings.TrimSpace(typed), "true")
	case float64:
		return typed != 0
	case int:
		return typed != 0
	default:
		return false
	}
}

func asStringSlice(value interface{}) []string {
	switch typed := value.(type) {
	case []string:
		return typed
	case []interface{}:
		output := make([]string, 0, len(typed))
		for _, item := range typed {
			if str := nonEmptyString(item); str != "" {
				output = append(output, str)
			}
		}
		return output
	case string:
		if strings.TrimSpace(typed) == "" {
			return nil
		}
		parts := strings.Split(typed, ",")
		output := make([]string, 0, len(parts))
		for _, part := range parts {
			trimmed := strings.TrimSpace(part)
			if trimmed != "" {
				output = append(output, trimmed)
			}
		}
		return output
	default:
		return nil
	}
}

func asMapSlice(value interface{}) []map[string]interface{} {
	switch typed := value.(type) {
	case []map[string]interface{}:
		return typed
	case []interface{}:
		output := make([]map[string]interface{}, 0, len(typed))
		for _, item := range typed {
			if cast, ok := item.(map[string]interface{}); ok {
				output = append(output, cast)
			}
		}
		return output
	default:
		return nil
	}
}

func asTime(value interface{}) (time.Time, bool) {
	switch typed := value.(type) {
	case time.Time:
		return typed, true
	case string:
		if typed == "" {
			return time.Time{}, false
		}
		for _, layout := range []string{time.RFC3339Nano, time.RFC3339, "2006-01-02"} {
			if parsed, err := time.Parse(layout, typed); err == nil {
				return parsed, true
			}
		}
	case map[string]interface{}:
		if raw, ok := typed["at"]; ok {
			return asTime(raw)
		}
	}
	return time.Time{}, false
}

func paramsStringSlice(params map[string]interface{}, key string) []string {
	if params == nil {
		return nil
	}
	return asStringSlice(params[key])
}

func paramsString(params map[string]interface{}, key string) string {
	if params == nil {
		return ""
	}
	return nonEmptyString(params[key])
}

func paramsFloat(params map[string]interface{}, key string) (float64, bool) {
	if params == nil {
		return 0, false
	}
	return asFloat(params[key])
}

func paramsInt(params map[string]interface{}, key string) (int, bool) {
	if params == nil {
		return 0, false
	}
	value, ok := asFloat(params[key])
	return int(value), ok
}

func isEmpty(value interface{}) bool {
	switch typed := value.(type) {
	case nil:
		return true
	case string:
		return strings.TrimSpace(typed) == ""
	case []interface{}:
		return len(typed) == 0
	case []string:
		return len(typed) == 0
	case map[string]interface{}:
		return len(typed) == 0
	default:
		return false
	}
}

func containsAny(values []string, target string) bool {
	for _, value := range values {
		if strings.EqualFold(value, target) {
			return true
		}
	}
	return false
}

func digestString(value string) string {
	sum := sha256.Sum256([]byte(value))
	return hex.EncodeToString(sum[:])
}

func looksHashed(value string, minLength int) bool {
	if len(value) < minLength {
		return false
	}
	isHex := true
	for _, r := range value {
		if !unicode.IsDigit(r) && (r < 'a' || r > 'f') && (r < 'A' || r > 'F') {
			isHex = false
			break
		}
	}
	if isHex {
		return true
	}
	for _, r := range value {
		if !(unicode.IsDigit(r) || unicode.IsLetter(r) || r == '+' || r == '/' || r == '=') {
			return false
		}
	}
	return strings.Count(value, "=") <= 2 && len(value)%4 == 0
}
