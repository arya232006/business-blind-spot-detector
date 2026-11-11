import type { Severity } from "./types";

export const COLORS = { primary: "#4F46E5", pos: "#10B981", neu: "#94A3B8", neg: "#EF4444", warn: "#F59E0B", ink: "#0F172A", muted: "#64748B", line: "#E2E8F0" };
export const SENT_COLORS: Record<string, string> = { positive: COLORS.pos, neutral: COLORS.neu, negative: COLORS.neg };
export const SEVERITIES: Severity[] = ["Low", "Moderate", "Significant", "High", "Critical"];
export const SEVERITY_COLORS: Record<string, string> = { Low: "#10B981", Moderate: "#EAB308", Significant: "#F97316", High: "#EF4444", Critical: "#991B1B" };
export const SEVERITY_BANDS: [Severity, string][] = [["Low", "0-20"], ["Moderate", "21-40"], ["Significant", "41-60"], ["High", "61-80"], ["Critical", "81-100"]];
export const CLASS_LABELS: Record<string, string> = {
  genuine_blind_spot: "Genuine blind spot", unmet_operational_need: "Unmet operational need", negative_experience: "Negative experience",
  communication_gap: "Communication gap", misplaced_emphasis: "Misplaced emphasis", aligned: "Aligned / low priority",
};
export const CLASS_COLORS: Record<string, string> = {
  genuine_blind_spot: "#B91C1C", unmet_operational_need: "#C2410C", negative_experience: "#D97706", communication_gap: "#2563EB", misplaced_emphasis: "#7C3AED", aligned: "#64748B",
};
export const CLASS_EXPLANATIONS: Record<string, string> = {
  genuine_blind_spot: "Customers care a lot and are unhappy, but company communication barely touches the topic.",
  unmet_operational_need: "Customers are explicitly asking for, or unable to do, something. This is an operational/product gap that messaging alone will not fix.",
  negative_experience: "The company does talk about this topic, yet customers report bad experiences - a possible promise-versus-reality mismatch.",
  communication_gap: "Customers discuss this topic mostly without hostility but the company says little about it - a messaging opportunity rather than a failure.",
  misplaced_emphasis: "The company communicates heavily about this topic, but it ranks low in customer priorities.",
  aligned: "Company attention and customer attention are in reasonable balance.",
};
export const CAVEAT = "Low company coverage shows a communication gap; it does not by itself prove the company lacks the corresponding operational capability.";
export const PRIORITY_COLORS: Record<string, string> = { P0: "#991B1B", P1: "#EF4444", P2: "#F97316", P3: "#EAB308", P4: "#64748B" };
export const KIND_NAMES: Record<string, string> = {
  complaint: "Complaint", explicit_expectation: "Explicit expectation", feature_request: "Feature request", unmet_need: "Unmet need",
  recurring_frustration: "Recurring frustration", inferred_expectation: "Inferred expectation",
};
export const KIND_COLORS: Record<string, string> = {
  complaint: "#DC2626", explicit_expectation: "#2563EB", feature_request: "#059669", unmet_need: "#D97706", recurring_frustration: "#7C3AED", inferred_expectation: "#64748B",
};
export const FLAGGED = new Set(["genuine_blind_spot", "unmet_operational_need", "negative_experience", "communication_gap"]);
export const CATEGORIES = ["Product", "Customer Support", "Operational", "Communication"] as const;
