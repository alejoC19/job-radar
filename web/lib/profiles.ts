export type CvProfile = {
  id: string;
  name: string;
  keywords: Record<string, number>;
  created_at: string;
};

/** Parsea lineas "keyword: peso" (una por renglon) a un dict {keyword: peso}. */
export function parseKeywordsText(text: string): Record<string, number> {
  const keywords: Record<string, number> = {};
  for (const rawLine of text.split("\n")) {
    const line = rawLine.trim();
    if (!line) continue;
    const [rawKeyword, rawWeight] = line.split(":");
    const keyword = rawKeyword?.trim().toLowerCase();
    if (!keyword) continue;
    const weight = rawWeight !== undefined ? parseFloat(rawWeight.trim()) : 1;
    keywords[keyword] = Number.isFinite(weight) ? weight : 1;
  }
  return keywords;
}

/** Inversa de parseKeywordsText, para precargar el textarea al editar. */
export function keywordsToText(keywords: Record<string, number>): string {
  return Object.entries(keywords)
    .map(([keyword, weight]) => `${keyword}: ${weight}`)
    .join("\n");
}
