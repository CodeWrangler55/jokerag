import type {
  DashboardMountConfig,
  PersistScoreHandler,
} from "./app/dashboard.js";
import type { ScoreBook } from "./app/dashboard-model.js";
import type { Headline } from "./domain/headlines.js";
import type { JokeCandidate } from "./domain/jokes.js";

interface ServerDashboardPayload {
  readonly dateLabel?: unknown;
  readonly feedUrls?: unknown;
  readonly statusMessage?: unknown;
  readonly headlines?: unknown;
  readonly jokes?: unknown;
  readonly initialScores?: unknown;
}

interface PersistVoteResponse {
  readonly initialScores?: unknown;
  readonly statusMessage?: unknown;
}

interface PersistVoteRequest {
  readonly jokeId: string;
  readonly voterId: string;
  readonly rating: number;
}

export async function loadDashboardConfigFromServer(): Promise<Partial<DashboardMountConfig> | null> {
  if (!canUseDashboardApi()) {
    return null;
  }

  try {
    const response = await fetch("/api/dashboard", {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      return null;
    }

    const payload = (await response.json()) as ServerDashboardPayload;
    return normalizeServerDashboardPayload(payload);
  } catch {
    return null;
  }
}

export function createPersistScoreHandler(): PersistScoreHandler | null {
  if (!canUseDashboardApi()) {
    return null;
  }

  return async ({ jokeId, score, voterId }) => {
    const response = await fetch("/api/votes", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        jokeId,
        voterId,
        rating: score,
      } satisfies PersistVoteRequest),
    });

    if (!response.ok) {
      throw new Error(`Failed to persist score: ${response.status}`);
    }

    const payload = (await response.json()) as PersistVoteResponse;
    return {
      initialScores: normalizeScoreBook(payload.initialScores) ?? {},
      statusMessage:
        typeof payload.statusMessage === "string"
          ? payload.statusMessage
          : `Saved ${score} for ${jokeId}.`,
    };
  };
}

function normalizeServerDashboardPayload(
  payload: ServerDashboardPayload,
): Partial<DashboardMountConfig> {
  return {
    dateLabel:
      typeof payload.dateLabel === "string"
        ? payload.dateLabel
        : formatTodayLabel(),
    feedUrls: normalizeFeedUrls(payload.feedUrls),
    statusMessage:
      typeof payload.statusMessage === "string" ? payload.statusMessage : null,
    headlines: normalizeHeadlines(payload.headlines),
    jokes: normalizeJokes(payload.jokes),
    initialScores: normalizeScoreBook(payload.initialScores),
  };
}

function normalizeHeadlines(value: unknown): readonly Headline[] | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }

  return value.flatMap((item) => {
    if (typeof item !== "object" || item === null) {
      return [];
    }

    const candidate = item as Record<string, unknown>;
    const id = candidate.id;
    const title = candidate.title;
    const source = candidate.source;
    const url = candidate.url;
    const publishedAt = candidate.publishedAt ?? candidate.published_at;
    if (
      typeof id !== "string" ||
      typeof title !== "string" ||
      typeof source !== "string" ||
      typeof url !== "string" ||
      typeof publishedAt !== "string"
    ) {
      return [];
    }

    const summary =
      typeof candidate.summary === "string" && candidate.summary.trim() !== ""
        ? candidate.summary
        : undefined;
    return [
      {
        id,
        title,
        source,
        url,
        publishedAt,
        summary,
      } satisfies Headline,
    ];
  });
}

function normalizeJokes(value: unknown): readonly JokeCandidate[] | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }

  return value.flatMap((item) => {
    if (typeof item !== "object" || item === null) {
      return [];
    }

    const candidate = item as Record<string, unknown>;
    const id = candidate.id;
    const text = candidate.text;
    const headlineIds = candidate.headlineIds ?? candidate.headline_ids;
    const votes = candidate.votes;
    const createdAt = candidate.createdAt ?? candidate.created_at;

    if (
      typeof id !== "string" ||
      typeof text !== "string" ||
      !Array.isArray(headlineIds) ||
      typeof votes !== "number" ||
      typeof createdAt !== "string"
    ) {
      return [];
    }

    return [
      {
        id,
        text,
        headlineIds: headlineIds.flatMap((headlineId) =>
          typeof headlineId === "string" ? [headlineId] : [],
        ),
        votes,
        createdAt,
      } satisfies JokeCandidate,
    ];
  });
}

function normalizeScoreBook(value: unknown): ScoreBook | undefined {
  if (typeof value !== "object" || value === null) {
    return undefined;
  }

  const entries = Object.entries(value as Record<string, unknown>);
  const scoreBook: ScoreBook = {};
  for (const [jokeId, rawVotes] of entries) {
    if (typeof rawVotes !== "object" || rawVotes === null) {
      continue;
    }

    const voteEntries = Object.entries(rawVotes as Record<string, unknown>);
    const votes: Record<string, 1 | 2 | 3 | 4 | 5> = {};
    for (const [voterId, rawScore] of voteEntries) {
      if (typeof rawScore !== "number" || !Number.isInteger(rawScore)) {
        continue;
      }
      if (rawScore < 1 || rawScore > 5) {
        continue;
      }
      votes[voterId] = rawScore as 1 | 2 | 3 | 4 | 5;
    }

    if (Object.keys(votes).length > 0) {
      scoreBook[jokeId] = votes;
    }
  }

  return scoreBook;
}

function normalizeFeedUrls(value: unknown): readonly string[] | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }

  const feedUrls = value.flatMap((item) => {
    if (typeof item !== "string") {
      return [];
    }

    const normalized = item.trim();
    return normalized === "" ? [] : [normalized];
  });

  return feedUrls.length === 0 ? undefined : feedUrls;
}

function canUseDashboardApi(): boolean {
  if (typeof fetch !== "function") {
    return false;
  }

  if (typeof window === "undefined" || window.location === undefined) {
    return false;
  }

  return (
    window.location.protocol === "http:" ||
    window.location.protocol === "https:"
  );
}

function formatTodayLabel(date: Date = new Date()): string {
  return date.toISOString().slice(0, 10);
}
