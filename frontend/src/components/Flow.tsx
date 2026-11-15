import type { ReactElement } from "react";
import { InvestigateArt, ParseArt, ReportArt, UploadArt } from "./Illustrations";

type ArtFn = (props: { className?: string; tilt?: number }) => ReactElement;
type Link = "straight" | "fork" | "merge";

type Step = {
  art: ArtFn;
  kicker: string;
  title: string;
  text: string;
  /** Connector drawn after this step, and what travels along it. */
  next?: { kind: Link; label: string };
};

export const STEPS: Step[] = [
  {
    art: UploadArt,
    kicker: "01 · Upload",
    title: "Your PDF",
    text: "We hash it and keep only the hash.",
    next: { kind: "straight", label: "text" },
  },
  {
    art: ParseArt,
    kicker: "02 · Parse",
    title: "Read the disclosures",
    text: "Authors, funding and competing interests, verbatim.",
    next: { kind: "fork", label: "N authors + funders" },
  },
  {
    art: InvestigateArt,
    kicker: "03 · Investigate",
    title: "Follow the money",
    text: "One agent per author, one for funders, in parallel.",
    next: { kind: "merge", label: "evidence + links" },
  },
  {
    art: ReportArt,
    kicker: "04 · Report",
    title: "Evidence, not opinions",
    text: "A fixed report and a score computed by rules.",
  },
];

const ENDS: Record<Link, number[]> = { straight: [40], fork: [14, 40, 66], merge: [40] };

/** Wire between two folders: it stretches to fill the gap, the arrowheads keep their shape. */
function Connector({ kind, label, state }: { kind: Link; label: string; state: string }) {
  return (
    <div className={`flow-link ${state}`} aria-hidden>
      <span className="flow-link-label">{label}</span>
      <div className="flow-wire">
        <svg className="flow-lines" viewBox="0 0 112 80" preserveAspectRatio="none">
          {kind === "straight" && <path d="M0 40 H112" />}
          {kind === "fork" &&
            [14, 40, 66].map((y) => <path key={y} d={`M0 40 H30 C58 40 62 ${y} 90 ${y} H112`} />)}
          {kind === "merge" &&
            [14, 40, 66].map((y) => <path key={y} d={`M0 ${y} H22 C50 ${y} 54 40 82 40 H112`} />)}
        </svg>
        <svg className="flow-heads" viewBox="0 0 8 80">
          {ENDS[kind].map((y) => (
            <path key={y} d={`M0 ${y - 4} L8 ${y} L0 ${y + 4} Z`} />
          ))}
        </svg>
      </div>
    </div>
  );
}

/**
 * The pipeline drawn as a roadmap: folders on one row joined by arrows, captions below.
 * `active` highlights the running step (progress page); omit it for the static explainer.
 */
export function Flow({ active }: { active?: number }) {
  const stepState = (i: number) =>
    active === undefined ? "idle" : i < active ? "done" : i === active ? "active" : "pending";
  const linkState = (i: number) =>
    active === undefined ? "idle" : i < active - 1 ? "done" : i === active - 1 ? "active" : "pending";

  return (
    <ol className="flow">
      {STEPS.map(({ art: Art, kicker, title, text, next }, i) => {
        const state = stepState(i);
        const col = 2 * i + 1;
        return (
          <li className="flow-item" key={kicker}>
            <div className={`flow-art hover-open ${state}`} style={{ gridColumn: col }}>
              <Art />
            </div>
            {next && (
              <div className="flow-link-cell" style={{ gridColumn: col + 1 }}>
                <Connector kind={next.kind} label={next.label} state={linkState(i)} />
              </div>
            )}
            <div
              className={`flow-text ${state}`}
              style={{ gridColumn: next ? `${col} / span 2` : col }}
            >
              <span className="kicker">
                {kicker}
                {state === "done" && <span className="flow-check"> ✓</span>}
              </span>
              <div className="flow-title">{title}</div>
              <p>{text}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

/** Map the worker's log lines to the step currently running. */
export function stageFromProgress(messages: string[]): number {
  let stage = 1;
  for (const m of messages) {
    if (m.startsWith("$ querying") || m.startsWith("$ investigating") || m.startsWith("$ funding")) {
      stage = 2;
    }
    if (m.startsWith("$ consolidating")) stage = 3;
    if (m.startsWith("$ done")) stage = 4;
  }
  return stage;
}
