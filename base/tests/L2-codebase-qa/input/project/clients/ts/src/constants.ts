export const API_VERSION = "v1";

export const IDEMPOTENCY_HEADER = "Idempotency-Key";

export const HEADERS = {
  idempotency: "X-Tessera-Idem-Key",
  client: "X-Tessera-Client",
  requestId: "X-Request-Id",
} as const;

export const CLIENT_NAME = "tessera-ts/0.14";
export const DEFAULT_TIMEOUT_MS = 30_000;
export const RETRYABLE_STATUS: readonly number[] = [502, 503, 504];
