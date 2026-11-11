"use client";

import { useEffect, useState } from "react";
import { Card, Note, PageHeader, Section, Table, Td } from "@/components/ui";
import { SEVERITY_BANDS } from "@/lib/constants";
import { api } from "@/lib/api";
import type { ScoringConfig } from "@/lib/types";

export default function Methodology() {
  const [cfg, setCfg] = useState<ScoringConfig | null>(null);
  useEffect(() => { api.getScoringConfig().then(setCfg).catch(() => setCfg(null)); }, []);
  return (
    <>
      <PageHeader title="Methodology & Limits" subtitle="How every number in this application is calculated, and what it cannot tell you" />
      <Section title="Pipeline">
        <ol className="list-decimal space-y-1.5 pl-5 text-sm text-slate-700">
          <li><b>Collect</b> customer data (reviews, comments, complaints …) and company data (website copy, ads, posts …) — kept separate.</li>
          <li><b>Preprocess</b>: HTML/URL removal, whitespace and unicode normalisation, spam filter, duplicate/empty removal, language check. The original text is always kept; negations, punctuation and emojis are preserved.</li>
          <li><b>Sentiment</b>: VADER baseline (+ optional Hugging Face transformer). Aspect-based: each review is split into clauses, scored separately and linked to a topic.</li>
          <li><b>Topics</b>: BERTopic (SBERT → UMAP → HDBSCAN → c-TF-IDF) discovers topics from <i>your</i> data; KMeans fallback for small datasets.</li>
          <li><b>Needs &amp; expectations</b>: cue-pattern detection of explicit requests/expectations/unmet needs + SBERT clustering of complaints; implied expectations are labelled <i>inferred</i>.</li>
          <li><b>Company communication</b>: separate clustering into themes; share % = messages in theme ÷ all messages.</li>
          <li><b>Semantic gap</b>: customer topics and company messages are compared with SBERT cosine similarity (no keyword matching alone).</li>
          <li><b>Scoring, trends, recommendations</b> (below). Everything after step 3 is deterministic and unit-tested.</li>
        </ol>
      </Section>

      <Section title="Blind Spot Score">
        <Card>
          <div className="text-center font-mono text-sm sm:text-base">Blind Spot Score = (Customer Importance × Expectation Gap × Issue Trend) ÷ (100 × 100)</div>
        </Card>
        <p className="mt-3 text-sm text-slate-700">Each component is normalised to <b>0–100</b> before multiplication. Worked example: 85 × 90 × 80 ÷ 10,000 = <b>61.2 → High</b>.</p>
        <Table className="mt-3" head={["Component", "How it is computed"]}>
          <tr><Td className="font-semibold">Customer Importance</Td><Td>Weighted sum of four 0–100 scores: <i>frequency</i> (statements ÷ max over topics), <i>unique customers</i> (÷ max), <i>sentiment</i> (0.7 × negative share + 0.3 × negative intensity), <i>explicit requests</i> (share of statements that are explicit requests/expectations/unmet needs; 30 % ⇒ 100). Default weights 0.30 / 0.25 / 0.30 / 0.15.</Td></tr>
          <tr><Td className="font-semibold">Expectation Gap</Td><Td>0.6 × (100 − <i>coverage index</i>) + 0.4 × (100 − <i>semantic-similarity index</i>). Coverage index = share of company communication that semantically addresses the topic (softmax over SBERT cosine similarities to topic centroids; messages below a similarity floor count as off-topic), scaled so the best-covered topic = 100. Similarity index = mean of the 3 closest company messages’ similarity, min-max scaled across topics.</Td></tr>
          <tr><Td className="font-semibold">Issue Trend</Td><Td>50 = unchanged, 100 = strongly growing and more negative, 0 = strongly falling. 0.6 × volume-growth score + 0.4 × negativity-change score, comparing the <i>recent third</i> of the time span with the earlier period on <b>shares</b> (not raw counts) and shrinking weak evidence toward 50 using a two-proportion z-test. Clipped below at the trend floor (default 10) so a fading issue is dampened but never erased.</Td></tr>
        </Table>
        <Note>Missing history: if there are fewer than 20 dated records, fewer than 7 days of data, or fewer than 8 statements for a topic, the trend is marked UNAVAILABLE and a neutral value (50) is used in the formula — the app never pretends an issue is increasing.</Note>
        <p className="text-sm text-slate-700"><b>Severity bands:</b> {SEVERITY_BANDS.map(([s, r]) => `${s} ${r}`).join(" · ")}</p>
      </Section>

      <Section title="Different things that are easy to confuse">
        <Table head={["Class", "Meaning"]}>
          <tr><Td className="font-semibold">Genuine blind spot</Td><Td>Important to customers, clearly negative, large gap, and the company barely mentions it (coverage &lt; 15).</Td></tr>
          <tr><Td className="font-semibold">Unmet operational need</Td><Td>Negative and dominated by explicit “I can’t… / please add… / I expect…” statements — a product/operations gap messaging alone won’t fix.</Td></tr>
          <tr><Td className="font-semibold">Negative customer experience</Td><Td>Customers are unhappy although the company <i>does</i> communicate about the topic — possible promise-vs-reality mismatch.</Td></tr>
          <tr><Td className="font-semibold">Communication gap</Td><Td>Customers discuss it (not mainly negatively) but the company says little — a messaging opportunity.</Td></tr>
          <tr><Td className="font-semibold">Misplaced emphasis</Td><Td>The company communicates about it heavily (coverage ≥ 50) and far beyond its customer importance (coverage − importance ≥ 35).</Td></tr>
        </Table>
        <p className="mt-2 text-sm italic text-slate-600">A lack of marketing coverage does not prove the company lacks the capability — it proves the topic is not being communicated.</p>
      </Section>

      <Section title="Trend method">
        <p className="text-sm text-slate-700">Buckets are day/week/month depending on the data span. Moving averages use 3 buckets. A topic is <b>increasing/declining</b> only if its recent vs historical share differs with p &lt; 0.10; <b>emerging</b> if it was ~absent before and now has ≥ 3 statements. Spikes use a robust (median/MAD) z-score ≥ 2.5 on negative counts. Growth in sample volume alone therefore does not create a trend.</p>
      </Section>

      <Section title="Assumptions & known limitations">
        <ul className="list-disc space-y-1.5 pl-5 text-sm text-slate-700">
          <li><b>VADER is lexicon-based.</b> It misses sarcasm and implicit complaints; we add a documented domain lexicon and “service-failure” cue rules, but accuracy is not that of a fine-tuned model. Enable the optional transformer for context.</li>
          <li><b>Offline fallback embeddings (TF-IDF/LSA)</b> capture word co-occurrence, not true paraphrase — SBERT is strongly preferred for the semantic comparison.</li>
          <li><b>Topic discovery is unsupervised</b> — labels are keywords, and similar topics can merge or split. Small datasets (&lt; 30 records) use KMeans and give low-confidence topics.</li>
          <li><b>Expectation cues are regex-based</b> and English-only; inferred expectations are hypotheses, flagged as such.</li>
          <li><b>Coverage is relative</b> (best-covered topic = 100), so values compare topics within one analysis, not across companies.</li>
          <li><b>Correlation, not causation</b>: a high score means customers care and the company is quiet — it does not prove the company is unaware or incapable.</li>
          <li>Data you upload is only as representative as its sources; review platforms over-represent extreme opinions.</li>
          <li>Web extraction handles only public, server-rendered pages and respects robots.txt.</li>
        </ul>
      </Section>

      <Section title="Current default scoring configuration">
        {cfg ? <pre className="overflow-x-auto rounded-xl bg-slate-900 p-4 text-xs text-slate-100">{JSON.stringify(cfg, null, 2)}</pre> : <Note warn>Configuration unavailable (backend not reachable).</Note>}
      </Section>
    </>
  );
}
