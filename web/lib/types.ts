export type Sentiment = "positive" | "neutral" | "negative";
export type Severity = "Low" | "Moderate" | "Significant" | "High" | "Critical";

export interface Company { id: number; name: string; industry: string | null; description: string | null; created_at: string; n_analyses: number; n_datasets: number }
export interface Dataset { id: number; company_id: number; kind: "customer" | "company"; source_type: string; name: string; filename: string | null; origin_url: string | null; is_synthetic: boolean; n_records: number; created_at: string; validation: ValidationReport | null }
export interface ValidationReport { ok: boolean; rows_in: number; rows_valid: number; mapping: Record<string, string | null>; warnings: string[]; errors: string[]; missing_dates: number }
export interface PreviewResult { columns: string[]; detected_mapping: Record<string, string | null>; mapping_used: Record<string, string | null>; preview: Record<string, unknown>[]; n_rows: number; report: ValidationReport }
export interface SessionSummary { id: number; status: "running" | "completed" | "failed"; started_at: string; finished_at: string | null; n_customer: number; n_company: number; is_synthetic: boolean; error: string | null; total_topics: number | null; total_blind_spots: number | null; avg_blind_spot_score: number | null; overall_sentiment: number | null; runtime_seconds: number | null }
export interface SessionStatus { id: number; company_id: number; status: "running" | "completed" | "failed"; progress: number; message: string | null; error: string | null; steps: number }

export interface CustomerRow { record_id: number; text_original: string; text_clean: string; language: string | null; source: string | null; date: string | null; customer_id: string | null; vader_compound: number; transformer_score: number | null; compound: number; label: Sentiment; model: string; topic_id: number | null }
export interface Mention { record_id: number; topic_id: number; clause: string; aspect: string | null; compound: number; label: Sentiment; similarity: number | null; explicit: boolean; signals: string[] | null }
export interface Topic { topic_id: number; label: string; category: string | null; keywords: string[] | null; representative_docs: string[] | null; mentions: number; conversations: number; unique_customers: number; share_pct: number; avg_sentiment: number; positive_pct: number; negative_pct: number; neutral_pct: number; neg_intensity: number; explicit_share_pct: number; importance: number; volume_change_pct: number | null; trend_status: string | null; score: number | null; severity: Severity | null; classification: string | null }
export interface Evidence { record_id?: number; text: string; compound: number; date: string | null; customer_id?: string | null }
export interface Expectation { topic_id: number; topic_label: string | null; kind: string; summary: string; is_inferred: boolean; support_count: number; share_pct: number; keywords: string[] | null; evidence: Evidence[] | null }
export interface Theme { theme_id: number; label: string; keywords: string[] | null; n_messages: number; share_pct: number; examples: string[] | null; sources: Record<string, number> | null }
export interface CompanyMessage { text: string; similarity: number }
export interface BlindSpot {
  topic_id: number; topic_label: string; keywords: string[] | null; rank: number; classification: string; severity: Severity; score: number;
  importance: number; gap: number; trend: number | null; trend_used: number; trend_available: boolean; trend_status: string | null;
  mentions: number; unique_customers: number; share_pct: number; negative_pct: number; neg_pct: number; explicit_share_pct: number;
  frequency_score: number; customers_score: number; sentiment_score: number; explicit_score: number; coverage_share: number; coverage_norm: number;
  similarity: number; similarity_norm: number; growth_score: number | null; negative_trend_score: number | null; trend_enough: boolean; recurring: boolean;
  evidence_quotes: Evidence[] | null; closest_company_messages: CompanyMessage[] | null;
}
export interface SeriesRow { topic_id: number; period: string; volume: number; avg_sentiment: number | null; neg_count: number; share: number | null; neg_share: number | null; volume_ma: number; neg_ma: number }
export interface OverallRow { period: string; volume: number; avg_sentiment: number | null; negative: number; negative_share: number | null; volume_ma: number; sentiment_ma: number | null }
export interface TrendSummary { topic_id: number; topic_label: string; status: string; trend_score: number | null; growth_score: number; negative_trend_score: number; recent_n: number; history_n: number; recent_share_pct: number; history_share_pct: number; volume_change_pct: number | null; volume_p_value: number; recent_negative_pct: number | null; history_negative_pct: number | null; negative_delta_pct: number; negative_p_value: number; confidence: number; sentiment_slope_per_week: number | null }
export interface Spike { topic_id: number; topic_label: string; period: string; negative_count: number; z_score: number }
export interface Emerging { topic_id: number; topic_label: string; status: string; reason: string; recent_n: number; history_n: number; volume_change_pct: number | null }
export interface Recommendation { topic_id: number; topic_label: string; category: string; problem: string; evidence: Evidence[] | null; blind_spot_score: number; severity: Severity; suggested_action: string; expected_impact: string; priority: string; classification: string | null; llm_enhanced: boolean }
export interface Promise_ { text: string; promise_types: string[]; is_benefit: boolean }

export interface Overview { total_conversations: number; total_company_messages: number; total_topics: number; total_blind_spots: number; genuine_blind_spots: number; total_emerging_issues: number; overall_sentiment: number; positive_pct: number; negative_pct: number; neutral_pct: number; avg_blind_spot_score: number; uncategorised_conversations: number; offtopic_company_share_pct: number }
export interface Meta { embedding_backend: string; semantic_embeddings: boolean; topic_backend: string; sentiment_model: string; scoring_config: ScoringConfig; notes: string[]; trend_available: boolean; trend_freq: string; trend_reason: string; recent_start: string | null; runtime_seconds: number; llm_used: boolean; company_keywords: [string, number][]; promises: Promise_[] }
export interface Bundle {
  session: { id: number; company_id: number; status: string; is_synthetic: boolean; started_at: string };
  overview: Overview; meta: Meta; customer: CustomerRow[]; mentions: Mention[]; topics: Topic[]; expectations: Expectation[]; company_themes: Theme[];
  blind_spots: BlindSpot[]; recommendations: Recommendation[]; trend_series: SeriesRow[]; trend_overall: OverallRow[]; trend_summary: TrendSummary[]; trend_spikes: Spike[]; trend_emerging: Emerging[];
}
export interface ScoringConfig { w_frequency: number; w_unique_customers: number; w_sentiment: number; w_explicit_requests: number; w_coverage: number; w_similarity: number; w_volume_trend: number; w_negative_trend: number; neutral_trend: number; trend_floor: number; min_records_for_trend: number; min_importance: number; min_gap: number; min_score: number; low_coverage: number; min_emphasis_gap: number }
export interface RescoreResult { config: ScoringConfig; blind_spots: BlindSpot[]; recommendations: Recommendation[]; summary: { total_blind_spots: number; avg_blind_spot_score: number; genuine_blind_spots: number }; persisted: boolean }
export interface TopicConversation { record_id: number; statement: string; aspect: string | null; aspect_sentiment: number; aspect_label: Sentiment; full_text: string; document_sentiment: number; source: string | null; date: string | null; customer_id: string | null; signals: string[] | null }
