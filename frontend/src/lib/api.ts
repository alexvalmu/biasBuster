import type { AnalysisOut } from "../types/report";
import { captchaToken } from "./captcha";

const BASE = import.meta.env.VITE_API_URL ?? "";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function parse(resp: Response): Promise<AnalysisOut> {
  if (!resp.ok) {
    let detail = `Request failed (${resp.status})`;
    try {
      const body = await resp.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (typeof body.error === "string") detail = body.error;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(resp.status, detail);
  }
  return resp.json();
}

export async function uploadPaper(file: File): Promise<AnalysisOut> {
  const form = new FormData();
  form.append("file", file);
  const token = await captchaToken("upload");
  if (token) form.append("captcha_token", token);
  return parse(await fetch(`${BASE}/api/analyses`, { method: "POST", body: form }));
}

export async function getAnalysis(sha256: string): Promise<AnalysisOut> {
  return parse(await fetch(`${BASE}/api/analyses/${sha256}`));
}
