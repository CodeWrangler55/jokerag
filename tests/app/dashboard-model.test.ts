import type { Headline } from "../../src/domain/headlines.js";
import type { JokeCandidate } from "../../src/domain/jokes.js";
import {
  FUNNINESS_SCORES,
  indexHeadlines,
  normalizeFunninessScore,
  recordScore,
  summarizeDashboard,
  type ScoreBook,
} from "../../src/app/dashboard-model.js";

describe("dashboard model", () => {
  const headlines: Headline[] = [
    {
      id: "h1",
      title: "Scientists discover beans can bounce",
      source: "Morning News",
      url: "https://example.com/1",
      publishedAt: "2026-04-07T08:00:00.000Z",
    },
    {
      id: "h2",
      title: "Traffic solved by unusually polite pigeons",
      source: "City Wire",
      url: "https://example.com/2",
      publishedAt: "2026-04-07T09:00:00.000Z",
    },
  ];

  const jokes: JokeCandidate[] = [
    {
      id: "j1",
      text: "The beans were so excited, they kept springing into action.",
      headlineIds: ["h1"],
      votes: 0,
      createdAt: "2026-04-07T10:00:00.000Z",
    },
    {
      id: "j2",
      text: "The pigeons directed traffic with tiny reflective vests.",
      headlineIds: ["h2"],
      votes: 0,
      createdAt: "2026-04-07T10:05:00.000Z",
    },
    {
      id: "j3",
      text: "A clerk filed a complaint against the weather for being dramatic.",
      headlineIds: ["h1", "h2"],
      votes: 0,
      createdAt: "2026-04-07T10:10:00.000Z",
    },
  ];

  it("exposes the 1-5 scoring scale", () => {
    expect(FUNNINESS_SCORES).toEqual([1, 2, 3, 4, 5]);
    expect(normalizeFunninessScore(3)).toBe(3);
    expect(normalizeFunninessScore(0)).toBeNull();
  });

  it("indexes headlines by id", () => {
    const indexed = indexHeadlines(headlines);
    expect(indexed.h1?.title).toBe(headlines[0]?.title);
  });

  it("summarizes the dashboard and updates leaderboard ordering from score changes", () => {
    const voterA = "anon-a";
    const voterB = "anon-b";
    let scoreBook: ScoreBook = {};

    scoreBook = recordScore(scoreBook, "j1", voterA, 4);
    scoreBook = recordScore(scoreBook, "j2", voterA, 5);
    scoreBook = recordScore(scoreBook, "j2", voterB, 3);
    scoreBook = recordScore(scoreBook, "j3", voterA, 2);
    scoreBook = recordScore(scoreBook, "j1", voterA, 5);

    const snapshot = summarizeDashboard(
      {
        dateLabel: "April 7, 2026",
        feedUrls: ["https://feeds.bbci.co.uk/news/rss.xml"],
        headlinesById: indexHeadlines(headlines),
        jokes,
      },
      scoreBook,
      voterA,
    );

    expect(snapshot.totalJokes).toBe(3);
    expect(snapshot.scoreCount).toBe(4);
    expect(
      snapshot.jokes.find((item) => item.joke.id === "j1")?.userScore,
    ).toBe(5);
    expect(
      snapshot.jokes.find((item) => item.joke.id === "j1")?.averageScore,
    ).toBe(5);
    expect(snapshot.leaderboard.map((item) => item.joke.id)).toEqual([
      "j1",
      "j2",
      "j3",
    ]);
    expect(snapshot.leaderboard[0]?.rank).toBe(1);
    expect(snapshot.overallAverage).toBeCloseTo(3.75);
  });

  it("breaks leaderboard ties by createdAt and id", () => {
    const scoreBook: ScoreBook = {
      j1: {
        v1: 3,
        v2: 3,
      },
      j2: {
        v3: 3,
        v4: 3,
      },
      a1: {
        v5: 4,
        v6: 2,
      },
      b1: {
        v7: 4,
        v8: 2,
      },
    };

    const snapshot = summarizeDashboard(
      {
        dateLabel: "April 7, 2026",
        feedUrls: ["https://feeds.bbci.co.uk/news/rss.xml"],
        headlinesById: indexHeadlines(headlines),
        jokes: [
          {
            id: "j2",
            text: "Later joke with same score",
            headlineIds: ["h2"],
            votes: 0,
            createdAt: "2026-04-07T10:10:00.000Z",
          },
          {
            id: "j1",
            text: "Earlier joke with same score",
            headlineIds: ["h1"],
            votes: 0,
            createdAt: "2026-04-07T10:00:00.000Z",
          },
          {
            id: "b1",
            text: "Id tie breaker later",
            headlineIds: ["h2"],
            votes: 0,
            createdAt: "2026-04-07T10:20:00.000Z",
          },
          {
            id: "a1",
            text: "Id tie breaker earlier",
            headlineIds: ["h1"],
            votes: 0,
            createdAt: "2026-04-07T10:20:00.000Z",
          },
        ],
      },
      scoreBook,
      "v1",
    );

    expect(snapshot.leaderboard.map((item) => item.joke.id)).toEqual([
      "j1",
      "j2",
      "a1",
      "b1",
    ]);
  });
});
