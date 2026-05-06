import type { JokeCandidate } from "../../src/domain/jokes.js";
import {
  applyVoteTotals,
  tallyVotes,
  type VoteRecord,
} from "../../src/domain/voting.js";

describe("voting helpers", () => {
  const candidates: JokeCandidate[] = [
    {
      id: "j1",
      text: "Joke one",
      headlineIds: ["h1"],
      votes: 2,
      createdAt: "2026-04-07T10:00:00.000Z",
    },
    {
      id: "j2",
      text: "Joke two",
      headlineIds: ["h2"],
      votes: 1,
      createdAt: "2026-04-07T10:01:00.000Z",
    },
  ];

  const votes: VoteRecord[] = [
    { jokeId: "j1", voterId: "u1" },
    { jokeId: "j1", voterId: "u2" },
    { jokeId: "j2", voterId: "u3" },
  ];

  it("tallies votes onto the current totals", () => {
    const totals = tallyVotes(candidates, votes);
    expect(totals.get("j1")).toBe(4);
    expect(totals.get("j2")).toBe(2);
  });

  it("applies totals back onto the candidate list", () => {
    const totals = tallyVotes(candidates, votes);
    expect(
      applyVoteTotals(candidates, totals).map((item) => item.votes),
    ).toEqual([4, 2]);
  });
});
