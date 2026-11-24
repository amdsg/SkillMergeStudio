function norm(value) {
  return String(value || "").normalize("NFC").toLowerCase();
}

export function scorePlatform(item, query) {
  const q = norm(query).trim();
  if (!q) return 1;
  const id = norm(item.id);
  const label = norm(item.label);
  const group = norm(item.group);
  const aliases = (item.aliases || []).map(norm);
  if (id === q) return 1000;
  if (label === q) return 950;
  if (aliases.includes(q)) return 900;
  if (label.startsWith(q)) return 800;
  if (id.startsWith(q)) return 740;
  if (aliases.some((alias) => alias.startsWith(q))) return 700;
  if (label.includes(q)) return 500;
  if (id.includes(q)) return 450;
  if (aliases.some((alias) => alias.includes(q))) return 420;
  if (group.includes(q)) return 200;
  return 0;
}

export function filterPlatforms(items, query, limit = 50) {
  const scored = (items || [])
    .map((item) => ({ item, score: scorePlatform(item, query) }))
    .filter((row) => row.score > 0);
  scored.sort((left, right) => right.score - left.score || left.item.label.localeCompare(right.item.label));
  return scored.slice(0, limit).map((row) => row.item);
}