import {
  buildJokePrompt,
  pickJokeOfTheDay,
  rankJokes,
  type JokeCandidate,
} from "../../src/domain/jokes.js";

describe("joke helpers", () => {
  const jokes: JokeCandidate[] = [
    {
      id: "j2",
      text: "Second joke",
      headlineIds: ["h1"],
      votes: 12,
      createdAt: "2026-04-07T10:01:00.000Z",
    },
    {
      id: "j1",
      text: "First joke",
      headlineIds: ["h2"],
      votes: 12,
      createdAt: "2026-04-07T10:00:00.000Z",
    },
    {
      id: "j3",
      text: "Third joke",
      headlineIds: ["h3"],
      votes: 7,
      createdAt: "2026-04-07T10:02:00.000Z",
    },
  ];

  it("ranks jokes by votes then createdAt then id", () => {
    expect(rankJokes(jokes).map((joke) => joke.id)).toEqual(["j1", "j2", "j3"]);
  });

  it("picks the joke of the day deterministically", () => {
    expect(pickJokeOfTheDay(jokes)?.id).toBe("j1");
  });

  it("returns null when there are no candidates", () => {
    expect(pickJokeOfTheDay([])).toBeNull();
  });

  it("builds a constrained joke prompt", () => {
    expect(buildJokePrompt("1. Headline", 10)).toContain(
      "exactly 10 candidates",
    );
  });

  it("rejects invalid joke counts", () => {
    expect(() => buildJokePrompt("1. Headline", 0)).toThrow(RangeError);
  });
});
