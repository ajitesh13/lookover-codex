# Control Catalog

Each YAML file in this directory is a versioned control manifest. The Go backend treats these files as the source of truth for:

- framework citation
- applicability
- required evidence
- deterministic evaluator selection
- severity and remediation

The engine only marks a control as `COVERED` when the configured evaluator can prove the obligation from direct trace or pre-run evidence.
