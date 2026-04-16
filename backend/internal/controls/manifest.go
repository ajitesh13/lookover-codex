package controls

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"gopkg.in/yaml.v3"
)

type Manifest struct {
	Version     int       `yaml:"version"`
	Framework   string    `yaml:"framework"`
	Description string    `yaml:"description"`
	Controls    []Control `yaml:"controls"`
}

type Control struct {
	ID               string          `yaml:"id"`
	Citation         string          `yaml:"citation"`
	Title            string          `yaml:"title"`
	Obligation       string          `yaml:"obligation"`
	Scope            string          `yaml:"scope"`
	AppliesTo        AppliesTo       `yaml:"applies_to"`
	RequiredEvidence []string        `yaml:"required_evidence"`
	Evaluator        EvaluatorConfig `yaml:"evaluator"`
	Severity         string          `yaml:"severity"`
	Priority         string          `yaml:"priority"`
	Remediation      string          `yaml:"remediation"`
}

type AppliesTo struct {
	RiskTiers  []string `yaml:"risk_tiers"`
	EventTypes []string `yaml:"event_types"`
}

type EvaluatorConfig struct {
	Kind   string                 `yaml:"kind"`
	Params map[string]interface{} `yaml:"params"`
}

func LoadAll(dir string) ([]Manifest, error) {
	pattern := filepath.Join(dir, "*.yaml")
	files, err := filepath.Glob(pattern)
	if err != nil {
		return nil, fmt.Errorf("glob controls: %w", err)
	}
	sort.Strings(files)

	manifests := make([]Manifest, 0, len(files))
	for _, path := range files {
		raw, readErr := os.ReadFile(path)
		if readErr != nil {
			return nil, fmt.Errorf("read %s: %w", path, readErr)
		}
		var manifest Manifest
		if unmarshalErr := yaml.Unmarshal(raw, &manifest); unmarshalErr != nil {
			return nil, fmt.Errorf("parse %s: %w", path, unmarshalErr)
		}
		if manifest.Framework == "" {
			return nil, fmt.Errorf("control manifest %s missing framework", path)
		}
		manifests = append(manifests, manifest)
	}
	return manifests, nil
}
