import { logger } from "./logger.ts";

/** Wait for `promise`, but give up after `ms` milliseconds. */
export function withTimeout<T>(promise: Promise<T>, ms: number, label = "operation"): Promise<T | undefined> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      logger.warn(`${label}: timeout after ${ms}ms`);
      resolve(undefined);
    }, ms);
    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (error) => {
        clearTimeout(timer);
        reject(error);
      },
    );
  });
}
