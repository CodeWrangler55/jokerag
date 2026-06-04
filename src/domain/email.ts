import type { Headline } from "./headlines.js";
import type { JokeCandidate } from "./jokes.js";

export interface DailyEmailPayload {
  readonly dateLabel: string;
  readonly winner: JokeCandidate;
  readonly headlines: readonly Headline[];
}

export function buildDailyEmailSubject(payload: DailyEmailPayload): string {
  return `Joke of the Day for ${payload.dateLabel}`;
}

export function buildDailyEmailBody(payload: DailyEmailPayload): string {
  const headlinesBlock = payload.headlines
    .map((headline) => `- ${headline.title}`)
    .join("\n");

  return [
    `Winner: ${payload.winner.text}`,
    "",
    "Headlines used:",
    headlinesBlock,
  ].join("\n");
}
