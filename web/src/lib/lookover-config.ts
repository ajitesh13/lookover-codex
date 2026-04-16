const DEFAULT_API_BASE_URL = "http://localhost:8080";
const DEFAULT_VOICE_AUDITOR_API_BASE_URL = "http://localhost:8000";

export function getConfiguredApiBaseUrl() {
  return (
    process.env.LOOKOVER_API_BASE_URL?.trim() ||
    process.env.NEXT_PUBLIC_API_BASE_URL?.trim() ||
    process.env.NEXT_PUBLIC_LOOKOVER_API_BASE_URL?.trim() ||
    process.env.API_BASE_URL?.trim() ||
    DEFAULT_API_BASE_URL
  );
}

export function getConfiguredVoiceAuditorApiBaseUrl() {
  return (
    process.env.VOICE_AUDITOR_API_BASE_URL?.trim() ||
    process.env.NEXT_PUBLIC_VOICE_AUDITOR_API_BASE_URL?.trim() ||
    DEFAULT_VOICE_AUDITOR_API_BASE_URL
  );
}
