import type { Headline } from "../../src/domain/headlines.js";
import type { JokeCandidate } from "../../src/domain/jokes.js";
import {
  indexHeadlines,
  recordScore,
  summarizeDashboard,
} from "../../src/app/dashboard-model.js";
import { renderDashboard } from "../../src/app/dashboard-view.js";

describe("dashboard view", () => {
  it("renders the daily joke list and leaderboard controls", () => {
    const headlines: Headline[] = [
      {
        id: "h1",
        title: "Storm of tiny umbrellas sweeps city",
        source: "Example News",
        url: "https://example.com/umbrella",
        publishedAt: "2026-04-07T08:00:00.000Z",
      },
    ];
    const jokes: JokeCandidate[] = [
      {
        id: "j1",
        text: "The umbrellas opened a union chapter.",
        headlineIds: ["h1"],
        votes: 0,
        createdAt: "2026-04-07T10:00:00.000Z",
      },
    ];

    const snapshot = summarizeDashboard(
      {
        dateLabel: "April 7, 2026",
        feedUrls: ["https://feeds.bbci.co.uk/news/rss.xml"],
        headlinesById: indexHeadlines(headlines),
        jokes,
      },
      recordScore({}, "j1", "anon-1", 4),
      "anon-1",
    );

    const markup = renderDashboard(snapshot);

    expect(markup).toContain("Score headline-grounded humor");
    expect(markup).toContain("Source feeds");
    expect(markup).toContain("https://feeds.bbci.co.uk/news/rss.xml");
    expect(markup).toContain('data-role="score-button"');
    expect(markup).toContain('data-joke-id="j1"');
    expect(markup).toContain("Live leaderboard");
    expect(markup).toContain("4.0 / 5");
  });

  it("renders empty headline state and status messages", () => {
    const snapshot = summarizeDashboard(
      {
        dateLabel: "April 7, 2026",
        feedUrls: [],
        headlinesById: indexHeadlines([]),
        jokes: [
          {
            id: "j1",
            text: "A joke with no source headlines yet.",
            headlineIds: [],
            votes: 0,
            createdAt: "2026-04-07T10:00:00.000Z",
          },
        ],
      },
      {},
      "anon-1",
    );

    const markup = renderDashboard({
      ...snapshot,
      statusMessage: "Saved 4 for j1",
    });

    expect(markup).toContain("No source headlines attached.");
    expect(markup).toContain("Saved 4 for j1");
  });
});
