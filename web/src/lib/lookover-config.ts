const DEFAULT_API_BASE_URL = "http://localhost:8080";

export function getConfiguredApiBaseUrl() {
  return (
    process.env.LOOKOVER_API_BASE_URL?.trim() ||
    process.env.NEXT_PUBLIC_API_BASE_URL?.trim() ||
    process.env.NEXT_PUBLIC_LOOKOVER_API_BASE_URL?.trim() ||
    process.env.API_BASE_URL?.trim() ||
    DEFAULT_API_BASE_URL
  );
}
