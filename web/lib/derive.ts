import { FLAGGED } from "./constants";
import type { BlindSpot, Bundle, CustomerRow, Expectation, Mention, Recommendation, Topic } from "./types";

export interface Filters { topics: number[]; sentiments: string[]; severities: string[]; sources: string[]; dateFrom: string; dateTo: string }
export const EMPTY_FILTERS: Filters = { topics: [], sentiments: [], severities: [], sources: [], dateFrom: "", dateTo: "" };

export type MentionX = Mention & { date: string | null; customer_id: string | null; source: string | null };
export interface View {
  customer: CustomerRow[]; mentions: MentionX[]; topics: Topic[]; blindSpots: BlindSpot[]; recs: Recommendation[]; expectations: Expectation[];
  allMentions: MentionX[]; dateBounds: [string, string] | null; sources: string[];
}

const day = (iso: string | null) => (iso ? iso.slice(0, 10) : null);

export function applyFilters(b: Bundle, f: Filters): View {
  const byRec = new Map(b.customer.map((c) => [c.record_id, c]));
  const allMentions: MentionX[] = b.mentions.map((m) => {
    const c = byRec.get(m.record_id);
    return { ...m, date: c?.date ?? null, customer_id: c?.customer_id ?? null, source: c?.source ?? null };
  });
  const dates = b.customer.map((c) => day(c.date)).filter(Boolean) as string[];
  const dateBounds: [string, string] | null = dates.length ? [dates.reduce((a, c) => (a < c ? a : c)), dates.reduce((a, c) => (a > c ? a : c))] : null;
  const sources = Array.from(new Set(b.customer.map((c) => c.source).filter(Boolean) as string[])).sort();
  const dateFilterActive = dateBounds && ((f.dateFrom && f.dateFrom !== dateBounds[0]) || (f.dateTo && f.dateTo !== dateBounds[1]));

  const customer = b.customer.filter((c) => {
    if (f.topics.length && (c.topic_id === null || !f.topics.includes(c.topic_id))) return false;
    if (f.sentiments.length && !f.sentiments.includes(c.label)) return false;
    if (f.sources.length && (!c.source || !f.sources.includes(c.source))) return false;
    if (dateFilterActive) {
      const d = day(c.date);
      if (!d) return false;
      if (f.dateFrom && d < f.dateFrom) return false;
      if (f.dateTo && d > f.dateTo) return false;
    }
    return true;
  });
  const ids = new Set(customer.map((c) => c.record_id));
  const mentions = allMentions.filter((m) => ids.has(m.record_id) && (!f.topics.length || f.topics.includes(m.topic_id)) && (!f.sentiments.length || f.sentiments.includes(m.label)));
  const topics = topicStats(b.topics.filter((t) => !f.topics.length || f.topics.includes(t.topic_id)), mentions);
  const topicSet = new Set(f.topics);
  const blindSpots = b.blind_spots.filter((s) => (!f.topics.length || topicSet.has(s.topic_id)) && (!f.severities.length || f.severities.includes(s.severity)));
  const recs = b.recommendations.filter((r) => (!f.topics.length || topicSet.has(r.topic_id)) && (!f.severities.length || f.severities.includes(r.severity)));
  const expectations = b.expectations.filter((e) => !f.topics.length || topicSet.has(e.topic_id));
  return { customer, mentions, topics, blindSpots, recs, expectations, allMentions, dateBounds, sources };
}

/** Recompute volume/sentiment statistics for the current filters (scores/importance stay as analysed). */
export function topicStats(topics: Topic[], mentions: MentionX[]): Topic[] {
  const total = mentions.length || 1;
  return topics.map((t) => {
    const g = mentions.filter((m) => m.topic_id === t.topic_id);
    const n = g.length;
    const cnt = (l: string) => g.filter((m) => m.label === l).length;
    const withId = new Set(g.filter((m) => m.customer_id).map((m) => m.customer_id));
    return {
      ...t, mentions: n, conversations: new Set(g.map((m) => m.record_id)).size,
      unique_customers: withId.size + g.filter((m) => !m.customer_id).length,
      share_pct: (n / total) * 100, avg_sentiment: n ? g.reduce((s, m) => s + m.compound, 0) / n : 0,
      positive_pct: n ? (cnt("positive") / n) * 100 : 0, negative_pct: n ? (cnt("negative") / n) * 100 : 0, neutral_pct: n ? (cnt("neutral") / n) * 100 : 0,
    };
  });
}

export const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);
export const pct = (n: number, d: number) => (d ? (n / d) * 100 : 0);
export const fmt = (v: number | null | undefined, digits = 0) => (v === null || v === undefined || Number.isNaN(v) ? "—" : v.toFixed(digits));

export function flaggedSpots(spots: BlindSpot[], minScore: number) {
  return spots.filter((s) => FLAGGED.has(s.classification) && s.score >= minScore);
}

/** Histogram of compound sentiment scores split by label. */
export function sentimentHistogram(rows: CustomerRow[], bins = 24) {
  const out = Array.from({ length: bins }, (_, i) => ({ x: -1 + (2 * (i + 0.5)) / bins, negative: 0, neutral: 0, positive: 0 }));
  for (const r of rows) {
    const i = Math.min(bins - 1, Math.max(0, Math.floor(((r.compound + 1) / 2) * bins)));
    out[i][r.label] += 1;
  }
  return out.map((o) => ({ ...o, x: Number(o.x.toFixed(2)) }));
}

export function downloadCsv(filename: string, rows: Record<string, unknown>[]) {
  if (!rows.length) return;
  const cols = Object.keys(rows[0]);
  const esc = (v: unknown) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const csv = [cols.join(","), ...rows.map((r) => cols.map((c) => esc(r[c])).join(","))].join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}
