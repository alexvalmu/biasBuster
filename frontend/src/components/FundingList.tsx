import type { FundingSource } from "../types/report";
import { EvidenceList } from "./EvidenceList";

export function FundingList({ funding }: { funding: FundingSource[] }) {
  if (!funding.length) {
    return <div className="empty-state">No funding sources could be identified.</div>;
  }
  return (
    <div>
      {funding.map((f) => (
        <div className="entity" key={f.name}>
          <div className="entity-head">
            <h3>{f.name}</h3>
            <div className="sources">
              <span className={`chip${f.type === "industry" ? " warn" : ""}`}>{f.type}</span>
              <span className={`chip ${f.declared_in_paper ? "ok" : "danger"}`}>
                {f.declared_in_paper ? "declared in paper" : "not declared in paper"}
              </span>
            </div>
          </div>
          <EvidenceList items={f.evidence} />
        </div>
      ))}
    </div>
  );
}
