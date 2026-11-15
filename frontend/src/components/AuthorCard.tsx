import type { AuthorFinding } from "../types/report";
import { EvidenceList } from "./EvidenceList";

const KIND: Record<string, string> = {
  employee: "employee",
  consultant: "consultant",
  speaker: "speaker fees",
  advisory_board: "advisory board",
  research_grant: "research grant",
  stock: "stock / equity",
  payments: "payments",
  patent: "patent",
  other: "other",
};

export function AuthorCard({ author }: { author: AuthorFinding }) {
  const undisclosed = author.relationships.filter((r) => !r.declared_in_paper).length;
  return (
    <article className="entity">
      <div className="entity-head">
        <h3>{author.name}</h3>
        <div className="sources">
          {author.relationships.length === 0 ? (
            <span className="chip ok">no relationships found</span>
          ) : (
            <>
              <span className="chip">{author.relationships.length} found</span>
              {undisclosed > 0 && <span className="chip danger">{undisclosed} undisclosed</span>}
            </>
          )}
        </div>
      </div>
      <div className="entity-sub">
        {author.affiliations.slice(0, 2).join(" · ")}
        {author.orcid && (
          <>
            {author.affiliations.length ? " · " : ""}
            <a href={`https://orcid.org/${author.orcid}`} target="_blank" rel="noopener noreferrer">
              ORCID {author.orcid}
            </a>
          </>
        )}
      </div>

      {author.relationships.map((r, i) => (
        <div className={`rel${r.declared_in_paper ? "" : " undeclared"}`} key={i}>
          <div className="rel-head">
            <strong>{r.company}</strong>
            <span className="chip">{KIND[r.kind] ?? r.kind}</span>
            {r.period && <span className="chip">{r.period}</span>}
            {r.amount_usd != null && (
              <span className="chip">
                ${r.amount_usd.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </span>
            )}
            <span className={`chip ${r.declared_in_paper ? "ok" : "danger"}`}>
              {r.declared_in_paper ? "declared" : "not declared"}
            </span>
            <span className={`chip${r.confidence === "low" ? " warn" : ""}`}>
              {r.confidence} confidence
            </span>
          </div>
          <EvidenceList items={r.evidence} />
        </div>
      ))}
    </article>
  );
}
