package config

import (
	"fmt"
	"os"
	"path/filepath"
)

type Config struct {
	DatabaseURL          string
	APIPort              string
	ReportsDir           string
	ControlsDir          string
	VoiceAuditorBaseURL  string
	VoiceAuditorTimeout  string
	SeedReviewerEmail    string
	SeedReviewerPassword string
}

func Load() (Config, error) {
	cfg := Config{
		DatabaseURL:          getEnv("DATABASE_URL", "postgres://lookover:lookover@localhost:5432/lookover_codex?sslmode=disable"),
		APIPort:              getEnv("API_PORT", "8080"),
		ReportsDir:           getEnv("REPORTS_DIR", filepath.Clean("../reports/generated")),
		ControlsDir:          getEnv("CONTROLS_DIR", filepath.Clean("../controls")),
		VoiceAuditorBaseURL:  getEnv("VOICE_AUDITOR_API_BASE_URL", "http://localhost:8000"),
		VoiceAuditorTimeout:  getEnv("VOICE_AUDITOR_TIMEOUT", "8s"),
		SeedReviewerEmail:    getEnv("SEED_REVIEWER_EMAIL", "reviewer@lookover.local"),
		SeedReviewerPassword: getEnv("SEED_REVIEWER_PASSWORD", "demo-reviewer"),
	}

	if cfg.DatabaseURL == "" {
		return Config{}, fmt.Errorf("DATABASE_URL is required")
	}
	if err := os.MkdirAll(cfg.ReportsDir, 0o755); err != nil {
		return Config{}, fmt.Errorf("create reports dir: %w", err)
	}
	return cfg, nil
}

func getEnv(key, fallback string) string {
	value := os.Getenv(key)
	if value == "" {
		return fallback
	}
	return value
}
