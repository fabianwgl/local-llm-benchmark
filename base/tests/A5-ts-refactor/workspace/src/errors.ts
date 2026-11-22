import type { ApiResponse, ErrorBody } from "./types.ts";

/** An error that maps onto an HTTP status. Handlers throw these; the router turns them into responses. */
export class HttpError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "HttpError";
    this.status = status;
    this.code = code;
  }
}

export class ValidationError extends HttpError {
  constructor(message: string) {
    super(400, "invalid_request", message);
    this.name = "ValidationError";
  }
}

export class NotFoundError extends HttpError {
  constructor(message: string) {
    super(404, "not_found", message);
    this.name = "NotFoundError";
  }
}

export class UnprocessableError extends HttpError {
  constructor(code: string, message: string) {
    super(422, code, message);
    this.name = "UnprocessableError";
  }
}

export function errorResponse(err: unknown): ApiResponse<ErrorBody> {
  if (err instanceof HttpError) {
    return { status: err.status, body: { error: { code: err.code, message: err.message } } };
  }
  return { status: 500, body: { error: { code: "internal", message: "internal server error" } } };
}
