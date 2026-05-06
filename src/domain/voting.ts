import type { JokeCandidate } from "./jokes.js";

export interface VoteRecord {
  readonly jokeId: string;
  readonly voterId: string;
}

export function tallyVotes(
  candidates: readonly JokeCandidate[],
  votes: readonly VoteRecord[],
): Map<string, number> {
  const totals = new Map<string, number>();

  for (const candidate of candidates) {
    totals.set(candidate.id, candidate.votes);
  }

  for (const vote of votes) {
    totals.set(vote.jokeId, (totals.get(vote.jokeId) ?? 0) + 1);
  }

  return totals;
}

export function applyVoteTotals(
  candidates: readonly JokeCandidate[],
  totals: ReadonlyMap<string, number>,
): JokeCandidate[] {
  return candidates.map((candidate) => ({
    ...candidate,
    votes: totals.get(candidate.id) ?? candidate.votes,
  }));
}
