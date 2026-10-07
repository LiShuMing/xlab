/** Each editor owns a separate branch. No operation clears another editor's draft. */
export type DraftBase = { title: string; body: string; revision: number };
export type Draft = {
  version: 3;
  blog_id: string;
  editor_id: string;
  draft_revision: number;
  base: DraftBase;
  title: string;
  body: string;
  updated_at: string;
};
export interface DraftStorage {
  readonly length: number;
  key(index: number): string | null;
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}
export class DraftStore {
  readonly prefix: string;
  readonly key: string;
  readonly storage: DraftStorage;
  readonly blogId: string;
  readonly editorId: string;
  constructor(storage: DraftStorage, blogId: string, editorId: string) {
    this.storage = storage;
    this.blogId = blogId;
    this.editorId = editorId;
    this.prefix = `panming.draft.v3.${blogId}.`;
    this.key = this.prefix + editorId;
  }
  list(): Draft[] {
    const result: Draft[] = [];
    for (let i = 0; i < this.storage.length; i++) {
      const key = this.storage.key(i);
      if (!key?.startsWith(this.prefix)) continue;
      try {
        const d = JSON.parse(this.storage.getItem(key) || "null");
        if (
          d?.version === 3 &&
          d.blog_id === this.blogId &&
          typeof d.editor_id === "string" &&
          typeof d.title === "string" &&
          typeof d.body === "string" &&
          Number.isInteger(d.base?.revision) &&
          typeof d.base?.title === "string" &&
          typeof d.base?.body === "string"
        )
          result.push(d);
      } catch {
        /* A malformed branch is preserved for manual recovery. */
      }
    }
    const legacy = this.storage.getItem(`panming.draft.${this.blogId}`);
    if (legacy) {
      try {
        const d = JSON.parse(legacy);
        if (
          typeof d.title === "string" &&
          typeof d.body === "string" &&
          Number.isInteger(d.revision)
        )
          result.push({
            version: 3,
            blog_id: this.blogId,
            editor_id: "legacy",
            draft_revision: 1,
            base: { title: "", body: "", revision: d.revision },
            title: d.title,
            body: d.body,
            updated_at: "旧版草稿",
          });
      } catch {
        /* Do not destroy v0.2 drafts. */
      }
    }
    return result.sort((a, b) => b.updated_at.localeCompare(a.updated_at));
  }
  save(base: DraftBase, title: string, body: string): Draft {
    const previous = this.storage.getItem(this.key);
    let revision = 0;
    try {
      revision = JSON.parse(previous || "null")?.draft_revision || 0;
    } catch {
      /* overwrite only our own invalid slot */
    }
    const draft: Draft = {
      version: 3,
      blog_id: this.blogId,
      editor_id: this.editorId,
      draft_revision: revision + 1,
      base: { ...base },
      title,
      body,
      updated_at: new Date().toISOString(),
    };
    this.storage.setItem(this.key, JSON.stringify(draft));
    return draft;
  }
  clearSaved(expected: Draft): boolean {
    const current = this.storage.getItem(this.key);
    if (
      !current ||
      JSON.stringify(JSON.parse(current)) !== JSON.stringify(expected) ||
      expected.editor_id !== this.editorId
    )
      return false;
    this.storage.removeItem(this.key);
    return true;
  }
}

export function downloadLocal(title: string, body: string) {
  const url = URL.createObjectURL(
    new Blob([`# 本机草稿：${title}\n\n${body}`], {
      type: "text/markdown;charset=utf-8",
    }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = "panming-local-draft.md";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
