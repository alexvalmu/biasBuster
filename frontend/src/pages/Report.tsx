import { useEffect, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { AuthorCard } from "../components/AuthorCard";
import { Disclaimer } from "../components/Disclaimer";
import { Flow, stageFromProgress } from "../components/Flow";
import { FundingList } from "../components/FundingList";
import { ProgressLog } from "../components/ProgressLog";
import { ApiError, getAnalysis } from "../lib/api";
import type { AnalysisOut, BiasReport } from "../types/report";

const POLL_MS = 2000;

export function Report() {
  const { sha256 = "" } = useParams();
  const [analysis, setAnalysis] = useState<AnalysisOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let timer: number | undefined;
    let cancelled = false;

    async function poll() {
      try {
        const a = await getAnalysis(sha256);
        if (cancelled) return;
        setAnalysis(a);
        setError(null);
        if (a.status === "queued" || a.status === "running") {
          timer = window.setTimeout(poll, POLL_MS);
        }
      } catch (e) {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 404) {
          setError("We have no report for this file yet. Upload the paper to analyze it.");
        } else {
          setError("Connection problem, retrying…");
          timer = window.setTimeout(poll, POLL_MS * 2);
        }
      }
    }

    poll();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [sha256]);

  if (error && !analysis) {
    return (
      <div className="sheet">
        <h2>
          No <em>report</em>
        </h2>
        <p className="sub">
          {error} <Link to="/">Check a paper</Link>.
        </p>
      </div>
    );
  }

  if (!analysis) return <p className="muted cursor">Loading</p>;

  if (analysis.status === "done" && analysis.report) {
    return <ReportView report={analysis.report} sha256={sha256} />;
  }

  const failed = analysis.status === "failed";
  const stage = stageFromProgress(analysis.progress.map((p) => p.msg));
  return (
    <article className="sheet">
      <div className="sheet-case">
        <span>Case · {sha256.slice(0, 12)}…</span>
        <span>{failed ? "Stopped" : analysis.status === "queued" ? "In the queue" : "In progress"}</span>
      </div>
      <h2>
        {failed ? (
          <>
            Something went <em>wrong</em>
          </>
        ) : (
          <>
            Investigating the <em>authors</em>
          </>
        )}
      </h2>
      <p className="sub">
        {failed
          ? "We could not finish this analysis. Uploading the same PDF again will retry it."
          : "This usually takes 1–4 minutes. Keep this page open, or come back to this link later."}
      </p>
      <Flow active={failed ? undefined : stage} />
      <ProgressLog entries={analysis.progress} running={!failed} />
      {error && <p className="error">{error}</p>}
    </article>
  );
}

function Section({ num, title, children }: { num: string; title: ReactNode; children: ReactNode }) {
  return (
    <section className="sheet-sec">
      <div className="sheet-sec-head">
        <span className="sec-num">§ {num}</span>
        <h3>{title}</h3>
      </div>
      <div>{children}</div>
    </section>
  );
}

function ReportView({ report, sha256 }: { report: BiasReport; sha256: string }) {
  const [copied, setCopied] = useState(false);
  const p = report.paper;
  const generated = report.generated_at ? new Date(report.generated_at).toLocaleDateString() : null;

  async function copyLink() {
    await navigator.clipboard.writeText(window.location.href);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }

  return (
    <article className="sheet">
      <div className="sheet-case">
        <span>Case · {sha256.slice(0, 12)}…</span>
        {generated && <span>Filed {generated}</span>}
        <span>Report v{report.report_version}</span>
      </div>

      <div className={`stamp risk-${report.risk_level}`} aria-label={`${report.risk_level} risk, ${report.risk_score} out of 100`}>
        <div className="stamp-level">{report.risk_level.toUpperCase()} RISK</div>
        <div className="stamp-score">{report.risk_score}</div>
        <div className="stamp-sub">
          {report.undisclosed_count} UNDISCLOSED
        </div>
      </div>

      <h2 className="sheet-title">{p.title ?? "Untitled paper"}</h2>
      <div className="meta">
        {p.journal && <span>{p.journal}</span>}
        {p.year && <span>{p.year}</span>}
        {p.doi && (
          <a href={`https://doi.org/${p.doi}`} target="_blank" rel="noopener noreferrer">
            doi:{p.doi}
          </a>
        )}
        {p.pmid && (
          <a href={`https://pubmed.ncbi.nlm.nih.gov/${p.pmid}/`} target="_blank" rel="noopener noreferrer">
            pmid:{p.pmid}
          </a>
        )}
        {(p.trial_ids ?? []).map((t) => (
          <a key={t} href={`https://clinicaltrials.gov/study/${t}`} target="_blank" rel="noopener noreferrer">
            {t}
          </a>
        ))}
      </div>
      {report.summary && <p className="summary">{report.summary}</p>}
      <div className="actions">
        <button className="btn" onClick={copyLink}>
          {copied ? "Link copied" : "Copy link"}
        </button>
        <Link to="/">Check another paper</Link>
      </div>

      <Section num="1" title={<>Why this <em>score</em></>}>
        {report.risk_breakdown.length ? (
          <ul className="breakdown">
            {report.risk_breakdown.map((f) => (
              <li key={f.label}>
                <span>{f.label}</span>
                <span className="pts">+{f.points}</span>
              </li>
            ))}
            <li>
              <strong>Total</strong>
              <span className={`pts risk-${report.risk_level}`}>{report.risk_score} / 100</span>
            </li>
          </ul>
        ) : (
          <div className="empty-state">No industry funding or relationships were found.</div>
        )}
      </Section>

      <Section num="2" title={<>What the paper <em>declares</em></>}>
        <div className="statements">
          <div className="statement">
            <span className="kicker">Funding</span>
            <p className={report.declared_funding_statement ? "" : "empty"}>
              {report.declared_funding_statement ?? "No funding statement found in the paper."}
            </p>
          </div>
          <div className="statement">
            <span className="kicker">Competing interests</span>
            <p className={report.declared_coi_statement ? "" : "empty"}>
              {report.declared_coi_statement ?? "No conflict-of-interest statement found in the paper."}
            </p>
          </div>
        </div>
      </Section>

      <Section num="3" title={<>Who <em>funded</em> it</>}>
        <FundingList funding={report.funding} />
      </Section>

      <Section num="4" title={<>The <em>authors</em></>}>
        {report.authors.length ? (
          report.authors.map((a) => <AuthorCard key={a.name} author={a} />)
        ) : (
          <div className="empty-state">No authors could be investigated.</div>
        )}
      </Section>

      <Section num="5" title={<em>Limitations</em>}>
        {report.limitations.length > 0 && (
          <ul className="limitations">
            {report.limitations.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        )}
        <Disclaimer />
      </Section>
    </article>
  );
}
