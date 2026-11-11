"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, useSyncExternalStore, type ReactNode } from "react";
import { api, ApiError, DEFAULT_API_URL, getApiUrl, resolveRegistry, setApiUrl as persistApiUrl, subscribeApiUrl } from "./api";
import { applyFilters, EMPTY_FILTERS, type Filters, type View } from "./derive";
import type { Bundle, Company, SessionSummary } from "./types";

type ApiStatus = "checking" | "online" | "offline";

interface AppState {
  apiUrl: string; apiStatus: ApiStatus; apiError: string | null; changeApiUrl: (url: string) => void; recheck: () => void;
  companies: Company[]; company: Company | null; selectCompany: (id: number) => void; refreshCompanies: () => Promise<void>;
  sessions: SessionSummary[]; sessionId: number | null; selectSession: (id: number) => void; refreshSessions: () => Promise<void>;
  bundle: Bundle | null; bundleLoading: boolean; bundleError: string | null; reloadBundle: () => Promise<void>;
  filters: Filters; setFilters: (f: Filters) => void; view: View | null;
  ready: boolean;
}

const Ctx = createContext<AppState | null>(null);
export const useApp = () => {
  const v = useContext(Ctx);
  if (!v) throw new Error("useApp must be used inside <AppProvider>");
  return v;
};

const LS = { company: "bbsd.companyId", session: "bbsd.sessionId" };
const lsGet = (k: string) => { try { const v = localStorage.getItem(k); return v ? Number(v) : null; } catch { return null; } };
const lsSet = (k: string, v: number | null) => { try { if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, String(v)); } catch { /* ignore */ } };
const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));

type Result<T> = { ok: true; data: T } | { ok: false; error: string };
async function attempt<T>(fn: () => Promise<T>): Promise<Result<T>> {
  try { return { ok: true, data: await fn() }; } catch (e) { return { ok: false, error: msg(e) }; }
}

interface BundleState { id: number | null; data: Bundle | null; error: string | null }

export function AppProvider({ children }: { children: ReactNode }) {
  // The backend URL lives in localStorage; useSyncExternalStore keeps SSR and hydration consistent.
  const apiUrl = useSyncExternalStore(subscribeApiUrl, getApiUrl, () => DEFAULT_API_URL);
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");
  const [apiError, setApiError] = useState<string | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companyId, setCompanyId] = useState<number | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [bundleState, setBundleState] = useState<BundleState>({ id: null, data: null, error: null });
  const [filterState, setFilterState] = useState<{ sessionId: number | null; filters: Filters }>({ sessionId: null, filters: EMPTY_FILTERS });
  const [ready, setReady] = useState(false);

  // ---- companies ---------------------------------------------------------------------------
  const applyCompanies = useCallback((r: Result<Company[]>) => {
    if (r.ok) {
      setCompanies(r.data); setApiStatus("online"); setApiError(null);
      setCompanyId((cur) => {
        const wanted = cur ?? lsGet(LS.company);
        const pick = r.data.find((c) => c.id === wanted)?.id ?? r.data[0]?.id ?? null;
        lsSet(LS.company, pick);
        return pick;
      });
    } else { setApiStatus("offline"); setApiError(r.error); setCompanies([]); }
    setReady(true);
  }, []);
  const refreshCompanies = useCallback(async () => { await resolveRegistry(); applyCompanies(await attempt(api.listCompanies)); }, [applyCompanies]);
  useEffect(() => {
    let live = true;
    // on a hosted site, first ask the registry where the backend currently is, then connect
    void resolveRegistry().then(() => attempt(api.listCompanies)).then((r) => { if (live) applyCompanies(r); });
    return () => { live = false; };
  }, [apiUrl, applyCompanies]);
  const recheck = useCallback(() => { setApiStatus("checking"); void refreshCompanies(); }, [refreshCompanies]);
  const changeApiUrl = useCallback((url: string) => { setApiStatus("checking"); persistApiUrl(url); }, []);

  // ---- analyses (sessions) of the selected company ---------------------------------------
  const applySessions = useCallback((r: Result<SessionSummary[]>) => {
    if (!r.ok) { setSessions([]); return; }
    setSessions(r.data);
    const done = r.data.filter((s) => s.status === "completed");
    setSessionId((cur) => {
      const wanted = cur ?? lsGet(LS.session);
      const pick = done.find((s) => s.id === wanted)?.id ?? done[0]?.id ?? null;
      lsSet(LS.session, pick);
      return pick;
    });
  }, []);
  const refreshSessions = useCallback(async () => {
    if (companyId !== null) applySessions(await attempt(() => api.listAnalyses(companyId)));
  }, [companyId, applySessions]);
  useEffect(() => {
    if (companyId === null) return;
    let live = true;
    void attempt(() => api.listAnalyses(companyId)).then((r) => { if (live) applySessions(r); });
    return () => { live = false; };
  }, [companyId, applySessions]);

  // ---- the selected analysis bundle -------------------------------------------------------
  useEffect(() => {
    if (sessionId === null) return;
    let live = true;
    void attempt(() => api.bundle(sessionId)).then((r) => {
      if (live) setBundleState(r.ok ? { id: sessionId, data: r.data, error: null } : { id: sessionId, data: null, error: r.error });
    });
    return () => { live = false; };
  }, [sessionId]);
  const reloadBundle = useCallback(async () => {
    if (sessionId === null) return;
    const r = await attempt(() => api.bundle(sessionId));
    setBundleState(r.ok ? { id: sessionId, data: r.data, error: null } : { id: sessionId, data: null, error: r.error });
  }, [sessionId]);

  const selectCompany = useCallback((id: number) => {
    lsSet(LS.company, id); lsSet(LS.session, null); setSessions([]); setSessionId(null); setCompanyId(id);
  }, []);
  const selectSession = useCallback((id: number) => { lsSet(LS.session, id); setSessionId(id); }, []);

  // ---- derived state ---------------------------------------------------------------------
  const company = useMemo(() => companies.find((c) => c.id === companyId) ?? null, [companies, companyId]);
  const current = sessionId !== null && bundleState.id === sessionId ? bundleState : null;
  // never show an analysis that belongs to a different company than the selected one
  const bundle = current?.data && current.data.session.company_id === companyId ? current.data : null;
  const bundleLoading = sessionId !== null && current === null;
  const bundleError = current?.error ?? null;
  const filters = filterState.sessionId === sessionId ? filterState.filters : EMPTY_FILTERS; // filters reset per analysis
  const setFilters = useCallback((f: Filters) => setFilterState({ sessionId, filters: f }), [sessionId]);
  const view = useMemo(() => (bundle ? applyFilters(bundle, filters) : null), [bundle, filters]);

  const value: AppState = {
    apiUrl, apiStatus, apiError, changeApiUrl, recheck, companies, company, selectCompany, refreshCompanies,
    sessions, sessionId, selectSession, refreshSessions, bundle, bundleLoading, bundleError, reloadBundle, filters, setFilters, view, ready,
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
