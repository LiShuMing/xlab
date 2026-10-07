export type Topic = { id: string; name: string; color: string };
export type SourceRef = {
  material_id: string;
  material_revision: number;
  blob_hash: string;
};
export function sourceRef(m: Material): SourceRef {
  return {
    material_id: m.id,
    material_revision: m.revision,
    blob_hash: m.blob_hash,
  };
}
export type Material = {
  id: string;
  title: string;
  content: string;
  blob_hash: string;
  kind: string;
  url: string;
  topic: string;
  reason: string;
  created_at: string;
  day: string;
  feedback: string;
  revision: number;
  is_demo: boolean;
  parse_state: string;
  processing_policy?: "local_only" | "cloud_allowed";
  cloud_allowed_profile?: string | null;
  digest: {
    summary: string;
    excerpts: { text: string; line: number }[];
    questions: string[];
  };
};
export type Brief = {
  title: string;
  topic: string;
  material_ids: string[];
  question: string;
};
export type Report = {
  id: string;
  title: string;
  day: string;
  revision: number;
  cutoff_at: string;
  sources: Material[];
  groups: { topic: string; name: string; materials: string[] }[];
  briefs: Brief[];
  ready_count: number;
  pending_count: number;
  coverage_state: string;
  is_demo: boolean;
  evidence_digests?: EvidenceDigest[];
};
export type Chunk = SourceRef & {
  chunk_id: string;
  chunk_hash: string;
  text: string;
  title: string;
  offset: number;
  end: number;
  start_line: number;
  end_line: number;
};
export type EvidenceDigest = {
  id: string;
  revision: number;
  created_at: string;
  job_id: string;
  source_refs: SourceRef[];
  chunks: Chunk[];
  mode: string;
  model: string;
  provider_profile?: LLMProfile | null;
  call_attempts?: CallAttempt[];
  output: {
    claims: {
      kind: string;
      text: string;
      citations: { chunk_id: string; quote: string }[];
    }[];
    questions: string[];
  };
  topic_delta: (SourceRef & { status: string })[];
  coverage_state: string;
  source_coverage: (SourceRef & { status: string })[];
};
export type Job = {
  id: string;
  revision: number;
  created_at: string;
  state: string;
  provider: string;
  source_refs: SourceRef[];
  attempts: number;
  fence: number;
  checkpoint: string;
  digest_id: string | null;
  error_code: string | null;
  reserved_units: number;
  used_units: number;
  provider_profile?: LLMProfile | null;
  call_attempts?: CallAttempt[];
};
export type CallAttempt = {
  id: string;
  fence: number;
  day: string;
  state: string;
  token_reservation: number;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  } | null;
  error_code: string | null;
};
export type LLMProfile = {
  provider: string;
  model: string;
  locality: string;
  profile_id?: string;
  endpoint_host?: string;
  max_tokens?: number;
  timeout?: number;
  max_input?: number;
};
export type DigestOptions = {
  provider: "mock" | "openai_compatible";
  cloud_consent?: boolean;
  provider_profile?: string;
};
export type Processing = {
  provider: string;
  external_calls_enabled: boolean;
  profiles: LLMProfile[];
  config_error: string | null;
  budget: {
    day: string;
    limit: number;
    reserved: number;
    used: number;
    remaining: number;
    cost: number | null;
    cloud?: {
      request_limit: number;
      token_limit: number;
      requests: number;
      reserved_requests: number;
      actual_tokens: number;
      uncertain_tokens: number;
      reserved_tokens: number;
      remaining_requests: number;
      remaining_tokens: number;
    } | null;
  };
};
export type Blog = {
  id: string;
  title: string;
  body: string;
  material_ids: string[];
  source_snapshots?: Material[];
  source_refs?: SourceRef[];
  topic: string;
  lifecycle: string;
  revision: number;
  is_demo: boolean;
  created_at: string;
};
export type Entry = Blog & {
  book: string;
  due_day: string;
  reviews: { date: string; grade: string }[];
};
export type Proposal = Entry & {
  status: string;
  blog_id: string;
  entry_id?: string;
};
export type Source = {
  id: string;
  title: string;
  url: string;
  kind: string;
  status: string;
  enabled: boolean;
};
export type State = {
  today: string;
  topics: Topic[];
  materials: Material[];
  reports: Report[];
  blogs: Blog[];
  entries: Entry[];
  proposals: Proposal[];
  sources: Source[];
  jobs: Job[];
  digests: EvidenceDigest[];
  processing: Processing;
  settings: {
    id?: string;
    display_name: string;
    report_time: string;
    timezone: string;
  };
};

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}
export async function api<T>(
  path: string,
  data?: unknown,
  method = data === undefined ? "GET" : "POST",
): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    method,
    headers: data === undefined ? {} : { "Content-Type": "application/json" },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "服务暂时不可用" }));
    throw new ApiError(
      typeof error.detail === "string" ? error.detail : "请检查输入格式后重试",
      response.status,
    );
  }
  return response.json();
}

export async function upload<T = Material>(
  file: File,
  path = "/captures/files",
): Promise<T> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch(`/api/v1${path}`, {
    method: "POST",
    body,
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "上传失败");
  }
  return response.json();
}
