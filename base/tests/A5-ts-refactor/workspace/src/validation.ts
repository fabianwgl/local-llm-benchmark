import { getProduct } from "./catalog.ts";
import { MAX_LINES, MAX_QUANTITY, MAX_QUOTE_VALIDITY_DAYS } from "./config.ts";
import { findCoupon } from "./coupons.ts";
import { isIsoDate } from "./dates.ts";
import { UnprocessableError, ValidationError } from "./errors.ts";
import { isSupportedCountry } from "./tax.ts";
import type { CartRequest, CountryCode, InvoiceRequest, LineInput, QuoteRequest } from "./types.ts";

type Json = Record<string, unknown>;

function isRecord(value: unknown): value is Json {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function requireBody(body: unknown): Json {
  if (!isRecord(body)) {
    throw new ValidationError("request body must be a JSON object");
  }
  return body;
}

function requireString(obj: Json, key: string, label: string = key): string {
  const value = obj[key];
  if (typeof value !== "string" || value.trim() === "") {
    throw new ValidationError(`${label} is required`);
  }
  return value;
}

function optionalString(obj: Json, key: string): string | undefined {
  const value = obj[key];
  if (value === undefined || value === null) {
    return undefined;
  }
  if (typeof value !== "string") {
    throw new ValidationError(`${key} must be a string`);
  }
  return value;
}

function requireCountry(obj: Json, key: string): CountryCode {
  const value = requireString(obj, key);
  if (!isSupportedCountry(value)) {
    throw new UnprocessableError("unsupported_country", `we do not ship to ${value}`);
  }
  return value;
}

function requireDate(obj: Json, key: string): string {
  const value = requireString(obj, key);
  if (!isIsoDate(value)) {
    throw new ValidationError(`${key} must be a date in YYYY-MM-DD format`);
  }
  return value;
}

/** Validates the requested lines: known, active products and whole, non-negative quantities. */
export function requireLines(obj: Json, key: string): LineInput[] {
  const raw = obj[key];
  if (!Array.isArray(raw) || raw.length === 0) {
    throw new ValidationError(`${key} must be a non-empty array`);
  }
  if (raw.length > MAX_LINES) {
    throw new ValidationError(`at most ${MAX_LINES} ${key} per request`);
  }
  return raw.map((entry: unknown, i: number) => {
    if (!isRecord(entry)) {
      throw new ValidationError(`${key}[${i}] must be an object`);
    }
    const sku = requireString(entry, "sku", `${key}[${i}].sku`);
    const quantity = entry.quantity;
    if (typeof quantity !== "number" || !Number.isInteger(quantity) || quantity < 0) {
      throw new ValidationError(`${key}[${i}].quantity must be a whole number of at least 0`);
    }
    if (quantity > MAX_QUANTITY) {
      throw new UnprocessableError("quantity_too_large", `${key}[${i}]: please contact sales for more than ${MAX_QUANTITY} units`);
    }
    const product = getProduct(sku);
    if (!product) {
      throw new UnprocessableError("unknown_sku", `unknown product ${sku}`);
    }
    if (!product.active) {
      throw new UnprocessableError("product_unavailable", `${sku} is no longer sold`);
    }
    return { sku, quantity };
  });
}

function requireCouponCode(obj: Json, key: string): string | undefined {
  const code = optionalString(obj, key);
  if (code === undefined || code.trim() === "") {
    return undefined;
  }
  if (!findCoupon(code)) {
    throw new UnprocessableError("unknown_coupon", `coupon ${code} does not exist`);
  }
  return code;
}

export function validateCartRequest(body: unknown): CartRequest {
  const obj = requireBody(body);
  return {
    items: requireLines(obj, "items"),
    country: requireCountry(obj, "country"),
    couponCode: requireCouponCode(obj, "couponCode"),
  };
}

export function validateQuoteRequest(body: unknown): QuoteRequest {
  const obj = requireBody(body);
  const customer = obj.customer;
  if (!isRecord(customer)) {
    throw new ValidationError("customer is required");
  }
  const validityDays = obj.validityDays;
  if (validityDays !== undefined) {
    if (typeof validityDays !== "number" || !Number.isInteger(validityDays) || validityDays < 1) {
      throw new ValidationError("validityDays must be a positive whole number");
    }
    if (validityDays > MAX_QUOTE_VALIDITY_DAYS) {
      throw new ValidationError(`validityDays must be at most ${MAX_QUOTE_VALIDITY_DAYS}`);
    }
  }
  return {
    customer: {
      name: requireString(customer, "name", "customer.name"),
      company: optionalString(customer, "company"),
      email: optionalString(customer, "email"),
    },
    lines: requireLines(obj, "lines"),
    country: requireCountry(obj, "country"),
    coupon: requireCouponCode(obj, "coupon"),
    date: requireDate(obj, "date"),
    validityDays: validityDays as number | undefined,
  };
}

export function validateInvoiceRequest(body: unknown): InvoiceRequest {
  const obj = requireBody(body);
  const orderId = requireString(obj, "orderId");
  if (!/^[A-Za-z0-9-]{3,32}$/.test(orderId)) {
    throw new ValidationError("orderId may contain letters, digits and dashes only (3-32 characters)");
  }
  return {
    orderId,
    customerId: requireString(obj, "customerId"),
    billingCountry: requireCountry(obj, "billingCountry"),
    items: requireLines(obj, "items"),
    couponCode: requireCouponCode(obj, "couponCode"),
    issueDate: requireDate(obj, "issueDate"),
  };
}
