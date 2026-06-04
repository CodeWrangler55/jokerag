import type { Headline } from "../domain/headlines.js";
import type { JokeCandidate } from "../domain/jokes.js";

export type FunninessScore = 1 | 2 | 3 | 4 | 5;

export const FUNNINESS_SCORES: readonly FunninessScore[] = [1, 2, 3, 4, 5];

export type ScoreBook = Record<string, Record<string, FunninessScore>>;

export interface DailyJokeDeck {
  readonly dateLabel: string;
  readonly feedUrls: readonly string[];
  readonly headlinesById: Readonly<Record<string, Headline>>;
  readonly jokes: readonly JokeCandidate[];
}

export interface JokeScoreSummary {
  readonly joke: JokeCandidate;
  readonly averageScore: number | null;
  readonly scoreCount: number;
  readonly totalScore: number;
  readonly userScore: FunninessScore | null;
  readonly headlineTitles: readonly string[];
}

export interface LeaderboardRow extends JokeScoreSummary {
  readonly rank: number;
}

export interface DashboardSnapshot {
  readonly dateLabel: string;
  readonly feedUrls: readonly string[];
  readonly voterId: string;
  readonly totalJokes: number;
  readonly scoreCount: number;
  readonly overallAverage: number | null;
  readonly statusMessage: string | null;
  readonly jokes: readonly JokeScoreSummary[];
  readonly leaderboard: readonly LeaderboardRow[];
}

export function indexHeadlines(
  headlines: readonly Headline[],
): Readonly<Record<string, Headline>> {
  const indexed: Record<string, Headline> = {};

  for (const headline of headlines) {
    indexed[headline.id] = headline;
  }

  return indexed;
}

export function normalizeFunninessScore(value: number): FunninessScore | null {
  if (!Number.isInteger(value) || value < 1 || value > 5) {
    return null;
  }

  return value as FunninessScore;
}

export function recordScore(
  scoreBook: ScoreBook,
  jokeId: string,
  voterId: string,
  score: FunninessScore,
): ScoreBook {
  return {
    ...scoreBook,
    [jokeId]: {
      ...(scoreBook[jokeId] ?? {}),
      [voterId]: score,
    },
  };
}

export function summarizeDashboard(
  deck: DailyJokeDeck,
  scoreBook: ScoreBook,
  voterId: string,
): DashboardSnapshot {
  const jokes = deck.jokes.map((joke) =>
    summarizeJoke(joke, deck.headlinesById, scoreBook, voterId),
  );
  const leaderboard = [...jokes]
    .sort(compareSummaryRows)
    .map((summary, index) => ({
      ...summary,
      rank: index + 1,
    }));
  const scoreCount = jokes.reduce((total, item) => total + item.scoreCount, 0);
  const totalScore = jokes.reduce((total, item) => total + item.totalScore, 0);

  return {
    dateLabel: deck.dateLabel,
    feedUrls: deck.feedUrls,
    voterId,
    totalJokes: deck.jokes.length,
    scoreCount,
    overallAverage: scoreCount === 0 ? null : totalScore / scoreCount,
    statusMessage: null,
    jokes,
    leaderboard,
  };
}

export function summarizeJoke(
  joke: JokeCandidate,
  headlinesById: Readonly<Record<string, Headline>>,
  scoreBook: ScoreBook,
  voterId: string,
): JokeScoreSummary {
  const scores = Object.values(scoreBook[joke.id] ?? {});
  const totalScore = scores.reduce((total, score) => total + score, 0);
  const scoreCount = scores.length;

  return {
    joke,
    averageScore: scoreCount === 0 ? null : totalScore / scoreCount,
    scoreCount,
    totalScore,
    userScore: scoreBook[joke.id]?.[voterId] ?? null,
    headlineTitles: joke.headlineIds.map(
      (headlineId) => headlinesById[headlineId]?.title ?? headlineId,
    ),
  };
}

export function compareSummaryRows(
  left: JokeScoreSummary,
  right: JokeScoreSummary,
): number {
  const leftScore = left.averageScore ?? -1;
  const rightScore = right.averageScore ?? -1;

  if (leftScore !== rightScore) {
    return rightScore - leftScore;
  }

  if (left.scoreCount !== right.scoreCount) {
    return right.scoreCount - left.scoreCount;
  }

  if (left.totalScore !== right.totalScore) {
    return right.totalScore - left.totalScore;
  }

  const createdAtDiff =
    new Date(left.joke.createdAt).getTime() -
    new Date(right.joke.createdAt).getTime();
  if (createdAtDiff !== 0) {
    return createdAtDiff;
  }

  return left.joke.id.localeCompare(right.joke.id);
}
