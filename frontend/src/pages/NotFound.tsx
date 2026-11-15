import { Link } from "react-router-dom";

export function NotFound() {
  return (
    <div className="card">
      <h2>
        Nothing <em>here</em>
      </h2>
      <p className="sub">
        That page does not exist. <Link to="/">Check a paper</Link>.
      </p>
    </div>
  );
}
