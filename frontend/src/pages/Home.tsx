import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Dropzone } from "../components/Dropzone";
import { Flow } from "../components/Flow";
import { uploadPaper } from "../lib/api";

const SOURCES = [
  ["PubMed", "https://pubmed.ncbi.nlm.nih.gov/", "COI statements of the authors' other papers"],
  ["Europe PMC", "https://europepmc.org/", "grants and author affiliations"],
  ["OpenAlex", "https://openalex.org/", "affiliation history, incl. companies"],
  ["Crossref", "https://www.crossref.org/", "declared funders and awards"],
  ["ORCID", "https://orcid.org/", "self-declared employments and funding"],
  ["ClinicalTrials.gov", "https://clinicaltrials.gov/", "trial sponsors and collaborators"],
  ["CMS Open Payments", "https://openpaymentsdata.cms.gov/", "industry payments to US physicians"],
  ["Web search (Tavily)", "https://tavily.com/", "only when the databases fall short"],
];

export function Home() {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(file: File) {
    setBusy(true);
    setError(null);
    try {
      const analysis = await uploadPaper(file);
      navigate(`/report/${analysis.sha256}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
      setBusy(false);
    }
  }

  return (
    <>
      <section className="hero">
        <h1>
          Who paid for this <em>paper</em>?
        </h1>
        <p className="sub">
          Find the industry ties behind a medical study before you trust it. For students,
          clinicians and researchers.
        </p>
        <div className="hero-drop">
          <Dropzone onFile={handleFile} busy={busy} />
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
        </div>
      </section>

      <section className="sec" id="how">
        <div className="sec-head">
          <span className="sec-num">§ 01</span>
          <h2>
            How it <em>works</em>
          </h2>
          <span className="kicker">1–4 minutes per paper</span>
        </div>
        <Flow />
        <p className="sec-note">
          The investigation forks into one agent per author plus one for funders and trial
          sponsors, then merges back into a single report. The score comes from fixed rules, never
          from the language model, and any claim without a verifiable link is discarded.
        </p>
      </section>

      <section className="sec" id="sources">
        <div className="sec-head">
          <span className="sec-num">§ 02</span>
          <h2>
            Where we <em>look</em>
          </h2>
          <span className="kicker">Open data only</span>
        </div>
        <ul className="source-list">
          {SOURCES.map(([name, url, what]) => (
            <li key={name}>
              <a href={url} target="_blank" rel="noopener noreferrer">
                {name} <span className="ext">↗</span>
              </a>
              <span className="muted">{what}</span>
            </li>
          ))}
        </ul>
        <p className="sec-note">
          Reports are public and addressed by the file's SHA-256 hash: anyone who uploads the same
          PDF gets the same report instantly. We do not store your file.
        </p>
      </section>
    </>
  );
}
