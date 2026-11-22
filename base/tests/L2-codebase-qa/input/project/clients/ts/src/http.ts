import { CLIENT_NAME, DEFAULT_TIMEOUT_MS, HEADERS, RETRYABLE_STATUS } from "./constants";

export interface TransportOptions {
  token?: string;
  timeoutMs?: number;
  retries?: number;
  fetch?: typeof fetch;
}

export interface RequestOptions {
  body?: unknown;
  query?: Record<string, string | number | undefined>;
  idempotent?: boolean;
  idempotencyKey?: string;
  signal?: AbortSignal;
}

export class HttpError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "HttpError";
  }
}

export class HttpTransport {
  private readonly fetchImpl: typeof fetch;

  constructor(
    private readonly baseUrl: string,
    private readonly options: TransportOptions = {},
  ) {
    this.fetchImpl = options.fetch ?? globalThis.fetch;
  }

  async request<T>(method: string, path: string, opts: RequestOptions = {}): Promise<T> {
    const url = new URL(path, this.baseUrl);
    for (const [k, v] of Object.entries(opts.query ?? {})) {
      if (v !== undefined) url.searchParams.set(k, String(v));
    }
    const headers: Record<string, string> = { Accept: "application/json", [HEADERS.client]: CLIENT_NAME };
    if (this.options.token) headers.Authorization = `Bearer ${this.options.token}`;
    if (opts.body !== undefined) headers["Content-Type"] = "application/json";
    if (opts.idempotent) headers[HEADERS.idempotency] = opts.idempotencyKey ?? newKey();

    const canRetry = method === "GET" || opts.idempotent === true;
    const attempts = canRetry ? 1 + (this.options.retries ?? 2) : 1;
    let last: unknown;
    for (let i = 0; i < attempts; i++) {
      if (i > 0) await sleep(250 * 2 ** (i - 1));
      const res = await this.fetchImpl(url, {
        method,
        headers,
        body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
        signal: opts.signal ?? AbortSignal.timeout(this.options.timeoutMs ?? DEFAULT_TIMEOUT_MS),
      });
      if (res.ok) {
        return (res.status === 204 ? undefined : await res.json()) as T;
      }
      const err = await toError(res);
      if (!RETRYABLE_STATUS.includes(res.status)) throw err;
      last = err;
    }
    throw last;
  }
}

async function toError(res: Response): Promise<HttpError> {
  try {
    const body = (await res.json()) as { error?: string; message?: string };
    return new HttpError(res.status, body.error ?? "unknown", body.message ?? res.statusText);
  } catch {
    return new HttpError(res.status, "unknown", res.statusText);
  }
}

function newKey(): string {
  return globalThis.crypto.randomUUID();
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
