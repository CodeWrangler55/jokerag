import type { Headline } from "../../src/domain/headlines.js";
import type { JokeCandidate } from "../../src/domain/jokes.js";
import {
  mountDailyJokeDashboard,
  type ScoreBook,
} from "../../src/app/dashboard.js";

function createMemoryStorage(seed: Record<string, string> = {}) {
  const data = new Map(Object.entries(seed));

  return {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => {
      data.set(key, value);
    },
    data,
  };
}

function createRoot() {
  return {
    innerHTML: "",
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  };
}

describe("dashboard mount", () => {
  const headlines: Headline[] = [
    {
      id: "h1",
      title: "Penguins open a very small bakery",
      source: "News Daily",
      url: "https://example.com/h1",
      publishedAt: "2026-04-07T08:00:00.000Z",
    },
    {
      id: "h2",
      title: "Mayor declares Tuesday is now cupcake day",
      source: "City Desk",
      url: "https://example.com/h2",
      publishedAt: "2026-04-07T09:00:00.000Z",
    },
  ];

  const jokes: JokeCandidate[] = [
    {
      id: "j1",
      text: "The penguins kneaded dough with absolute certainty.",
      headlineIds: ["h1"],
      votes: 0,
      createdAt: "2026-04-07T10:00:00.000Z",
    },
    {
      id: "j2",
      text: "The cupcakes won Tuesday by a crumb.",
      headlineIds: ["h2"],
      votes: 0,
      createdAt: "2026-04-07T10:05:00.000Z",
    },
  ];

  it("mounts a scoreable dashboard and persists anonymous scores", () => {
    const storage = createMemoryStorage();
    const root = createRoot();
    const initialScores: ScoreBook = {
      j1: {
        other: 4,
      },
    };

    const controller = mountDailyJokeDashboard(root as never, {
      dateLabel: "April 7, 2026",
      headlines,
      jokes,
      storage,
      initialScores,
    });

    expect(root.innerHTML).toContain("Score headline-grounded humor");
    expect(root.innerHTML).toContain("Voter anon-");
    expect(storage.data.has("jokerag:joke-dashboard:voter-id")).toBe(true);

    controller.submitScore("j2", 5);

    expect(controller.getSnapshot().leaderboard[0]?.joke.id).toBe("j2");
    expect(root.innerHTML).toContain("Saved 5 for j2");
    expect(storage.getItem("jokerag:joke-dashboard:scores")).toContain('"j2"');

    controller.submitScore("j2", 0);
    expect(controller.getSnapshot().leaderboard[0]?.joke.id).toBe("j2");

    controller.destroy();
    expect(root.removeEventListener).toHaveBeenCalledWith(
      "click",
      expect.any(Function),
    );
  });

  it("works without a storage adapter", () => {
    const root = createRoot();
    const controller = mountDailyJokeDashboard(root as never, {
      dateLabel: "April 7, 2026",
      headlines,
      jokes,
    });

    expect(controller.getSnapshot().voterId.startsWith("anon-")).toBe(true);
    controller.submitScore("j1", 4);
    expect(controller.getSnapshot().scoreCount).toBe(1);
    expect(root.innerHTML).toContain("Set average");

    controller.destroy();
  });

  it("persists scores through an injected remote handler", async () => {
    const root = createRoot();
    const storage = createMemoryStorage();
    const persistScore = vi.fn(async ({ jokeId, score, voterId }) => ({
      initialScores: {
        [jokeId]: {
          [voterId]: score as 1 | 2 | 3 | 4 | 5,
        },
      },
      statusMessage: `Saved ${score} for ${jokeId}.`,
    }));

    const controller = mountDailyJokeDashboard(root as never, {
      dateLabel: "April 7, 2026",
      headlines,
      jokes,
      storage,
      persistScore,
    });

    controller.submitScore("j1", 4);
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(persistScore).toHaveBeenCalledWith({
      jokeId: "j1",
      score: 4,
      voterId: expect.stringMatching(/^anon-/),
    });
    expect(root.innerHTML).toContain("Saved 4 for j1.");
    expect(controller.getSnapshot().jokes[0]?.userScore).toBe(4);

    controller.destroy();
  });

  it("shows an error message when remote score persistence fails", async () => {
    const root = createRoot();
    const storage = createMemoryStorage();
    const persistScore = vi.fn(async () => {
      throw new Error("server offline");
    });

    const controller = mountDailyJokeDashboard(root as never, {
      dateLabel: "April 7, 2026",
      headlines,
      jokes,
      storage,
      persistScore,
    });

    controller.submitScore("j2", 3);
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(root.innerHTML).toContain("server offline");
    expect(controller.getSnapshot().jokes[1]?.userScore).toBe(3);

    controller.destroy();
  });

  it("handles score button clicks from the rendered dashboard", () => {
    const originalElement = globalThis.Element;
    const originalHTMLButtonElement = globalThis.HTMLButtonElement;

    class FakeElement {
      closest(): FakeButtonElement | null {
        return null;
      }
    }

    class FakeButtonElement extends FakeElement {
      dataset = {
        jokeId: "j1",
        score: "5",
      };

      override closest(): FakeButtonElement {
        return this;
      }
    }

    globalThis.Element = FakeElement as never;
    globalThis.HTMLButtonElement = FakeButtonElement as never;

    try {
      const root = {
        innerHTML: "",
        addEventListener: vi.fn(
          (_event: string, handler: EventListenerOrEventListenerObject) => {
            (
              root as {
                clickHandler?: EventListenerOrEventListenerObject;
              }
            ).clickHandler = handler;
          },
        ),
        removeEventListener: vi.fn(),
        clickHandler: undefined as
          | EventListenerOrEventListenerObject
          | undefined,
      };

      const controller = mountDailyJokeDashboard(root as never, {
        dateLabel: "April 7, 2026",
        headlines,
        jokes,
        storage: createMemoryStorage(),
      });

      const button = new FakeButtonElement();
      const event = { target: button } as never;
      const clickHandler = root.clickHandler;
      if (typeof clickHandler === "function") {
        clickHandler(event);
      } else if (clickHandler !== undefined) {
        clickHandler.handleEvent(event);
      }

      expect(controller.getSnapshot().jokes[0]?.userScore).toBe(5);

      controller.destroy();
    } finally {
      globalThis.Element = originalElement;
      globalThis.HTMLButtonElement = originalHTMLButtonElement;
    }
  });

  it("ignores score button clicks that do not carry a joke id", () => {
    const originalElement = globalThis.Element;
    const originalHTMLButtonElement = globalThis.HTMLButtonElement;

    class FakeElement {
      closest(): FakeButtonElement | null {
        return null;
      }
    }

    class FakeButtonElement extends FakeElement {
      dataset = {
        score: "5",
      };

      override closest(): FakeButtonElement {
        return this;
      }
    }

    globalThis.Element = FakeElement as never;
    globalThis.HTMLButtonElement = FakeButtonElement as never;

    try {
      const root = {
        innerHTML: "",
        addEventListener: vi.fn(
          (_event: string, handler: EventListenerOrEventListenerObject) => {
            (
              root as {
                clickHandler?: EventListenerOrEventListenerObject;
              }
            ).clickHandler = handler;
          },
        ),
        removeEventListener: vi.fn(),
        clickHandler: undefined as
          | EventListenerOrEventListenerObject
          | undefined,
      };

      const controller = mountDailyJokeDashboard(root as never, {
        dateLabel: "April 7, 2026",
        headlines,
        jokes,
        storage: createMemoryStorage(),
      });

      const button = new FakeButtonElement();
      const event = { target: button } as never;
      const clickHandler = root.clickHandler;
      if (typeof clickHandler === "function") {
        clickHandler(event);
      } else if (clickHandler !== undefined) {
        clickHandler.handleEvent(event);
      }

      expect(controller.getSnapshot().scoreCount).toBe(0);
      controller.destroy();
    } finally {
      globalThis.Element = originalElement;
      globalThis.HTMLButtonElement = originalHTMLButtonElement;
    }
  });
});
