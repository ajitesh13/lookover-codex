"""Static control references used by the pre-run scanner.

The Python side keeps this intentionally small and dependency-free. The backend
can keep the authoritative YAML catalog; the scanner only needs a stable set of
control references to attach evidence to findings.
"""

CONTROL_REFERENCES = {
    "ai_policy_ref": {
        "control_id": "ISO42001-5-2-AI-POLICY",
        "framework": "ISO_42001",
        "citation": "Clause 5.2",
        "title": "AI policy reference present",
    },
    "ai_risk_assessment_ref": {
        "control_id": "ISO42001-6-1-RISK-OPPORTUNITY",
        "framework": "ISO_42001",
        "citation": "Clause 6.1",
        "title": "AI risk and opportunity assessment current",
    },
    "ai_impact_assessment_ref": {
        "control_id": "ISO42001-8-2-IMPACT-ASSESSMENT",
        "framework": "ISO_42001",
        "citation": "Clause 8.2",
        "title": "AI impact assessment reference present",
    },
    "disclosure_shown": {
        "control_id": "ISO42001-7-4-COMMUNICATION",
        "framework": "ISO_42001",
        "citation": "Clause 7.4",
        "title": "User and capability disclosures present",
    },
    "human_reviewer_id": {
        "control_id": "ISO42001-8-5-HUMAN-OVERSIGHT",
        "framework": "ISO_42001",
        "citation": "Clause 8.5",
        "title": "Human oversight evidenced",
    },
    "tools_declared_scope": {
        "control_id": "ISO42001-8-1-OPERATIONAL-CONTROL",
        "framework": "ISO_42001",
        "citation": "Clause 8.1",
        "title": "Operational controls enforced",
    },
    "data_sources": {
        "control_id": "ISO42001-8-3-DATA-GOVERNANCE",
        "framework": "ISO_42001",
        "citation": "Clause 8.3",
        "title": "AI data governance documented",
    },
    "injection_scan_result": {
        "control_id": "OWASP-LLM01-PROMPT-INJECTION",
        "framework": "OWASP_LLM_TOP_10_2025",
        "citation": "LLM01:2025",
        "title": "Prompt injection scan coverage",
    },
    "output_validation_result": {
        "control_id": "OWASP-LLM05-OUTPUT-HANDLING",
        "framework": "OWASP_LLM_TOP_10_2025",
        "citation": "LLM05:2025",
        "title": "Output validation before tool execution",
    },
    "tools_invoked_scope": {
        "control_id": "OWASP-LLM06-EXCESSIVE-AGENCY",
        "framework": "OWASP_LLM_TOP_10_2025",
        "citation": "LLM06:2025",
        "title": "Tool use remains within declared scope",
    },
    "system_prompt_hash": {
        "control_id": "OWASP-LLM07-SYSTEM-PROMPT-LEAKAGE",
        "framework": "OWASP_LLM_TOP_10_2025",
        "citation": "LLM07:2025",
        "title": "System prompt protected",
    },
    "embedding_provenance": {
        "control_id": "OWASP-LLM08-VECTOR-WEAKNESS",
        "framework": "OWASP_LLM_TOP_10_2025",
        "citation": "LLM08:2025",
        "title": "Retrieval sources validated",
    },
}

MISSING_GOVERNANCE_FIELDS = [
    "ai_policy_ref",
    "ai_risk_assessment_ref",
    "ai_impact_assessment_ref",
    "human_reviewer_id",
    "disclosure_shown",
    "tools_declared_scope",
    "data_sources",
    "agent_version",
    "model_id",
]

