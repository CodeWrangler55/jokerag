import type { Headline } from "../domain/headlines.js";
import type { JokeCandidate } from "../domain/jokes.js";
import {
  indexHeadlines,
  normalizeFunninessScore,
  recordScore,
  summarizeDashboard,
  type FunninessScore,
  type DashboardSnapshot,
  type DailyJokeDeck,
  type ScoreBook,
} from "./dashboard-model.js";
import { renderDashboard } from "./dashboard-view.js";

export interface DashboardMountConfig {
  readonly dateLabel: string;
  readonly feedUrls?: readonly string[];
  readonly headlines: readonly Headline[];
  readonly jokes: readonly JokeCandidate[];
  readonly storage?: StorageLike;
  readonly initialScores?: ScoreBook;
  readonly voterId?: string;
  readonly statusMessage?: string | null;
  readonly persistScore?: PersistScoreHandler | null;
}

export interface PersistScoreRequest {
  readonly jokeId: string;
  readonly score: FunninessScore;
  readonly voterId: string;
}

export interface PersistScoreResult {
  readonly initialScores: ScoreBook;
  readonly statusMessage?: string | null;
}

export type PersistScoreHandler = (
  request: PersistScoreRequest,
) => Promise<PersistScoreResult | null>;

export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export interface DashboardController {
  readonly root: HTMLElement;
  readonly getSnapshot: () => DashboardSnapshot;
  readonly submitScore: (jokeId: string, score: number) => void;
  readonly destroy: () => void;
}

const STORAGE_PREFIX = "jokerag:joke-dashboard";
const SCORES_KEY = `${STORAGE_PREFIX}:scores`;
const VOTER_KEY = `${STORAGE_PREFIX}:voter-id`;

function createStorageAdapter(storage?: StorageLike): StorageLike | null {
  if (storage !== undefined) {
    return storage;
  }

  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

function createAnonymousVoterId(
  generator: () => string = defaultIdGenerator,
): string {
  return `anon-${generator()}`;
}

function defaultIdGenerator(): string {
  const crypto = globalThis.crypto;
  if (crypto?.randomUUID) {
    return crypto.randomUUID();
  }

  return Math.random().toString(36).slice(2, 10);
}

function loadScoreBook(storage: StorageLike | null): ScoreBook {
  if (storage === null) {
    return {};
  }

  const raw = storage.getItem(SCORES_KEY);
  if (raw === null) {
    return {};
  }

  try {
    const parsed = JSON.parse(raw) as unknown;
    if (typeof parsed !== "object" || parsed === null) {
      return {};
    }

    return parsed as ScoreBook;
  } catch {
    return {};
  }
}

function saveScoreBook(
  storage: StorageLike | null,
  scoreBook: ScoreBook,
): void {
  if (storage === null) {
    return;
  }

  storage.setItem(SCORES_KEY, JSON.stringify(scoreBook));
}

function loadOrCreateVoterId(storage: StorageLike | null): string {
  if (storage === null) {
    return createAnonymousVoterId();
  }

  const current = storage.getItem(VOTER_KEY);
  if (current !== null && current.trim() !== "") {
    return current;
  }

  const voterId = createAnonymousVoterId();
  storage.setItem(VOTER_KEY, voterId);
  return voterId;
}

function createDeck(config: DashboardMountConfig): DailyJokeDeck {
  return {
    dateLabel: config.dateLabel,
    feedUrls: config.feedUrls ?? [],
    headlinesById: indexHeadlines(config.headlines),
    jokes: config.jokes,
  };
}

function findScoreButton(target: EventTarget | null): HTMLButtonElement | null {
  if (
    typeof Element === "undefined" ||
    typeof HTMLButtonElement === "undefined"
  ) {
    return null;
  }

  if (!(target instanceof Element)) {
    return null;
  }

  const button = target.closest<HTMLButtonElement>(
    "[data-role='score-button']",
  );
  return button instanceof HTMLButtonElement ? button : null;
}

export function mountDailyJokeDashboard(
  root: HTMLElement,
  config: DashboardMountConfig,
): DashboardController {
  const storage = createStorageAdapter(config.storage);
  const voterId = config.voterId ?? loadOrCreateVoterId(storage);
  const deck = createDeck(config);
  let scoreBook = {
    ...loadScoreBook(storage),
    ...(config.initialScores ?? {}),
  };
  let statusMessage = config.statusMessage ?? null;
  let snapshot = summarizeDashboard(deck, scoreBook, voterId);

  const render = (message?: string | null): void => {
    root.innerHTML = renderDashboard({
      ...snapshot,
      statusMessage: message ?? statusMessage,
    });
  };

  const sync = (message?: string | null): void => {
    if (message !== undefined) {
      statusMessage = message;
    }
    snapshot = summarizeDashboard(deck, scoreBook, voterId);
    saveScoreBook(storage, scoreBook);
    render(message);
  };

  const submitScore = (jokeId: string, score: number): void => {
    const normalizedScore = normalizeFunninessScore(score);
    if (normalizedScore === null) {
      return;
    }

    scoreBook = recordScore(scoreBook, jokeId, voterId, normalizedScore);
    sync(`Saved ${normalizedScore} for ${jokeId}`);

    const persistScore = config.persistScore;
    if (persistScore === null || persistScore === undefined) {
      return;
    }

    void persistScore({
      jokeId,
      score: normalizedScore,
      voterId,
    })
      .then((result) => {
        if (result === null) {
          return;
        }

        scoreBook = result.initialScores;
        sync(result.statusMessage ?? `Saved ${normalizedScore} for ${jokeId}`);
      })
      .catch((error) => {
        const message =
          error instanceof Error
            ? error.message
            : "Could not save the score to the dashboard server.";
        sync(message);
      });
  };

  const handleClick = (event: MouseEvent): void => {
    const button = findScoreButton(event.target);
    if (button === null) {
      return;
    }

    const jokeId = button.dataset.jokeId;
    const score = Number(button.dataset.score);
    if (jokeId === undefined) {
      return;
    }

    submitScore(jokeId, score);
  };

  root.addEventListener("click", handleClick);
  render();

  return {
    root,
    getSnapshot: () => snapshot,
    submitScore,
    destroy: () => {
      root.removeEventListener("click", handleClick);
    },
  };
}

export function createDashboardSnapshot(
  config: DashboardMountConfig,
  scoreBook: ScoreBook,
  voterId: string,
): DashboardSnapshot {
  return summarizeDashboard(createDeck(config), scoreBook, voterId);
}

export type { ScoreBook } from "./dashboard-model.js";
