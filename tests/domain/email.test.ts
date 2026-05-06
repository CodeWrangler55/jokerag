import type { Headline } from "../../src/domain/headlines.js";
import type { JokeCandidate } from "../../src/domain/jokes.js";
import {
  buildDailyEmailBody,
  buildDailyEmailSubject,
  type DailyEmailPayload,
} from "../../src/domain/email.js";

describe("email helpers", () => {
  const payload: DailyEmailPayload = {
    dateLabel: "April 7, 2026",
    winner: {
      id: "j1",
      text: "The winning joke",
      headlineIds: ["h1"],
      votes: 42,
      createdAt: "2026-04-07T10:00:00.000Z",
    } satisfies JokeCandidate,
    headlines: [
      {
        id: "h1",
        title: "Headline one",
        source: "News",
        url: "https://example.com/a",
        publishedAt: "2026-04-07T00:00:00.000Z",
      } satisfies Headline,
    ],
  };

  it("builds a date-specific subject", () => {
    expect(buildDailyEmailSubject(payload)).toBe(
      "Joke of the Day for April 7, 2026",
    );
  });

  it("builds a readable daily email body", () => {
    expect(buildDailyEmailBody(payload)).toContain("Winner: The winning joke");
  });
});
