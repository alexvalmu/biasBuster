import { Folder, INK, INK_2, ORANGE, PAPER } from "./Folder";

const STROKE = {
  fill: "none",
  stroke: INK,
  strokeWidth: 1.5,
  strokeLinejoin: "round" as const,
  strokeLinecap: "round" as const,
};
const SANS = "Satoshi, sans-serif";

type ArtProps = { className?: string; tilt?: number };

/** A paper with its Funding / COI lines highlighted, under a magnifying glass. */
export function ParseArt(props: ArtProps) {
  return (
    <Folder color="mint" title="DISCLOSURES" subtitle="read what they declare" {...props}>
      <g {...STROKE}>
        <path d="M44 78 H170 L196 104 V272 H44 Z" fill={PAPER} />
        <path d="M170 78 V104 H196" />
        <path d="M58 96 H140 M58 108 H124" strokeWidth="3" />
        <path d="M58 126 H178 M58 136 H170 M58 146 H176 M58 156 H150" strokeOpacity=".35" />
        <path d="M58 196 H178 M58 206 H164 M58 248 H170 M58 258 H140" strokeOpacity=".35" />
      </g>
      <g fontFamily={SANS} fontSize="6.5" fill={INK_2}>
        <text x="58" y="176">FUNDING</text>
        <text x="58" y="228">COMPETING INTERESTS</text>
      </g>
      <rect x="56" y="181" width="104" height="8" rx="2" fill={ORANGE} fillOpacity=".35" />
      <rect x="56" y="233" width="80" height="8" rx="2" fill={ORANGE} fillOpacity=".35" />
      <g {...STROKE}>
        <path d="M58 185 H156 M58 237 H132" />
        <circle cx="168" cy="214" r="24" fill={PAPER} fillOpacity=".55" strokeWidth="2" />
        <path d="M185 231 L204 250" strokeWidth="5" />
      </g>
      <g className="pulse">
        <circle cx="168" cy="214" r="4" fill={ORANGE} />
      </g>
    </Folder>
  );
}

/** One author connected to the organisations around them; one edge leads to industry. */
export function InvestigateArt(props: ArtProps) {
  const nodes = [
    { x: 74, y: 112, label: "university" },
    { x: 172, y: 112, label: "pharma" },
    { x: 74, y: 236, label: "nih grant" },
    { x: 172, y: 236, label: "device co" },
  ];
  return (
    <Folder color="blue" title="FOLLOW THE MONEY" subtitle="one agent per author" {...props}>
      <g {...STROKE}>
        <rect x="28" y="72" width="184" height="204" rx="8" fill={PAPER} />
        <path d="M120 174 L74 112 M120 174 L74 236 M120 174 L172 236" strokeOpacity=".5" />
        <path d="M120 174 L172 112" stroke={ORANGE} strokeWidth="2" strokeDasharray="4 3" />
        {nodes.map((n) => (
          <rect key={n.label} x={n.x - 30} y={n.y - 9} width="60" height="18" rx="4" fill={PAPER} />
        ))}
        <circle cx="120" cy="174" r="17" fill={INK} />
      </g>
      <g fontFamily={SANS} fontSize="6.5" fill={INK_2} textAnchor="middle">
        {nodes.map((n) => (
          <text key={n.label} x={n.x} y={n.y + 2.5}>
            {n.label}
          </text>
        ))}
      </g>
      <g fill={PAPER}>
        <circle cx="120" cy="168" r="5" />
        <path d="M110 184 C110 176 130 176 130 184 Z" />
      </g>
      <g fontFamily={SANS} fontSize="6" fill={INK_2}>
        <text x="40" y="88">$ query openalex orcid pubmed</text>
        <text x="40" y="266">$ match affiliation ✓</text>
      </g>
      <g className="pulse">
        <circle cx="146" cy="143" r="4.5" fill={ORANGE} />
      </g>
    </Folder>
  );
}

/** A dial and a checklist where every line carries a link. */
export function ReportArt(props: ArtProps) {
  return (
    <Folder color="violet" title="EVIDENCE" subtitle="every claim, a link" {...props}>
      <g {...STROKE}>
        <rect x="36" y="72" width="168" height="204" rx="8" fill={PAPER} />
      </g>
      <Dial cx={120} cy={148} r={52} score={64} />
      <g {...STROKE}>
        {[196, 220, 244].map((y) => (
          <g key={y}>
            <rect x="54" y={y - 6} width="10" height="10" rx="2" fill={y === 220 ? INK : PAPER} />
            <path d={`M72 ${y - 1} H${y === 244 ? 138 : 158}`} strokeOpacity=".35" />
            <path d={`M170 ${y - 3} l4 -4 a3 3 0 0 1 4 4 l-4 4 M174 ${y + 1} l-4 4 a3 3 0 0 1 -4 -4 l4 -4`} strokeWidth="1.2" />
          </g>
        ))}
      </g>
    </Folder>
  );
}

/** A semicircular gauge. Pure SVG, reused by the report cover. */
export function Dial({ cx, cy, r, score }: { cx: number; cy: number; r: number; score: number }) {
  const angle = Math.PI * (1 - Math.min(100, Math.max(0, score)) / 100);
  const nx = cx + (r - 12) * Math.cos(angle);
  const ny = cy - (r - 12) * Math.sin(angle);
  const ticks = Array.from({ length: 11 }, (_, i) => {
    const a = Math.PI * (1 - i / 10);
    const inner = i % 5 === 0 ? r - 10 : r - 6;
    return `M${cx + inner * Math.cos(a)} ${cy - inner * Math.sin(a)} L${cx + r * Math.cos(a)} ${cy - r * Math.sin(a)}`;
  }).join(" ");
  return (
    <g>
      <g {...STROKE}>
        <path d={`M${cx - r} ${cy} A${r} ${r} 0 0 1 ${cx + r} ${cy}`} strokeWidth="2" />
        <path d={ticks} strokeOpacity=".6" />
        <path d={`M${cx} ${cy} L${nx} ${ny}`} strokeWidth="2.5" />
        <circle cx={cx} cy={cy} r="4" fill={INK} />
      </g>
      <g className="pulse">
        <circle cx={nx} cy={ny} r="4.5" fill={ORANGE} />
      </g>
      <g fontFamily={SANS} fontSize="6.5" fill={INK_2}>
        <text x={cx - r} y={cy + 12} textAnchor="middle">0</text>
        <text x={cx + r} y={cy + 12} textAnchor="middle">100</text>
      </g>
    </g>
  );
}

/** Empty folder with a paper sliding in: the upload target. */
export function UploadArt(props: ArtProps) {
  return (
    <Folder color="mint" title="YOUR PAPER" subtitle="drop the pdf here" {...props}>
      <g {...STROKE}>
        <path d="M60 110 H160 L184 134 V262 H60 Z" fill={PAPER} />
        <path d="M160 110 V134 H184" />
        <path d="M76 160 H168 M76 172 H160 M76 184 H166 M76 196 H140" strokeOpacity=".35" />
        <path d="M122 214 V250 M108 236 L122 250 L136 236" strokeWidth="2" />
      </g>
      <text x="76" y="146" fontFamily="Doto, monospace" fontWeight="800" fontSize="13" fill={INK}>
        PDF
      </text>
      <g className="pulse">
        <circle cx="122" cy="256" r="4" fill={ORANGE} />
      </g>
    </Folder>
  );
}
