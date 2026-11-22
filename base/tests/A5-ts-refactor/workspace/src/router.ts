import { errorResponse, NotFoundError } from "./errors.ts";
import { priceCart } from "./handlers/cart.ts";
import { checkCoupon } from "./handlers/coupons.ts";
import { createInvoice } from "./handlers/invoice.ts";
import { health, listCountries } from "./handlers/meta.ts";
import { getProductHandler, listProductsHandler } from "./handlers/products.ts";
import { createQuote } from "./handlers/quote.ts";
import { pathSegments } from "./http.ts";
import type { ApiRequest, ApiResponse, Handler } from "./types.ts";

interface Route {
  method: string;
  pattern: string[];
  handler: Handler;
}

function r(method: string, path: string, handler: Handler): Route {
  return { method, pattern: pathSegments(path), handler };
}

const ROUTES: Route[] = [
  r("GET", "/health", health),
  r("GET", "/countries", listCountries),
  r("GET", "/products", listProductsHandler),
  r("GET", "/products/:sku", getProductHandler),
  r("POST", "/coupons/check", checkCoupon),
  r("POST", "/cart/price", priceCart),
  r("POST", "/quotes", createQuote),
  r("POST", "/invoices", createInvoice),
];

function match(pattern: string[], segments: string[]): Record<string, string> | null {
  if (pattern.length !== segments.length) {
    return null;
  }
  const params: Record<string, string> = {};
  for (let i = 0; i < pattern.length; i++) {
    if (pattern[i].startsWith(":")) {
      params[pattern[i].slice(1)] = decodeURIComponent(segments[i]);
    } else if (pattern[i] !== segments[i]) {
      return null;
    }
  }
  return params;
}

/** Entry point for every request. Never throws: errors become error responses. */
export function handle(req: ApiRequest): ApiResponse {
  const segments = pathSegments(req.path);
  let pathMatched = false;
  for (const route of ROUTES) {
    const params = match(route.pattern, segments);
    if (!params) {
      continue;
    }
    pathMatched = true;
    if (route.method !== req.method.toUpperCase()) {
      continue;
    }
    try {
      return route.handler(req, params);
    } catch (err) {
      return errorResponse(err);
    }
  }
  if (pathMatched) {
    return { status: 405, body: { error: { code: "method_not_allowed", message: `${req.method} not allowed` } } };
  }
  return errorResponse(new NotFoundError(`no route for ${req.path}`));
}
