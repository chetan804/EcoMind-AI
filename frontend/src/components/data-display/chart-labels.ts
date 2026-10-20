/** Roughly the width one date label needs, in px; labels closer than this are dropped. */
const LABEL_SLOT = 72;

/**
 * Indexes of the x labels to draw. The first and last label always show; the ones between are
 * thinned evenly so text never overlaps (the data table still lists every period).
 */
export function visibleLabelIndexes(labels: string[], innerWidth: number): number[] {
  const n = labels.length;
  if (n <= 2) return labels.map((_, i) => i);
  const fit = Math.max(Math.floor(innerWidth / LABEL_SLOT), 2);
  if (n <= fit) return labels.map((_, i) => i);
  const step = Math.ceil((n - 1) / (fit - 1));
  const picked: number[] = [];
  for (let i = 0; i < n - 1; i += step) picked.push(i);
  // keep a gap before the final label
  if (picked.length > 1 && (n - 1 - (picked[picked.length - 1] ?? 0)) * (innerWidth / (n - 1)) < LABEL_SLOT * 0.8) picked.pop();
  picked.push(n - 1);
  return picked;
}
