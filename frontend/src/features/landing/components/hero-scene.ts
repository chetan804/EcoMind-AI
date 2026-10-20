/**
 * Geometry for the landing hero illustration. Everything is authored in "scene units": the
 * coordinate system of the design reference's hero (a 4.99x enlargement of its native crop),
 * which HeroArt maps onto the 1440 x 770 page region. Keeping the numbers here keeps the
 * component readable and makes the composition easy to tune.
 */

export interface Tower {
  x: number;
  width: number;
  top: number;
  /** y of the antenna tip; omitted when the tower has no antenna. */
  spire?: number;
  /** 0 = far and hazy, 1 = near and crisp. */
  depth: number;
  kind?: 'glass' | 'garden' | 'pale' | 'roof-garden';
}

export const towers: Tower[] = [
  { x: 372, width: 40, top: 500, depth: 0.2 },
  { x: 432, width: 90, top: 432, depth: 0.35 },
  { x: 555, width: 90, top: 392, spire: 290, depth: 0.5 },
  { x: 642, width: 34, top: 425, depth: 0.5 },
  { x: 668, width: 30, top: 500, depth: 0.3 },
  { x: 700, width: 78, top: 418, depth: 0.55 },
  { x: 972, width: 64, top: 285, spire: 208, depth: 0.55 },
  { x: 795, width: 104, top: 265, spire: 185, depth: 0.85 },
  { x: 1087, width: 92, top: 228, spire: 130, depth: 0.8 },
  { x: 1200, width: 96, top: 275, depth: 0.25, kind: 'pale' },
  { x: 1322, width: 170, top: 75, spire: 18, depth: 1, kind: 'garden' },
  { x: 1445, width: 150, top: 388, depth: 0.9, kind: 'roof-garden' },
];

/** Deterministic pseudo-random generator, so the scene is identical on every render. */
export function seeded(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export const globe = { cx: 1165, cy: 595, r: 265 };

export interface Canopy {
  x: number;
  y: number;
  r: number;
  /** 0 = distant and desaturated, 1 = near and rich. */
  depth: number;
}

function row(seed: number, from: number, to: number, y: number, rMin: number, rMax: number, step: number, depth: number): Canopy[] {
  const rand = seeded(seed);
  const out: Canopy[] = [];
  for (let x = from; x < to; x += step * (0.7 + rand() * 0.6)) {
    out.push({ x, y: y + (rand() - 0.5) * 36, r: rMin + rand() * (rMax - rMin), depth });
  }
  return out;
}

/** The globe stands clear above the foliage, as in the reference: no canopies across its lower half. */
const clearOfGlobe = (t: Canopy) => !(t.x > globe.cx - globe.r * 0.95 && t.x < globe.cx + globe.r * 0.98 && t.y - t.r < 790);

export const backTrees: Canopy[] = row(11, -600, 1600, 650, 34, 58, 62, 0.35).filter(clearOfGlobe);
export const midTrees: Canopy[] = row(23, -480, 1600, 715, 42, 72, 84, 0.65).filter(clearOfGlobe);

/** Large trees in the foreground, placed by hand to frame the scene as the reference does. */
export const frontTrees: Canopy[] = [
  { x: 230, y: 690, r: 92, depth: 1 },
  { x: 120, y: 720, r: 74, depth: 1 },
  { x: -60, y: 700, r: 96, depth: 1 },
  { x: 350, y: 770, r: 46, depth: 1 },
    { x: 1400, y: 735, r: 74, depth: 1 },
  { x: 1500, y: 700, r: 92, depth: 1 },
  { x: 1555, y: 610, r: 58, depth: 1 },
];


/** Jittered ridge line between key points, so slopes are ragged rather than ruler-straight. */
export function ridgePath(points: Array<[number, number]>, seed: number, jitter: number, parts = 7): string {
  const rand = seeded(seed);
  const out: string[] = [];
  let prev: [number, number] | undefined;
  for (const point of points) {
    const [x, y] = point;
    if (prev === undefined) {
      out.push(`${x} ${y}`);
    } else {
      const [px, py] = prev;
      for (let k = 1; k <= parts; k += 1) {
        const t = k / parts;
        const wobble = k === parts ? 0 : jitter;
        out.push(`${(px + (x - px) * t + (rand() - 0.5) * wobble).toFixed(1)} ${(py + (y - py) * t + (rand() - 0.5) * wobble).toFixed(1)}`);
      }
    }
    prev = point;
  }
  return out.join(' L');
}

/** Dark forest bumps on the near mountain's lower slope. */
export const slopeForest: Canopy[] = (() => {
  const rand = seeded(5);
  const out: Canopy[] = [];
  for (let i = 0; i < 46; i += 1) {
    const y = 250 + rand() * 330;
    const x = -200 + rand() * (330 + (y - 250) * 0.55) + (y - 250) * 0.2;
    out.push({ x, y, r: 16 + rand() * 20, depth: 0.2 + rand() * 0.3 });
  }
  return out;
})();
