import { Link, Outlet, useLocation } from "react-router-dom";
import { ThemeToggle } from "./ThemeToggle";

function Mark() {
  return (
    <svg className="brand-mark" viewBox="0 0 64 64" aria-hidden>
      <path d="M8 52h48" stroke="currentColor" strokeWidth="5" strokeLinecap="round" />
      <path
        d="M10 51C17 51 19 14 26 14S39 41 55 50"
        fill="none"
        stroke="currentColor"
        strokeWidth="5"
        strokeLinecap="round"
      />
      <circle cx="38" cy="26" r="5.5" fill="#FF5A1F" />
    </svg>
  );
}

export function Layout() {
  const { pathname } = useLocation();
  const crumb = pathname.startsWith("/report") ? "Report" : "Check a paper";
  return (
    <div className="page">
      <header className="topbar">
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <Link to="/" className="brand">
            <Mark />
            <span className="brand-name">
              bias<i>buster</i>
            </span>
          </Link>
          <span className="crumb">
            /<b>{crumb}</b>
          </span>
        </div>
        <div className="top-right">
          <nav className="top-links">
            <a href="/#how">How it works</a>
            <a href="/#sources">Sources</a>
          </nav>
          <ThemeToggle />
        </div>
      </header>
      <main>
        <Outlet />
      </main>
      <footer className="footer">
        Built on open data from PubMed, Europe PMC, OpenAlex, Crossref, ORCID, ClinicalTrials.gov
        and CMS Open Payments.
      </footer>
    </div>
  );
}
