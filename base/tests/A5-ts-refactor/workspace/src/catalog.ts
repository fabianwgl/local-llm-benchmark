import type { Product } from "./types.ts";

// The catalogue is small and changes rarely, so it lives in code. Prices are net (before tax).
const PRODUCTS: readonly Product[] = [
  { sku: "KB-101", name: "Mechanical keyboard", priceCents: 8990, category: "peripherals", active: true },
  { sku: "MS-220", name: "Wireless mouse", priceCents: 2495, category: "peripherals", active: true },
  { sku: "PAD-XL", name: "Desk pad XL", priceCents: 1990, category: "accessories", active: true },
  { sku: "MON-27", name: "27-inch monitor", priceCents: 27900, category: "displays", active: true },
  { sku: "ARM-2", name: "Dual monitor arm", priceCents: 6475, category: "displays", active: true },
  { sku: "CAM-HD", name: "HD webcam", priceCents: 5995, category: "peripherals", active: true },
  { sku: "HS-PRO", name: "Headset Pro", priceCents: 12999, category: "audio", active: true },
  { sku: "SPK-MINI", name: "Mini speaker", priceCents: 3333, category: "audio", active: true },
  { sku: "SSD-1T", name: "Portable SSD 1 TB", priceCents: 8449, category: "storage", active: true },
  { sku: "USB-64", name: "USB stick 64 GB", priceCents: 1105, category: "storage", active: true },
  { sku: "CB-USBC", name: "USB-C cable 1 m", priceCents: 799, category: "cables", active: true },
  { sku: "CB-HDMI", name: "HDMI cable 2 m", priceCents: 1149, category: "cables", active: true },
  { sku: "HUB-7", name: "7-port USB hub", priceCents: 3450, category: "peripherals", active: true },
  { sku: "LBL-100", name: "Cable labels (100)", priceCents: 365, category: "accessories", active: true },
  { sku: "TIE-50", name: "Cable ties (50)", priceCents: 233, category: "accessories", active: true },
  { sku: "WIPE-20", name: "Screen wipes (20)", priceCents: 451, category: "accessories", active: true },
  { sku: "KB-90", name: "Membrane keyboard", priceCents: 2990, category: "peripherals", active: false },
];

const BY_SKU = new Map(PRODUCTS.map((p) => [p.sku, p]));

export function getProduct(sku: string): Product | undefined {
  return BY_SKU.get(sku);
}

export function listProducts(options: { category?: string; includeInactive?: boolean } = {}): Product[] {
  return PRODUCTS.filter(
    (p) => (options.includeInactive || p.active) && (!options.category || p.category === options.category),
  );
}

export function categories(): string[] {
  return [...new Set(PRODUCTS.map((p) => p.category))].sort();
}
