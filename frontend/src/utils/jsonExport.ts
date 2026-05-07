export function formatJson(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2);
}

export function safeExportFilename(value: unknown, fallback: string): string {
  const cleaned = String(value || fallback)
    .trim()
    .replace(/[^a-z0-9._-]+/gi, "_")
    .replace(/^_+|_+$/g, "");
  return cleaned || fallback;
}

export function exportJson(value: unknown, filename: string): void {
  const blob = new Blob([`${formatJson(value)}\n`], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
