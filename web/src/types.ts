// Type definitions matching analysis/export/findings.json schema (data_contract.md)

export interface Corpus {
  discussion_documents: number;
  discussion_documents_by_source: Record<string, number>;
  vendor_documents: number;
  switching_vendor_documents: number;
}

export interface ShareOfVoiceEntry {
  vendor: string;
  documents: number;
  share_of_vendor_documents: number;
  mentions: number;
  switching_documents: number;
  reason_v2_documents: number;
  documents_by_source: Record<string, number>;
}

export interface ReasonCategory {
  category: string;
  reasons: number;
  by_source: Record<string, number>;
  by_sample: Record<string, number>;
}

export interface ReasonBySource {
  source: string;
  documents: number;
  with_reason: number;
  with_move: number;
  reason_share: number;
}

export interface Reasons {
  documents_labelled: number;
  reasons_total: number;
  by_category: ReasonCategory[];
  by_source: ReasonBySource[];
}

export interface AgreementEntry {
  sample: string;
  field: string;
  n: number;
  agree: number;
  pct_agree: number;
  cohen_kappa: number;
  raters: string[];
}

export interface PromotionalCategory {
  category: string;
  with: number;
  without: number;
}

export interface PromotionalVariant {
  flagged_document_ids: number[];
  flagged_with_reason: number;
  reasons_with: number;
  reasons_without: number;
  by_category: PromotionalCategory[];
  rank_order_with: string[];
  rank_order_without: string[];
}

export interface PromotionalSensitivity {
  seed_v2: PromotionalVariant;
  all_samples: PromotionalVariant;
}

export interface Quote {
  document_id: number;
  category: string;
  quote: string;
  source: string;
  url: string;
  posted_at: string;
  sample: string;
  from_vendor: string;
  to_vendor: string;
  direction: string;
}

export interface ClouderaCase {
  document_id: number;
  kind: string;
  source: string;
  url: string;
  title: string | null;
  posted_at: string;
  quotes: string[];
}

export interface ClouderaDocument {
  document_id: number;
  source: string;
  url: string;
  title: string | null;
  posted_at: string;
  other_vendors: string[];
  switching_v1: boolean;
  sample: string | null;
  taxonomy_code: string | null;
  direction: string | null;
  from_vendor: string | null;
}

export interface Cloudera {
  documents: number;
  by_source: Record<string, number>;
  by_year: Record<string, number>;
  labelled: number;
  labelled_with_reason: number;
  labelled_leaving_cloudera: number;
  cases: ClouderaCase[];
  document_list: ClouderaDocument[];
}

export interface DeploymentControlProbe {
  strict_documents_audited: number;
  deployment_control_reason: number;
  overlaps_other_category: number;
  not_a_reason: number;
  decision: string;
}

export interface Findings {
  schema_version: number;
  generated_at: string;
  label_set: string;
  human_reviewed_labels: number;
  corpus: Corpus;
  share_of_voice: ShareOfVoiceEntry[];
  reasons: Reasons;
  agreement: AgreementEntry[];
  promotional_sensitivity: PromotionalSensitivity;
  quotes: Quote[];
  cloudera: Cloudera;
  deployment_control_probe: DeploymentControlProbe;
}
