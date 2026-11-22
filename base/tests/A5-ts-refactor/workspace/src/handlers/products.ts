import { categories, getProduct, listProducts } from "../catalog.ts";
import { CURRENCY } from "../config.ts";
import { NotFoundError, ValidationError } from "../errors.ts";
import { formatCents } from "../format.ts";
import { ok } from "../http.ts";
import type { ApiRequest, ApiResponse, Product } from "../types.ts";
import { volumeTiers } from "../volume.ts";

interface ProductView {
  sku: string;
  name: string;
  category: string;
  priceCents: number;
  price: string;
}

function view(p: Product): ProductView {
  return { sku: p.sku, name: p.name, category: p.category, priceCents: p.priceCents, price: formatCents(p.priceCents) };
}

/** GET /products?category=audio */
export function listProductsHandler(req: ApiRequest): ApiResponse {
  const category = req.query?.category;
  if (category !== undefined && !categories().includes(category)) {
    throw new ValidationError(`unknown category ${category}; expected one of ${categories().join(", ")}`);
  }
  const products = listProducts({ category }).map(view);
  return ok({ currency: CURRENCY, count: products.length, products });
}

/** GET /products/:sku */
export function getProductHandler(_req: ApiRequest, params: Record<string, string>): ApiResponse {
  const product = getProduct(params.sku);
  if (!product || !product.active) {
    throw new NotFoundError(`no product ${params.sku}`);
  }
  return ok({ ...view(product), volumeTiers: volumeTiers() });
}
