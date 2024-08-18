export function buildQuery(params = {}) {
  const pairs = Object.entries(params)
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`);

  return pairs.length > 0 ? `?${pairs.join("&")}` : "";
}
