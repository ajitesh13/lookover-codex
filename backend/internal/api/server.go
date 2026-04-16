package api

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/ajitesh/lookover-codex/backend/internal/evaluator"
	"github.com/ajitesh/lookover-codex/backend/internal/reporting"
	"github.com/ajitesh/lookover-codex/backend/internal/store"
	"github.com/ajitesh/lookover-codex/backend/internal/types"
	"github.com/go-chi/chi/v5"
)

type Server struct {
	store               *store.Store
	engine              *evaluator.Engine
	reportsDir          string
	voiceAuditorBaseURL string
	httpClient          *http.Client
}

func New(store *store.Store, engine *evaluator.Engine, reportsDir, voiceAuditorBaseURL string, voiceAuditorTimeout time.Duration) http.Handler {
	server := &Server{
		store:               store,
		engine:              engine,
		reportsDir:          reportsDir,
		voiceAuditorBaseURL: strings.TrimRight(voiceAuditorBaseURL, "/"),
		httpClient: &http.Client{
			Timeout: voiceAuditorTimeout,
		},
	}

	router := chi.NewRouter()
	router.Use(server.cors)

	router.Get("/healthz", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, map[string]interface{}{"ok": true})
	})

	router.Route("/v1", func(r chi.Router) {
		server.mountAPI(r)
	})
	router.Route("/api", func(r chi.Router) {
		server.mountAPI(r)
	})
	return router
}

func (s *Server) mountAPI(r chi.Router) {
	r.Get("/prerun/scans", s.handleListPreRunScans)
	r.Post("/prerun/scans", s.handleCreatePreRunScan)
	r.Post("/prerun/events", s.handleRuntimeEvent)
	r.Get("/prerun/scans/{scanID}", s.handleGetPreRunScan)
	r.Post("/runtime/events", s.handleRuntimeEvent)
	r.Get("/traces", s.handleListTraces)
	r.Get("/traces/{traceID}", s.handleGetTrace)
	r.Post("/traces/{traceID}/close", s.handleCloseTrace)
	r.Get("/traces/{traceID}/findings", s.handleTraceFindings)
	r.Post("/traces/{traceID}/share", s.handleShareTrace)
	r.Get("/shared/{shareID}", s.handleGetShare)
	r.Get("/voice-runs", s.handleListVoiceRuns)
	r.Post("/voice-runs", s.handleCreateVoiceRun)
	r.Get("/voice-runs/{voiceRunID}", s.handleGetVoiceRun)
	r.Post("/auth/login", s.handleLogin)
}

func (s *Server) handleListPreRunScans(w http.ResponseWriter, r *http.Request) {
	scans, err := s.store.ListPreRunScans(r.Context())
	if err != nil {
		writeError(w, http.StatusInternalServerError, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]interface{}{"items": scans})
}

func (s *Server) handleCreatePreRunScan(w http.ResponseWriter, r *http.Request) {
	var scan types.PreRunScan
	if err := json.NewDecoder(r.Body).Decode(&scan); err != nil {
		writeError(w, http.StatusBadRequest, fmt.Errorf("decode pre-run scan: %w", err))
		return
	}
	if scan.ScanID == "" {
		scan.ScanID = randomID("scan")
	}
	if err := s.store.SavePreRunScan(r.Context(), scan); err != nil {
		writeError(w, http.StatusInternalServerError, err)
		return
	}
	writeJSON(w, http.StatusCreated, map[string]interface{}{"scan_id": scan.ScanID})
}

func (s *Server) handleGetPreRunScan(w http.ResponseWriter, r *http.Request) {
	scan, err := s.store.GetPreRunScan(r.Context(), chi.URLParam(r, "scanID"))
	if err != nil {
		writeError(w, http.StatusNotFound, err)
		return
	}
	writeJSON(w, http.StatusOK, scan)
}

func (s *Server) handleRuntimeEvent(w http.ResponseWriter, r *http.Request) {
	raw, err := decodeMap(r.Context(), r)
	if err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	event := normalizeRuntimeEvent(raw)
	if event.TraceID == "" || event.SpanID == "" {
		writeError(w, http.StatusBadRequest, fmt.Errorf("trace_id and span_id are required"))
		return
	}
	if err = s.store.UpsertRuntimeEvent(r.Context(), event); err != nil {
		writeError(w, http.StatusInternalServerError, err)
		return
	}
	writeJSON(w, http.StatusAccepted, map[string]interface{}{"trace_id": event.TraceID, "span_id": event.SpanID})
}

func (s *Server) handleListTraces(w http.ResponseWriter, r *http.Request) {
	traces, err := s.store.ListTraces(r.Context())
	if err != nil {
		writeError(w, http.StatusInternalServerError, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]interface{}{"items": traces})
}

func (s *Server) handleGetTrace(w http.ResponseWriter, r *http.Request) {
	trace, err := s.store.GetTraceDetail(r.Context(), chi.URLParam(r, "traceID"))
	if err != nil {
		writeError(w, http.StatusNotFound, err)
		return
	}
	writeJSON(w, http.StatusOK, trace)
}

func (s *Server) handleCloseTrace(w http.ResponseWriter, r *http.Request) {
	traceID := chi.URLParam(r, "traceID")
	if err := s.closeTrace(r.Context(), traceID); err != nil {
		writeError(w, http.StatusInternalServerError, err)
		return
	}
	trace, err := s.store.GetTraceDetail(r.Context(), traceID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err)
		return
	}
	writeJSON(w, http.StatusOK, trace)
}

func (s *Server) handleTraceFindings(w http.ResponseWriter, r *http.Request) {
	trace, err := s.store.GetTraceDetail(r.Context(), chi.URLParam(r, "traceID"))
	if err != nil {
		writeError(w, http.StatusNotFound, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]interface{}{
		"items":           trace.Findings,
		"control_summary": trace.ControlSummary,
	})
}

func (s *Server) handleShareTrace(w http.ResponseWriter, r *http.Request) {
	payload, err := decodeMap(r.Context(), r)
	if err != nil && err != http.ErrBodyNotAllowed {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	mode := "audit_log_only"
	if value := strings.TrimSpace(nonEmptyString(payload["mode"])); value != "" {
		mode = value
	}
	shareID, err := s.store.CreateShareLink(r.Context(), chi.URLParam(r, "traceID"), mode)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err)
		return
	}
	writeJSON(w, http.StatusCreated, map[string]interface{}{"share_id": shareID, "mode": mode})
}

func (s *Server) handleGetShare(w http.ResponseWriter, r *http.Request) {
	if _, err := s.requireSession(r.Context(), r); err != nil {
		writeError(w, http.StatusUnauthorized, err)
		return
	}
	share, err := s.store.GetShareDetail(r.Context(), chi.URLParam(r, "shareID"))
	if err != nil {
		writeError(w, http.StatusNotFound, err)
		return
	}
	writeJSON(w, http.StatusOK, share)
}

func (s *Server) handleLogin(w http.ResponseWriter, r *http.Request) {
	body, err := decodeMap(r.Context(), r)
	if err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	email := normalizeDemoEmail(nonEmptyString(body["email"]))
	writeJSON(w, http.StatusOK, map[string]interface{}{
		"token": demoSessionToken(email),
		"user":  demoAuthUser(email),
	})
}

func (s *Server) handleListVoiceRuns(w http.ResponseWriter, r *http.Request) {
	query, err := voiceRunQueryFromRequest(r)
	if err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}

	response, err := s.store.ListVoiceRuns(r.Context(), query)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err)
		return
	}
	writeJSON(w, http.StatusOK, response)
}

func (s *Server) handleGetVoiceRun(w http.ResponseWriter, r *http.Request) {
	record, err := s.store.GetVoiceRun(r.Context(), chi.URLParam(r, "voiceRunID"))
	if err != nil {
		writeError(w, http.StatusNotFound, err)
		return
	}
	writeJSON(w, http.StatusOK, record)
}

func (s *Server) handleCreateVoiceRun(w http.ResponseWriter, r *http.Request) {
	defer r.Body.Close()

	var payload types.VoiceRunCreateRequest
	if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
		writeError(w, http.StatusBadRequest, fmt.Errorf("decode voice run request: %w", err))
		return
	}

	payload = normalizeVoiceRunCreateRequest(payload)
	if strings.TrimSpace(payload.Transcript) == "" {
		writeError(w, http.StatusBadRequest, fmt.Errorf("transcript is required"))
		return
	}

	record := types.VoiceRunRecord{
		VoiceRunID:     randomID("vr"),
		CallID:         payload.CallID,
		Tenant:         payload.Tenant,
		Deployer:       payload.Deployer,
		Status:         "pending",
		AgentVersion:   payload.AgentVersion,
		PolicyVersion:  payload.PolicyVersion,
		TranscriptText: payload.Transcript,
	}
	if err := s.store.CreateVoiceRunPending(r.Context(), record); err != nil {
		writeError(w, http.StatusInternalServerError, err)
		return
	}

	auditorResponse, auditorReport, err := s.runVoiceAudit(r.Context(), payload)
	if err != nil {
		_ = s.store.FailVoiceRun(r.Context(), record.VoiceRunID, err.Error())
		writeError(w, http.StatusBadGateway, err)
		return
	}

	record.Status = "completed"
	record.Disposition = auditorResponse.Record.Disposition
	record.Applicability = auditorResponse.Record.Applicability
	record.AIDisclosureStatus = auditorResponse.Record.ComplianceEvidence.AIDisclosureStatus
	record.DisclosureTimestamp = auditorResponse.Record.ComplianceEvidence.DisclosureTimestamp
	record.HighRiskFlag = auditorResponse.Record.ComplianceEvidence.HighRiskFlag
	record.EmotionOrBiometricFeatures = auditorResponse.Record.ComplianceEvidence.EmotionRecognitionUsed || auditorResponse.Record.ComplianceEvidence.BiometricCategorisationUsed
	record.HumanHandoff = auditorResponse.Record.ComplianceEvidence.HumanOversightPathPresent
	record.TranscriptTurns = firstNonEmptyTranscriptTurns(auditorResponse)
	record.AuditorReport = auditorReport

	if err = s.store.CompleteVoiceRun(r.Context(), record); err != nil {
		writeError(w, http.StatusInternalServerError, err)
		return
	}

	stored, err := s.store.GetVoiceRun(r.Context(), record.VoiceRunID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err)
		return
	}
	writeJSON(w, http.StatusCreated, stored)
}

func (s *Server) closeTrace(ctx context.Context, traceID string) error {
	trace, err := s.store.GetTraceDetail(ctx, traceID)
	if err != nil {
		return err
	}
	results, overallRisk := s.engine.Evaluate(trace)
	if err = s.store.ReplaceControlResults(ctx, traceID, results, overallRisk, "CLOSED"); err != nil {
		return err
	}
	if err = s.store.MergeTraceMetadata(ctx, traceID, map[string]interface{}{
		"ruleset_version":        s.engine.RulesetVersion(),
		"overall_risk_score":     overallRisk,
		"compliance_trend_score": overallRisk,
	}); err != nil {
		return err
	}
	trace, err = s.store.GetTraceDetail(ctx, traceID)
	if err != nil {
		return err
	}
	reportPath, err := reporting.WriteTraceReport(s.reportsDir, trace)
	if err != nil {
		return err
	}
	return s.store.MergeTraceMetadata(ctx, traceID, map[string]interface{}{
		"audit_package_ready":          true,
		"external_audit_package_ready": true,
		"report_path":                  reportPath,
	})
}

func (s *Server) requireSession(ctx context.Context, r *http.Request) (types.AuthUser, error) {
	token := sessionTokenFromRequest(r)
	if token == "" {
		return types.AuthUser{}, fmt.Errorf("missing session token")
	}
	if demoEmail, ok := demoSessionEmail(token); ok {
		return demoAuthUser(demoEmail), nil
	}
	return s.store.ValidateSession(ctx, token)
}

func normalizeDemoEmail(email string) string {
	email = strings.TrimSpace(email)
	if email == "" {
		return "reviewer@lookover.local"
	}
	return email
}

func demoSessionToken(email string) string {
	return "demo-session:" + url.QueryEscape(normalizeDemoEmail(email))
}

func demoAuthUser(email string) types.AuthUser {
	return types.AuthUser{
		ID:    "demo-reviewer",
		Email: normalizeDemoEmail(email),
		Role:  "reviewer",
	}
}

func demoSessionEmail(token string) (string, bool) {
	token = strings.TrimSpace(token)
	switch {
	case strings.HasPrefix(token, "demo-session:"):
		email := strings.TrimSpace(strings.TrimPrefix(token, "demo-session:"))
		if decoded, decodeErr := url.QueryUnescape(email); decodeErr == nil && strings.TrimSpace(decoded) != "" {
			email = strings.TrimSpace(decoded)
		}
		return normalizeDemoEmail(email), true
	default:
		return "", false
	}
}

func sessionTokenFromRequest(r *http.Request) string {
	header := strings.TrimSpace(r.Header.Get("Authorization"))
	if header != "" {
		parts := strings.Fields(header)
		if len(parts) == 1 {
			return parts[0]
		}
		if len(parts) == 2 && strings.EqualFold(parts[0], "Bearer") {
			return strings.TrimSpace(parts[1])
		}
	}
	if cookie, err := r.Cookie("lookover_session_token"); err == nil {
		return strings.TrimSpace(cookie.Value)
	}
	return ""
}

func (s *Server) cors(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func decodeMap(_ context.Context, r *http.Request) (map[string]interface{}, error) {
	defer r.Body.Close()
	if r.Body == nil {
		return map[string]interface{}{}, nil
	}
	var raw map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&raw); err != nil {
		if errors.Is(err, io.EOF) {
			return map[string]interface{}{}, nil
		}
		return nil, err
	}
	return raw, nil
}

func normalizeRuntimeEvent(raw map[string]interface{}) types.RuntimeEvent {
	attributes := map[string]interface{}{}
	for key, value := range raw {
		if key == "attributes" || key == "metadata" || key == "payload" {
			continue
		}
		attributes[key] = value
	}
	if nested, ok := raw["attributes"].(map[string]interface{}); ok {
		for key, value := range nested {
			attributes[key] = value
		}
	}
	if nested, ok := raw["metadata"].(map[string]interface{}); ok {
		for key, value := range nested {
			attributes[key] = value
		}
	}
	if nested, ok := raw["payload"].(map[string]interface{}); ok {
		for key, value := range nested {
			attributes[key] = value
		}
	}

	traceID := nonEmptyString(raw["trace_id"])
	if traceID == "" {
		traceID = nonEmptyString(attributes["trace_id"])
	}
	if traceID == "" {
		traceID = randomID("trace")
	}

	spanID := nonEmptyString(raw["span_id"])
	if spanID == "" {
		spanID = nonEmptyString(attributes["span_id"])
	}
	if spanID == "" {
		spanID = randomID("span")
	}

	parentSpanID := nonEmptyString(raw["parent_span_id"])
	if parentSpanID == "" {
		parentSpanID = nonEmptyString(attributes["parent_span_id"])
	}

	startTime, ok := parseTime(raw["start_time"])
	if !ok {
		startTime, ok = parseTime(attributes["start_time"])
	}
	if !ok {
		startTime, ok = parseTime(raw["timestamp"])
	}
	if !ok {
		startTime, ok = parseTime(attributes["timestamp"])
	}
	if !ok {
		startTime = time.Now().UTC()
	}
	endTime, ok := parseTime(raw["end_time"])
	if !ok {
		endTime, ok = parseTime(attributes["end_time"])
	}
	if !ok {
		endTime = startTime
	}

	return types.RuntimeEvent{
		TraceID:      traceID,
		SpanID:       spanID,
		ParentSpanID: parentSpanID,
		SessionID:    firstNonEmpty(raw["session_id"], attributes["session_id"]),
		AgentID:      firstNonEmpty(raw["agent_id"], attributes["agent_id"]),
		AgentVersion: firstNonEmpty(raw["agent_version"], attributes["agent_version"]),
		Name:         firstNonEmpty(raw["name"], attributes["name"], raw["event_type"], attributes["event_type"]),
		EventType:    firstNonEmpty(raw["event_type"], attributes["event_type"]),
		Status:       firstNonEmpty(raw["status"], attributes["status"], "completed"),
		StartTime:    startTime,
		EndTime:      endTime,
		Attributes:   attributes,
	}
}

func writeJSON(w http.ResponseWriter, status int, payload interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}

func writeError(w http.ResponseWriter, status int, err error) {
	writeJSON(w, status, map[string]interface{}{
		"error": err.Error(),
	})
}

func firstNonEmpty(values ...interface{}) string {
	for _, value := range values {
		if candidate := nonEmptyString(value); candidate != "" {
			return candidate
		}
	}
	return ""
}

func nonEmptyString(value interface{}) string {
	switch typed := value.(type) {
	case string:
		return strings.TrimSpace(typed)
	default:
		if typed == nil {
			return ""
		}
		return strings.TrimSpace(fmt.Sprintf("%v", typed))
	}
}

func parseTime(value interface{}) (time.Time, bool) {
	switch typed := value.(type) {
	case time.Time:
		return typed, true
	case string:
		for _, layout := range []string{time.RFC3339Nano, time.RFC3339, "2006-01-02"} {
			if parsed, err := time.Parse(layout, typed); err == nil {
				return parsed, true
			}
		}
	}
	return time.Time{}, false
}

func randomID(prefix string) string {
	buf := make([]byte, 8)
	_, _ = rand.Read(buf)
	return fmt.Sprintf("%s_%s", prefix, hex.EncodeToString(buf))
}

func normalizeVoiceRunCreateRequest(payload types.VoiceRunCreateRequest) types.VoiceRunCreateRequest {
	if strings.TrimSpace(payload.CallID) == "" {
		payload.CallID = randomID("voice-call")
	}
	if strings.TrimSpace(payload.Tenant) == "" {
		payload.Tenant = "lookover-voice-runs"
	}
	if strings.TrimSpace(payload.Deployer) == "" {
		payload.Deployer = "voice-ops"
	}
	if strings.TrimSpace(payload.Language) == "" {
		payload.Language = "en"
	}
	if strings.TrimSpace(payload.AgentVersion) == "" {
		payload.AgentVersion = "voice-runs-ui-v1"
	}
	if strings.TrimSpace(payload.PolicyVersion) == "" {
		payload.PolicyVersion = "policy-voice-runs-ui"
	}
	if strings.TrimSpace(payload.RawAudioURI) == "" {
		payload.RawAudioURI = "backend://voice-runs"
	}
	return payload
}

func voiceRunQueryFromRequest(r *http.Request) (types.VoiceRunQuery, error) {
	values := r.URL.Query()
	dateFrom, err := parseOptionalQueryDate(values.Get("from"), false)
	if err != nil {
		return types.VoiceRunQuery{}, err
	}
	dateTo, err := parseOptionalQueryDate(values.Get("to"), true)
	if err != nil {
		return types.VoiceRunQuery{}, err
	}
	page, err := parseIntQuery(values.Get("page"), 1)
	if err != nil {
		return types.VoiceRunQuery{}, err
	}
	pageSize, err := parseIntQuery(values.Get("page_size"), 25)
	if err != nil {
		return types.VoiceRunQuery{}, err
	}

	return types.VoiceRunQuery{
		Query:                      strings.TrimSpace(values.Get("query")),
		Status:                     strings.TrimSpace(values.Get("status")),
		Disposition:                strings.TrimSpace(values.Get("disposition")),
		Tenant:                     strings.TrimSpace(values.Get("tenant")),
		Deployer:                   strings.TrimSpace(values.Get("deployer")),
		Applicability:              strings.TrimSpace(values.Get("applicability")),
		AIDisclosureStatus:         strings.TrimSpace(values.Get("ai_disclosure_status")),
		Article:                    strings.TrimSpace(values.Get("article")),
		Severity:                   strings.TrimSpace(values.Get("severity")),
		DateFrom:                   dateFrom,
		DateTo:                     dateTo,
		HighRiskFlag:               parseOptionalBoolQuery(values.Get("high_risk_flag")),
		EmotionOrBiometricFeatures: parseOptionalBoolQuery(values.Get("emotion_or_biometric_features")),
		HumanHandoff:               parseOptionalBoolQuery(values.Get("human_handoff")),
		Page:                       page,
		PageSize:                   pageSize,
	}, nil
}

func parseOptionalQueryDate(raw string, inclusiveEnd bool) (*time.Time, error) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return nil, nil
	}
	parsed, err := time.Parse("2006-01-02", raw)
	if err != nil {
		return nil, fmt.Errorf("invalid date %q", raw)
	}
	if inclusiveEnd {
		parsed = parsed.Add(23*time.Hour + 59*time.Minute + 59*time.Second)
	}
	value := parsed.UTC()
	return &value, nil
}

func parseIntQuery(raw string, fallback int) (int, error) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return fallback, nil
	}
	var value int
	if _, err := fmt.Sscanf(raw, "%d", &value); err != nil {
		return 0, fmt.Errorf("invalid numeric query value %q", raw)
	}
	return value, nil
}

func parseOptionalBoolQuery(raw string) *bool {
	raw = strings.TrimSpace(strings.ToLower(raw))
	switch raw {
	case "true":
		value := true
		return &value
	case "false":
		value := false
		return &value
	default:
		return nil
	}
}

func (s *Server) runVoiceAudit(ctx context.Context, payload types.VoiceRunCreateRequest) (types.VoiceAuditorResponse, map[string]interface{}, error) {
	requestBody := map[string]interface{}{
		"transcript":                        payload.Transcript,
		"call_id":                           payload.CallID,
		"tenant":                            payload.Tenant,
		"deployer":                          payload.Deployer,
		"language":                          payload.Language,
		"agent_version":                     payload.AgentVersion,
		"policy_version":                    payload.PolicyVersion,
		"raw_audio_uri":                     payload.RawAudioURI,
		"synthetic_audio_used":              payload.SyntheticAudioUsed,
		"synthetic_audio_marked":            payload.SyntheticAudioMarked,
		"deepfake_like_content_flag":        payload.DeepfakeLikeContentFlag,
		"emotion_recognition_used":          payload.EmotionRecognitionUsed,
		"biometric_categorisation_used":     payload.BiometricCategorisationUsed,
		"decision_support_flag":             payload.DecisionSupportFlag,
		"human_oversight_path_present":      payload.HumanOversightPathPresent,
		"notice_to_affected_person_present": payload.NoticeToAffectedPersonPresent,
		"high_risk_flag":                    payload.HighRiskFlag,
	}

	rawBody, err := json.Marshal(requestBody)
	if err != nil {
		return types.VoiceAuditorResponse{}, nil, fmt.Errorf("marshal voice auditor request: %w", err)
	}

	request, err := http.NewRequestWithContext(ctx, http.MethodPost, s.voiceAuditorBaseURL+"/api/transcript-audits", strings.NewReader(string(rawBody)))
	if err != nil {
		return types.VoiceAuditorResponse{}, nil, fmt.Errorf("build voice auditor request: %w", err)
	}
	request.Header.Set("Accept", "application/json")
	request.Header.Set("Content-Type", "application/json")

	response, err := s.httpClient.Do(request)
	if err != nil {
		return types.VoiceAuditorResponse{}, nil, fmt.Errorf("call voice auditor: %w", err)
	}
	defer response.Body.Close()

	var rawResponse map[string]interface{}
	if err = json.NewDecoder(response.Body).Decode(&rawResponse); err != nil {
		return types.VoiceAuditorResponse{}, nil, fmt.Errorf("decode voice auditor response: %w", err)
	}
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		if detail := nonEmptyString(rawResponse["detail"]); detail != "" {
			return types.VoiceAuditorResponse{}, rawResponse, fmt.Errorf("voice auditor: %s", detail)
		}
		if detail := nonEmptyString(rawResponse["error"]); detail != "" {
			return types.VoiceAuditorResponse{}, rawResponse, fmt.Errorf("voice auditor: %s", detail)
		}
		return types.VoiceAuditorResponse{}, rawResponse, fmt.Errorf("voice auditor returned status %d", response.StatusCode)
	}

	normalizedRaw, err := json.Marshal(rawResponse)
	if err != nil {
		return types.VoiceAuditorResponse{}, rawResponse, fmt.Errorf("re-marshal voice auditor response: %w", err)
	}

	var auditorResponse types.VoiceAuditorResponse
	if err = json.Unmarshal(normalizedRaw, &auditorResponse); err != nil {
		return types.VoiceAuditorResponse{}, rawResponse, fmt.Errorf("normalize voice auditor response: %w", err)
	}

	return auditorResponse, rawResponse, nil
}

func firstNonEmptyTranscriptTurns(response types.VoiceAuditorResponse) []types.VoiceTranscriptTurn {
	if len(response.TranscriptTurns) > 0 {
		return response.TranscriptTurns
	}
	return response.Record.TranscriptTurns
}
