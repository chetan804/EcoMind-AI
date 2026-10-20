import { backTrees, frontTrees, globe, midTrees, ridgePath, seeded, slopeForest, towers, type Canopy, type Tower } from './hero-scene';

/**
 * Original hero illustration, composed to follow the design reference: a sunlit green mountain,
 * hazy peaks, glass towers (one with a vertical garden), a moss-covered globe carrying the
 * recycling mark, a collection truck, trees, a lawn and a road. Decorative only (aria-hidden).
 *
 * It is vector art authored for this project, not a trace or copy of the reference photograph.
 * Layers run back to front; geometry lives in `hero-scene.ts`. The scene units map onto the
 * 1440 x 770 hero region with `translate(391 57) scale(0.669)`.
 */

function Skyscraper({ tower }: { tower: Tower }) {
  const { x, width, top, spire, depth, kind = 'glass' } = tower;
  const bottom = 700;
  const height = bottom - top;
  const fill = kind === 'pale' ? 'url(#hero-glass-pale)' : kind === 'garden' || kind === 'roof-garden' ? 'url(#hero-glass-green)' : 'url(#hero-glass)';
  return (
    <g opacity={0.55 + depth * 0.45}>
      {spire !== undefined && <path d={`M${x + width / 2} ${top} V${spire}`} stroke="#a9c1c4" strokeWidth={3} />}
      <rect x={x} y={top} width={width} height={height} fill={fill} />
      <rect x={x} y={top} width={width} height={height} fill="url(#hero-windows)" opacity={0.7} />
      <rect x={x} y={top} width={width} height={5} fill="#d5ecea" opacity={0.55} />
      <rect x={x + width * 0.62} y={top} width={width * 0.38} height={height} fill="#06222b" opacity={0.22} />
      {kind === 'garden' && (
        <g fill="#4aa043" opacity={0.7}>
          {[8, 30, 62, 88, 124, 146].map((dx, i) => (
            <rect key={dx} x={x + dx} y={top + 40 + (i % 3) * 22} width={11} height={190 + (i % 2) * 90} rx={5} />
          ))}
          <rect x={x + 6} y={top - 6} width={width - 12} height={14} rx={7} fill="#3a8a35" />
        </g>
      )}
      {kind === 'roof-garden' && <path d={`M${x} ${top + 4} q${width * 0.15} -30 ${width * 0.3} -10 q${width * 0.2} -26 ${width * 0.4} -4 q${width * 0.15} -16 ${width * 0.3} 14Z`} fill="#4a9a3a" />}
    </g>
  );
}

const FOLIAGE = {
  far: { dark: '#3d7a52', light: '#6aa67a' },
  mid: { dark: '#2a6f2e', light: '#5ba844' },
  near: { dark: '#1c5f27', light: '#4aa83c' },
};

const foliageFor = (depth: number) => (depth > 0.8 ? FOLIAGE.near : depth > 0.5 ? FOLIAGE.mid : FOLIAGE.far);

/** Each canopy is a cluster of overlapping lobes, lit from the upper left. */
function Canopies({ trees, id }: { trees: Canopy[]; id: string }) {
  return (
    <g>
      {trees.map((t, i) => {
        const palette = foliageFor(t.depth);
        const rand = seeded(i * 97 + Math.round(t.x));
        return (
          <g key={`${id}-${i}`}>
            <circle cx={t.x} cy={t.y + t.r * 0.08} r={t.r} fill={palette.dark} />
            {Array.from({ length: 7 }, (_, k) => {
              const angle = rand() * Math.PI * 2;
              const dist = rand() * t.r * 0.55;
              const lit = Math.cos(angle - Math.PI * 1.25);
              return (
                <circle
                  key={k}
                  cx={t.x + Math.cos(angle) * dist}
                  cy={t.y + Math.sin(angle) * dist}
                  r={t.r * (0.28 + rand() * 0.22)}
                  fill={lit > 0.1 ? palette.light : palette.dark}
                  opacity={0.55 + rand() * 0.4}
                />
              );
            })}
            <circle cx={t.x - t.r * 0.34} cy={t.y - t.r * 0.36} r={t.r * 0.3} fill="#a6dc62" opacity={0.15 + t.depth * 0.3} />
          </g>
        );
      })}
    </g>
  );
}

/** Three chunky chasing arrows forming a triangle. Drawn as shapes so the colour and weight match the scene. */
function RecycleMark({ cx, cy }: { cx: number; cy: number }) {
  const arrow = 'M-56 -15 H10 V-34 L62 0 L10 34 V15 H-56 Z';
  return (
    <g transform={`translate(${cx} ${cy}) scale(1.42)`}>
      {[0, 120, 240].map((angle) => (
        <g key={angle} transform={`rotate(${angle})`}>
          <g transform="translate(49 -30) rotate(60)">
            <path d={arrow} fill="#0c4a2c" opacity={0.55} transform="translate(4 5)" />
            <path d={arrow} fill="url(#hero-arrow)" stroke="#a6f0b5" strokeOpacity={0.55} strokeWidth={1.5} strokeLinejoin="round" />
          </g>
        </g>
      ))}
    </g>
  );
}

function Truck() {
  return (
    <g>
      <ellipse cx={700} cy={846} rx={300} ry={20} fill="#050c10" opacity={0.6} />
      {/* rear hopper */}
      <path d="M440 700 H592 V790 H440 Z" fill="#1b6a30" />
      <path d="M440 700 H592 V716 H440 Z" fill="#2f8c45" />
      <path d="M436 716 q12 -30 28 -16 v90 h-28Z" fill="#3a8f7a" opacity={0.7} />
      {/* main container */}
      <rect x={672} y={640} width={222} height={146} rx={8} fill="url(#hero-truck)" />
      <rect x={672} y={640} width={222} height={12} rx={6} fill="#47a35a" opacity={0.85} />
      <path d="M752 652 V780 M826 652 V780" stroke="#0d4f22" strokeWidth={3} opacity={0.6} />
      <circle cx={783} cy={712} r={20} fill="#0f5a2a" stroke="#cdf5d6" strokeOpacity={0.8} strokeWidth={3} />
      <path d="M775 706 l8 -9 l8 9 M776 722 l-6 -6 M796 722 l6 -6" stroke="#cdf5d6" strokeWidth={3} strokeLinecap="round" fill="none" />
      {/* white cab module */}
      <path d="M588 656 q0 -10 10 -10 H672 V786 H588Z" fill="#eef1ee" />
      <rect x={602} y={668} width={50} height={56} rx={9} fill="#2f4752" />
      <rect x={606} y={672} width={20} height={48} rx={7} fill="#6f93a3" opacity={0.55} />
      <rect x={588} y={756} width={84} height={30} fill="#d5dad6" />
      {/* nose */}
      <path d="M894 668 H938 q24 6 24 40 V782 H894Z" fill="#1f7a37" />
      <path d="M912 682 H936 q10 4 10 26 H912Z" fill="#a3d6df" opacity={0.75} />
      <rect x={894} y={768} width={72} height={20} rx={4} fill="#11191c" />
      {/* undercarriage + wheels */}
      <rect x={436} y={782} width={530} height={14} fill="#0c1417" />
      {[550, 734, 880].map((wx) => (
        <g key={wx}>
          <circle cx={wx} cy={808} r={34} fill="#0b1114" />
          <circle cx={wx} cy={808} r={15} fill="#6d7f86" />
          <circle cx={wx} cy={808} r={6} fill="#10181b" />
        </g>
      ))}
    </g>
  );
}

export function HeroArt() {
  const { cx, cy, r } = globe;
  return (
    <svg className="hero-art" viewBox="0 0 1440 770" preserveAspectRatio="xMaxYMax slice" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="hero-sky" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#1c62ac" />
          <stop offset="0.3" stopColor="#4a97d3" />
          <stop offset="0.58" stopColor="#a8d1ec" />
          <stop offset="0.8" stopColor="#d9e9ec" />
        </linearGradient>
        <radialGradient id="hero-glow" cx="0.72" cy="0.3" r="0.4">
          <stop offset="0" stopColor="#fff6e0" stopOpacity="0.8" />
          <stop offset="1" stopColor="#fff6e0" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="hero-mountain" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stopColor="#123f17" />
          <stop offset="0.6" stopColor="#2c7125" />
          <stop offset="1" stopColor="#4c9a30" />
        </linearGradient>
        <linearGradient id="hero-far" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#5f87a6" />
          <stop offset="1" stopColor="#b9d3df" />
        </linearGradient>
        <linearGradient id="hero-glass" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stopColor="#8fbdb7" />
          <stop offset="1" stopColor="#2f6468" />
        </linearGradient>
        <linearGradient id="hero-glass-green" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stopColor="#56a08a" />
          <stop offset="1" stopColor="#1f5e55" />
        </linearGradient>
        <linearGradient id="hero-glass-pale" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stopColor="#b7d5df" />
          <stop offset="1" stopColor="#7aa3b4" />
        </linearGradient>
        <pattern id="hero-windows" width="11" height="14" patternUnits="userSpaceOnUse">
          <path d="M0 13.5H11M10.5 0V14" stroke="#d9f1ee" strokeOpacity="0.38" strokeWidth="1" />
        </pattern>
        <linearGradient id="hero-haze" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#cfe5ea" stopOpacity="0" />
          <stop offset="1" stopColor="#cfe5ea" stopOpacity="0.5" />
        </linearGradient>
        <radialGradient id="hero-globe-sea" cx="0.62" cy="0.3" r="0.8">
          <stop offset="0" stopColor="#d3ecf7" />
          <stop offset="0.3" stopColor="#5aa2cc" />
          <stop offset="0.7" stopColor="#1d5a7c" />
          <stop offset="1" stopColor="#0c2f40" />
        </radialGradient>
        <clipPath id="hero-globe-clip">
          <circle cx={cx} cy={cy} r={r} />
        </clipPath>
        <linearGradient id="hero-arrow" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0" stopColor="#5fe58a" />
          <stop offset="1" stopColor="#1f9d4d" />
        </linearGradient>
        <linearGradient id="hero-truck" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#2a8a40" />
          <stop offset="1" stopColor="#14602a" />
        </linearGradient>
        <linearGradient id="hero-road" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#1f2e35" />
          <stop offset="1" stopColor="#0a1317" />
        </linearGradient>
        <linearGradient id="hero-lawn" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#7fbf3f" />
          <stop offset="1" stopColor="#3d8a2c" />
        </linearGradient>
        <filter id="hero-soft" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="7" />
        </filter>
      </defs>

      <rect width="1440" height="770" fill="url(#hero-sky)" />
      <rect width="1440" height="770" fill="url(#hero-glow)" />

      <g transform="translate(391 57) scale(0.669)">
        {/* clouds */}
        <g fill="#ffffff" filter="url(#hero-soft)" opacity={0.85}>
          <circle cx={1050} cy={175} r={62} />
          <circle cx={1125} cy={128} r={72} />
          <circle cx={1215} cy={96} r={58} />
          <circle cx={1310} cy={88} r={46} />
          <ellipse cx={1330} cy={118} rx={80} ry={22} />
          <ellipse cx={1100} cy={8} rx={70} ry={20} />
          <ellipse cx={1530} cy={140} rx={50} ry={16} />
        </g>

        {/* distant ridges */}
        <path d="M1270 330 L1330 262 L1420 240 L1568 222 V470 H1270Z" fill="url(#hero-far)" opacity={0.7} />
        <path d="M655 340 L720 318 L790 372 L800 470 H655Z" fill="url(#hero-far)" opacity={0.55} />
        <path d="M300 205 L380 175 L455 146 L500 205 L560 292 L640 352 L820 440 L820 560 H300Z" fill="url(#hero-far)" />
        <path d="M455 146 L500 205 L560 292 L520 270 L470 190Z" fill="#e5eef2" opacity={0.35} />

        {/* near mountain, left: ragged ridge plus forest texture */}
        <path d={`M-600 -80 L${ridgePath([[90, -80], [190, 70], [300, 215], [400, 300], [470, 470]], 3, 22)} L330 600 H-600Z`} fill="url(#hero-mountain)" />
        <path d={`M${ridgePath([[90, -80], [190, 70], [300, 215], [400, 300], [470, 470]], 3, 22)}`} stroke="#9fd460" strokeOpacity="0.4" strokeWidth={4} fill="none" />
        <path d="M-200 150 L60 90 L180 210 L320 330 L-200 330Z" fill="#0e3512" opacity={0.3} />
        <g opacity={0.75}>
          {slopeForest.map((t, i) => (
            <circle key={i} cx={t.x} cy={t.y} r={t.r} fill={i % 3 === 0 ? '#2f7a2c' : '#164a1c'} opacity={0.55} />
          ))}
        </g>

        {/* haze behind the city */}
        <rect x={300} y={380} width={1300} height={300} fill="url(#hero-haze)" />

        {/* towers, far to near */}
        {[...towers].sort((a, b) => a.depth - b.depth).map((tower) => (
          <Skyscraper key={tower.x} tower={tower} />
        ))}
        <rect x={300} y={520} width={1300} height={180} fill="url(#hero-haze)" opacity={0.6} />

        {/* globe */}
        <circle cx={cx} cy={cy} r={r} fill="url(#hero-globe-sea)" />
        <g clipPath="url(#hero-globe-clip)">
          <g fill="#ffffff" opacity={0.55} filter="url(#hero-soft)">
            <ellipse cx={1215} cy={400} rx={105} ry={38} />
            <ellipse cx={1320} cy={470} rx={70} ry={26} />
          </g>
          <path d="M890 520 C896 430 955 378 1040 352 C1010 398 988 432 998 472 C1010 522 962 560 978 620 C988 672 940 704 922 694 C902 640 886 580 890 520Z" fill="#2e7d2b" />
          <path d="M1040 352 C1100 322 1192 316 1262 342 C1304 356 1344 380 1370 424 C1322 402 1282 396 1240 408 C1190 418 1150 396 1100 402 C1068 404 1050 386 1040 352Z" fill="#43962f" />
          <path d="M1370 424 C1405 470 1428 540 1418 610 C1400 560 1380 520 1352 498 C1368 470 1372 446 1370 424Z" fill="#2f7e3a" opacity={0.85} />
          <path d="M930 640 C1000 700 1100 765 1200 772 C1310 778 1395 722 1430 630 L1440 900 L900 900Z" fill="#1c4a37" />
          <g fill="#6fbf4f" opacity={0.75}>
            <ellipse cx={1330} cy={555} rx={24} ry={14} />
            <ellipse cx={1385} cy={505} rx={18} ry={11} />
            <ellipse cx={1010} cy={440} rx={26} ry={16} />
            <ellipse cx={1060} cy={395} rx={32} ry={12} />
          </g>
          <circle cx={cx} cy={cy} r={r - 3} fill="none" stroke="#9fe0a0" strokeOpacity={0.25} strokeWidth={6} />
        </g>
        <RecycleMark cx={1162} cy={585} />

        {/* trees and lawn */}
        <Canopies trees={backTrees} id="back" />
        <Canopies trees={midTrees} id="mid" />
        <path d="M-600 770 H1568 V840 H-600Z" fill="url(#hero-lawn)" />
        <path d="M-600 810 H1568 V1200 H-600Z" fill="url(#hero-road)" />
        <path d="M-600 806 H1568" stroke="#050b0e" strokeWidth={8} opacity={0.5} />

        <Truck />

        <Canopies trees={frontTrees} id="front" />
        <path d="M1400 975 C1420 930 1480 880 1568 862 V1000Z" fill="url(#hero-lawn)" />
      </g>
    </svg>
  );
}
