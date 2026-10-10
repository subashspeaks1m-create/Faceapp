import { CATALOG } from './catalog.generated.ts';
import type { CategoryId, IntensityBand, StyleInfo } from './types.ts';

export { CATALOG };

export function styleById(id: string): StyleInfo | undefined {
  return CATALOG.styles.find((s) => s.id === id);
}

export function categoryName(id: CategoryId): string {
  return CATALOG.categories.find((c) => c.id === id)?.name ?? id;
}

export function bandFor(intensity: number): IntensityBand {
  const v = Math.max(0, Math.min(100, Math.round(intensity)));
  const band = CATALOG.intensity_bands.find((b) => v >= b.min && v <= b.max);
  if (band === undefined) throw new RangeError('intensity bands do not cover 0..100');
  return band;
}

function normalize(text: string): string {
  return text.toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '');
}

// Every word of the query must match the style's name, summary, tags or category name.
export function filterStyles(query: string, category: CategoryId | 'all'): readonly StyleInfo[] {
  const words = normalize(query).split(/\s+/).filter((w) => w.length > 0);
  return CATALOG.styles.filter((s) => {
    if (category !== 'all' && s.category !== category) return false;
    if (words.length === 0) return true;
    const haystack = normalize([s.name, s.summary, categoryName(s.category), ...s.tags].join(' '));
    return words.every((w) => haystack.includes(w));
  });
}
