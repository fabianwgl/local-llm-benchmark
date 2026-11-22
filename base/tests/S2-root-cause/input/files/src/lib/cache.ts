type Entry = { value: unknown; expiresAt: number };

const store = new Map<string, Entry>();

/** Return the cached value for `key`, or run `loader`, cache its result for `ttlMs`, and return it. */
export async function getOrSet<T>(key: string, ttlMs: number, loader: () => Promise<T>): Promise<T> {
  const now = Date.now();
  const hit = store.get(key);
  if (hit && hit.expiresAt > now) {
    return hit.value as T;
  }
  const value = await loader();
  store.set(key, { value, expiresAt: now + ttlMs });
  return value;
}

export function invalidate(key: string): void {
  store.delete(key);
}

export function size(): number {
  return store.size;
}
