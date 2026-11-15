// Aliases over the types generated from the FastAPI OpenAPI schema (`npm run gen:types`).
import type { components } from "./api";

type S = components["schemas"];

export type AnalysisOut = S["AnalysisOut"];
export type BiasReport = S["BiasReport"];
export type AuthorFinding = S["AuthorFinding"];
export type Relationship = S["Relationship"];
export type FundingSource = S["FundingSource"];
export type Evidence = S["Evidence"];
export type RiskFactor = S["RiskFactor"];
export type ProgressEntry = S["ProgressEntry"];
