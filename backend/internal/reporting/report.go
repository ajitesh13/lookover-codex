package reporting

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"github.com/ajitesh/lookover-codex/backend/internal/types"
)

func WriteTraceReport(reportsDir string, detail types.TraceDetail) (string, error) {
	if err := os.MkdirAll(reportsDir, 0o755); err != nil {
		return "", fmt.Errorf("create reports dir: %w", err)
	}
	target := filepath.Join(reportsDir, fmt.Sprintf("%s-report.json", detail.Trace.TraceID))
	raw, err := json.MarshalIndent(detail, "", "  ")
	if err != nil {
		return "", fmt.Errorf("marshal report: %w", err)
	}
	if err = os.WriteFile(target, raw, 0o644); err != nil {
		return "", fmt.Errorf("write report: %w", err)
	}
	return target, nil
}
