export const COARSE_POINTER_QUERY = '(any-pointer: coarse)';

export interface MediaQueryResultLike {
  matches: boolean;
}

export type MatchMediaFn = (query: string) => MediaQueryResultLike;

/**
 * Mengembalikan true bila perangkat memiliki perangkat penunjuk sentuh (coarse pointer).
 */
export function isCoarsePointerDevice(matchMediaFn?: MatchMediaFn | null): boolean {
  const fn =
    matchMediaFn === undefined
      ? typeof window !== 'undefined' && typeof window.matchMedia === 'function'
        ? (q: string) => window.matchMedia(q)
        : null
      : matchMediaFn;

  if (!fn) return false;
  try {
    return Boolean(fn(COARSE_POINTER_QUERY)?.matches);
  } catch {
    return false;
  }
}
