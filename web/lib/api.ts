import type { Bundle, Company, Dataset, PreviewResult, RescoreResult, ScoringConfig, SessionStatus, SessionSummary, TopicConversation } from "./types";

export const DEFAULT_API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
/** Optional public JSON file `{"url": "https://..."}` that always holds the CURRENT backend URL. It lets a hosted frontend find a
 *  backend that sits behind a tunnel whose address changes on every restart (see scripts/share.sh). */
export const REGISTRY_URL = process.env.NEXT_PUBLIC_REGISTRY_URL || "";
const STORAGE_KEY = "bbsd.apiUrl";

const listeners = new Set<() => void>();
let registryUrl: string | null = null;
export const subscribeApiUrl = (cb: () => void) => {
  listeners.add(cb);
  return () => { listeners.delete(cb); };
};
const notify = () => listeners.forEach((l) => l());
const isLocalHost = () => typeof window !== "undefined" && ["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname);

function override(): string | null {
  try { return localStorage.getItem(STORAGE_KEY); } catch { return null; }
}

/** Precedence: URL typed in Backend settings > URL from the registry (hosted sites only) > NEXT_PUBLIC_API_URL > localhost. */
export function getApiUrl(): string {
  if (typeof window === "undefined") return DEFAULT_API_URL;
  return (override() || registryUrl || DEFAULT_API_URL).replace(/\/+$/, "");
}

export function setApiUrl(url: string) {
  try {
    if (url.trim()) localStorage.setItem(STORAGE_KEY, url.trim().replace(/\/+$/, ""));
    else localStorage.removeItem(STORAGE_KEY);
  } catch { /* storage unavailable */ }
  notify();
}

/** Fetch the current backend URL from the registry. Never throws; leaves the default in place on failure. */
export async function resolveRegistry(): Promise<void> {
  if (!REGISTRY_URL || typeof window === "undefined" || isLocalHost() || override()) return;
  try {
    const res = await fetch(`${REGISTRY_URL}${REGISTRY_URL.includes("?") ? "&" : "?"}t=${Date.now()}`, { cache: "no-store" });
    const body = (await res.json()) as { url?: string };
    const next = body.url ? body.url.replace(/\/+$/, "") : null;
    if (next !== registryUrl) { registryUrl = next; notify(); }
  } catch { /* registry unreachable: keep whatever we have */ }
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
    throw new ApiError(`Cannot reach the backend at ${base}. It may be switched off (the owner's machine must be running it).`);
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
