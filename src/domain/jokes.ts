export interface JokeCandidate {
  readonly id: string;
  readonly text: string;
  readonly headlineIds: readonly string[];
  readonly votes: number;
  readonly createdAt: string;
}

export function rankJokes(
  candidates: readonly JokeCandidate[],
): JokeCandidate[] {
  return [...candidates].sort(compareJokes);
}

export function pickJokeOfTheDay(
  candidates: readonly JokeCandidate[],
): JokeCandidate | null {
  if (candidates.length === 0) {
    return null;
  }
  return rankJokes(candidates)[0] ?? null;
}

export function buildJokePrompt(
  headlinesBrief: string,
  jokeCount: number,
): string {
  if (!Number.isInteger(jokeCount) || jokeCount <= 0) {
    throw new RangeError("jokeCount must be a positive integer");
  }

  return [
    "Write short, punchy jokes based on these headlines.",
    "Do not explain the joke.",
    `Return exactly ${jokeCount} candidates.`,
    "Headlines:",
    headlinesBrief,
  ].join("\n");
}

function compareJokes(left: JokeCandidate, right: JokeCandidate): number {
  if (left.votes !== right.votes) {
    return right.votes - left.votes;
  }

  const createdAtDiff =
    new Date(left.createdAt).getTime() - new Date(right.createdAt).getTime();
  if (createdAtDiff !== 0) {
    return createdAtDiff;
  }

  return left.id.localeCompare(right.id);
}
