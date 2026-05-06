export interface Headline {
  readonly id: string;
  readonly title: string;
  readonly source: string;
  readonly url: string;
  readonly publishedAt: string;
}

export function normalizeHeadlineTitle(title: string): string {
  return title.trim().replace(/\s+/g, " ").toLowerCase();
}

export function dedupeHeadlines(headlines: readonly Headline[]): Headline[] {
  const seen = new Set<string>();
  const unique: Headline[] = [];

  for (const headline of headlines) {
    const key = normalizeHeadlineTitle(headline.title);
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    unique.push(headline);
  }

  return unique;
}

export function limitHeadlines(
  headlines: readonly Headline[],
  maxCount: number,
): Headline[] {
  if (!Number.isInteger(maxCount) || maxCount < 0) {
    throw new RangeError("maxCount must be a non-negative integer");
  }
  return headlines.slice(0, maxCount);
}

export function buildHeadlineBrief(headlines: readonly Headline[]): string {
  return headlines
    .map(
      (headline, index) =>
        `${index + 1}. ${headline.title} (${headline.source})`,
    )
    .join("\n");
}
