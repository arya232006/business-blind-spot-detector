import type { Bundle, Company, Dataset, PreviewResult, RescoreResult, ScoringConfig, SessionStatus, SessionSummary, TopicConversation } from "./types";

export const DEFAULT_API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const STORAGE_KEY = "bbsd.apiUrl";

/** The backend URL can be changed at runtime (Settings) so a deployed frontend can point at any backend. */
export function getApiUrl(): string {
  if (typeof window === "undefined") return DEFAULT_API_URL;
  try {
    return (localStorage.getItem(STORAGE_KEY) || DEFAULT_API_URL).replace(/\/+$/, "");
  } catch {
    return DEFAULT_API_URL;
  }
}
const listeners = new Set<() => void>();
export function subscribeApiUrl(cb: () => void) {
  listeners.add(cb);
  return () => { listeners.delete(cb); };
}
export function setApiUrl(url: string) {
  try {
    localStorage.setItem(STORAGE_KEY, url.trim().replace(/\/+$/, ""));
  } catch { /* storage unavailable */ }
  listeners.forEach((l) => l());
}

export class ApiError extends Error {
  constructor(message: string, public status = 0) { super(message); }
}

async function request<T>(method: string, path: string, opts: { json?: unknown; form?: FormData; timeoutMs?: number } = {}): Promise<T> {
  const base = getApiUrl();
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), opts.timeoutMs ?? 120000);
  try {
    const res = await fetch(base + path, {
      method,
      signal: ctrl.signal,
      headers: opts.json !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: opts.form ?? (opts.json !== undefined ? JSON.stringify(opts.json) : undefined),
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
      } catch { /* non-JSON error */ }
      throw new ApiError(detail, res.status);
    }
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    if (e instanceof DOMException && e.name === "AbortError") throw new ApiError("The backend took too long to respond.");
    throw new ApiError(`Cannot reach the backend at ${base}. Is it running (uvicorn backend.main:app --port 8000)?`);
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  health: () => request<{ status: string; embedding_backend: string; database: string }>("GET", "/health", { timeoutMs: 6000 }),
  listCompanies: () => request<Company[]>("GET", "/companies"),
  createCompany: (name: string, industry?: string) => request<Company>("POST", "/companies", { json: { name, industry: industry || null } }),
  deleteCompany: (id: number) => request<void>("DELETE", `/companies/${id}`),
  listDatasets: (cid: number) => request<Dataset[]>("GET", `/companies/${cid}/datasets`),
  previewUpload: (file: File, kind: string, mapping?: Record<string, string | null>) => {
    const f = new FormData();
    f.append("file", file); f.append("kind", kind);
    if (mapping) f.append("mapping", JSON.stringify(mapping));
    return request<PreviewResult>("POST", "/datasets/preview", { form: f });
  },
  uploadDataset: (cid: number, file: File, kind: string, mapping?: Record<string, string | null>, name?: string) => {
    const f = new FormData();
    f.append("file", file); f.append("kind", kind);
    if (mapping) f.append("mapping", JSON.stringify(mapping));
    if (name) f.append("name", name);
    return request<Dataset>("POST", `/companies/${cid}/datasets/upload`, { form: f });
  },
  addText: (cid: number, kind: string, text: string, source: string) => request<Dataset>("POST", `/companies/${cid}/datasets/text`, { json: { kind, text, source } }),
  addUrl: (cid: number, kind: string, url: string) => request<Dataset>("POST", `/companies/${cid}/datasets/url`, { json: { kind, url } }),
  loadSample: (cid: number) => request<{ loaded: boolean; message: string; datasets: Dataset[] }>("POST", `/companies/${cid}/datasets/sample`),
  datasetRecords: (id: number, limit = 50) => request<Record<string, string | null>[]>("GET", `/datasets/${id}/records?limit=${limit}`),
  deleteDataset: (id: number) => request<void>("DELETE", `/datasets/${id}`),
  startAnalysis: (cid: number, customerIds?: number[], companyIds?: number[]) =>
    request<{ session_id: number }>("POST", `/companies/${cid}/analyses`, { json: { customer_source_ids: customerIds ?? null, company_source_ids: companyIds ?? null } }),
  analysisStatus: (sid: number) => request<SessionStatus>("GET", `/analyses/${sid}/status`, { timeoutMs: 15000 }),
  listAnalyses: (cid: number) => request<SessionSummary[]>("GET", `/companies/${cid}/analyses`),
  bundle: (sid: number) => request<Bundle>("GET", `/analyses/${sid}`, { timeoutMs: 300000 }),
  deleteAnalysis: (sid: number) => request<void>("DELETE", `/analyses/${sid}`),
  topicConversations: (sid: number, tid: number) => request<TopicConversation[]>("GET", `/analyses/${sid}/topics/${tid}/conversations`),
  rescore: (sid: number, config: Partial<ScoringConfig>, persist: boolean) => request<RescoreResult>("POST", `/analyses/${sid}/rescore`, { json: { config, persist } }),
  getScoringConfig: () => request<ScoringConfig>("GET", "/config/scoring"),
  saveScoringConfig: (cfg: ScoringConfig) => request<ScoringConfig>("PUT", "/config/scoring", { json: cfg }),
};
