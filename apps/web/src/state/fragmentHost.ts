import type { Entity } from "./types";

function fold(value: string): string {
  return value
    .normalize("NFKC")
    .replace(/İ/g, "i")
    .replace(/I/g, "ı")
    .toLocaleLowerCase("tr-TR")
    .trim();
}

/** The shortest other finding on the same page that already covers this span. */
export function fragmentHost(entity: Entity, entities: Entity[]): Entity | null {
  const length = entity.end - entity.start;
  if (length <= 0) return null;
  let best: Entity | null = null;
  let bestSpan = Number.POSITIVE_INFINITY;
  const fragment = fold(entity.text);
  for (const other of entities) {
    if (other.id === entity.id || other.page !== entity.page) continue;
    const span = other.end - other.start;
    if (span <= length) continue;
    const contains = other.start <= entity.start && other.end >= entity.end;
    const overlaps = other.start < entity.end && entity.start < other.end;
    if (!contains && !overlaps) continue;
    if (!contains && (!fragment || !fold(other.text).includes(fragment))) continue;
    if (span < bestSpan) {
      best = other;
      bestSpan = span;
    }
  }
  return best;
}
