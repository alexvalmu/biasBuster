import { useEffect, useRef } from "react";
import type { ProgressEntry } from "../types/report";

function hhmmss(ts: string) {
  return new Date(ts).toLocaleTimeString([], { hour12: false });
}

export function ProgressLog({ entries, running }: { entries: ProgressEntry[]; running: boolean }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    ref.current?.scrollTo({ top: ref.current.scrollHeight });
  }, [entries.length]);

  return (
    <div className="log" ref={ref} role="log" aria-live="polite">
      {entries.length === 0 && <div className="muted">$ waiting for a worker …</div>}
      {entries.map((e, i) => (
        <div className="log-line" key={i}>
          <time>{hhmmss(e.ts)}</time>
          <span>{e.msg}</span>
        </div>
      ))}
      {running && <span className="cursor" aria-hidden />}
    </div>
  );
}
