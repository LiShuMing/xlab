export async function fetchJson(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers ?? {}) };
  const response = await fetch(path, {
    credentials: 'include',
    ...options,
    headers,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data.detail)
      ? data.detail.map((item) => `${item.loc?.join('.') ?? 'request'}: ${item.msg}`).join('; ')
      : data.detail || data.message || data.error;
    throw new Error(detail ? `Request failed: ${response.status} - ${detail}` : `Request failed: ${response.status}`);
  }
  return data;
}
