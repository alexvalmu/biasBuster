import type { Evidence } from "../types/report";

const SOURCE_NAMES: Record<Evidence["source"], string> = {
  pubmed: "PubMed",
  europepmc: "Europe PMC",
  openalex: "OpenAlex",
  crossref: "Crossref",
  orcid: "ORCID",
  clinicaltrials: "ClinicalTrials.gov",
  open_payments: "Open Payments",
  web: "Web",
};

function hostname(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function EvidenceList({ items }: { items: Evidence[] }) {
  if (!items.length) return null;
  return (
    <ul className="evidence">
      {items.map((e, i) => (
        <li key={i}>
          <span className="src">{SOURCE_NAMES[e.source]}</span>
          {e.snippet && <q>{e.snippet}</q>}{" "}
          <a href={e.url} target="_blank" rel="noopener noreferrer nofollow">
            {hostname(e.url)}
          </a>
        </li>
      ))}
    </ul>
  );
}
