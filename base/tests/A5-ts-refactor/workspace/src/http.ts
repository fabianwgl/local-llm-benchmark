import type { ApiResponse } from "./types.ts";

export function ok<T>(body: T): ApiResponse<T> {
  return { status: 200, body };
}

export function created<T>(body: T): ApiResponse<T> {
  return { status: 201, body };
}

/** Splits "/products/KB-101?x=1" into path segments, ignoring the query string. */
export function pathSegments(path: string): string[] {
  const clean = path.split("?")[0];
  return clean.split("/").filter((s) => s.length > 0);
}
