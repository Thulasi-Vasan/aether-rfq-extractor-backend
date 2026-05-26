import type { BasicExtraction } from "../types/basicExtraction";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

export function resolveApiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) {
    return path;
  }
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

export async function createBasicExtraction(
  pdf: File,
  step: File,
  forceReextract = true,
): Promise<BasicExtraction> {
  const formData = new FormData();
  formData.append("pdf", pdf);
  formData.append("step", step);

  const response = await fetch(
    `${API_BASE_URL}/v1/basic-extractions?force_reextract=${forceReextract}`,
    {
      method: "POST",
      body: formData,
    },
  );

  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Extraction failed with HTTP ${response.status}`);
  }

  return response.json();
}
