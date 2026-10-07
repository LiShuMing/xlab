import type {
  ArticleDraft,
  Material,
  MaterialPage,
  MaterialView,
  Overview,
  PublicationJob,
  Topic,
} from "./types";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail ?? `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  overview: () => request<Overview>("/api/overview"),
  topics: () => request<Topic[]>("/api/topics"),
  material: (id: string) => request<Material>(`/api/materials/${id}`),
  materials: (view: MaterialView, query: string, topicId: string | null) => {
    const parameters = new URLSearchParams({ limit: "80", view });
    if (query) parameters.set("q", query);
    if (topicId) parameters.set("topic_id", topicId);
    return request<MaterialPage>(`/api/materials?${parameters}`);
  },
  route: (materialId: string, topicName: string) =>
    request<{ topic_id: string; topic_name: string; assigned: number }>(
      "/api/materials/batch/route",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ material_ids: [materialId], topic_name: topicName }),
      },
    ),
  createDraft: (topicId: string) =>
    request<ArticleDraft>(`/api/topics/${topicId}/drafts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ limit: 12 }),
    }),
  articles: () => request<ArticleDraft[]>("/api/articles"),
  article: (id: string) => request<ArticleDraft>(`/api/articles/${id}`),
  saveArticle: (
    articleId: string,
    values: Pick<ArticleDraft, "title" | "summary" | "body_markdown" | "version">,
  ) =>
    request<ArticleDraft>(`/api/articles/${articleId}/versions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: values.title,
        summary: values.summary,
        body_markdown: values.body_markdown,
        expected_version: values.version,
      }),
    }),
  approveArticle: (versionId: string) =>
    request<ArticleDraft>(`/api/article-versions/${versionId}/approve`, {
      method: "POST",
    }),
  createPublications: (versionId: string) =>
    request<PublicationJob[]>(`/api/article-versions/${versionId}/publications`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platforms: ["blog", "xiaohongshu"] }),
    }),
  publications: () => request<PublicationJob[]>("/api/publications"),
  preparePublication: (jobId: string) =>
    request<PublicationJob>(`/api/publication-jobs/${jobId}/prepare`, {
      method: "POST",
    }),
  previewPublication: (jobId: string) =>
    request<PublicationJob>(`/api/publication-jobs/${jobId}/preview`, {
      method: "POST",
    }),
  recordPublication: (jobId: string, externalUrl: string, note: string) =>
    request<PublicationJob>(`/api/publication-jobs/${jobId}/record-published`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ external_url: externalUrl, confirmation_note: note }),
    }),
};
