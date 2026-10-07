export type RunSummary = {
  id: string;
  status: string;
  trigger: string;
  started_at: string;
  finished_at: string | null;
  summary: Record<string, number>;
  error: string | null;
};

export type Overview = {
  materials: number;
  new: number;
  personal: number;
  needs_review: number;
  topics: number;
  last_run: RunSummary | null;
};

export type Material = {
  id: string;
  platform: string;
  external_id: string;
  author: string;
  title: string;
  excerpt: string;
  content?: string;
  url: string;
  published_at: string | null;
  first_seen_at: string;
  priority: number;
  quality_score: number;
  status: string;
  personal: boolean;
  tags: string[];
  topics: string[];
  topic_ids: string[];
  source_ids: string[];
  event_count: number;
  metrics?: Record<string, number>;
  fingerprints?: {
    url_hash: string | null;
    content_hash: string;
    normalizer_version: number;
  };
};

export type ArticleDraft = {
  article_id: string;
  version_id: string;
  title: string;
  summary: string;
  body_markdown: string;
  artifact_path: string;
  reused: boolean;
  status: string;
  article_type: string;
  topic_id: string;
  topic_name: string;
  version: number;
  evidence_count: number;
  evidence?: ArticleEvidence[];
};

export type ArticleEvidence = {
  claim_id: string;
  citation_order: number;
  note: string;
  material_id: string;
  title: string;
  author: string;
  platform: string;
  canonical_url: string;
  quality_score: number;
};

export type PublicationArtifact = {
  id: string;
  kind: string;
  path: string;
  sha256: string;
  metadata: Record<string, unknown>;
  created_at: string;
  url: string;
};

export type PublicationJob = {
  job_id: string;
  article_version_id: string;
  article_id: string;
  article_title: string;
  topic_name: string;
  platform: "blog" | "xiaohongshu";
  adapter_id: string;
  capabilities: string[];
  manual_confirmation_required: boolean;
  status: string;
  attempt_count: number;
  created_at: string;
  updated_at: string;
  last_error: string | null;
  prepared_at: string | null;
  previewed_at: string | null;
  published_at: string | null;
  external_url: string | null;
  artifacts: PublicationArtifact[];
};

export type WorkspaceSection = "materials" | "articles" | "distribution";

export type MaterialPage = {
  items: Material[];
  next_cursor: string | null;
};

export type Topic = {
  id: string;
  slug: string;
  name: string;
  description: string;
  material_count: number;
};

export type MaterialView = "all" | "new" | "personal" | "needs_review";
