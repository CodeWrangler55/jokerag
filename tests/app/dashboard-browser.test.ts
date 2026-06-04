import {
  bootstrapDashboardApp,
  loadDashboardConfig,
  resolveDashboardConfig,
} from "../../src/dashboard-browser.js";
import type { DashboardMountConfig } from "../../src/app/dashboard.js";
import type { DashboardController } from "../../src/app/dashboard.js";

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

describe("dashboard browser bootstrap", () => {
  const originalDocument = globalThis.document;
  const originalWindow = globalThis.window;

  afterEach(() => {
    globalThis.document = originalDocument;
    globalThis.window = originalWindow;
    vi.unstubAllGlobals();
  });

  it("falls back to the bundled demo dashboard config", () => {
    const config = resolveDashboardConfig();

    expect(config.dateLabel).toBeTruthy();
    expect(config.feedUrls).toEqual(["https://feeds.bbci.co.uk/news/rss.xml"]);
    expect(config.headlines).toHaveLength(5);
    expect(config.jokes).toHaveLength(10);
  });

  it("bootstraps onto the dashboard root and stores anonymous state", async () => {
    const root = createRoot();
    const storage = createMemoryStorage();
    const documentStub = {
      readyState: "complete",
      getElementById: vi.fn(() => root),
      addEventListener: vi.fn(),
    };
    const windowStub: {
      JOKERAG_DASHBOARD?: Partial<DashboardMountConfig>;
      JOKERAG_DASHBOARD_CONTROLLER?: DashboardController;
    } = {
      JOKERAG_DASHBOARD: {
        storage,
      },
    };

    globalThis.document = documentStub as never;
    globalThis.window = windowStub as never;

    const controller = await bootstrapDashboardApp();

    expect(documentStub.getElementById).toHaveBeenCalledWith("dashboard-root");
    expect(root.innerHTML).toContain("Score headline-grounded humor");
    expect(root.innerHTML).toContain("Source feeds");
    expect(storage.data.has("jokerag:joke-dashboard:voter-id")).toBe(true);
    expect(windowStub.JOKERAG_DASHBOARD_CONTROLLER).toBe(controller);
  });

  it("allows caller overrides to replace the demo seed", () => {
    const config = resolveDashboardConfig({
      config: {
        dateLabel: "May 7, 2026",
        headlines: [],
        jokes: [],
      },
    });

    expect(config.dateLabel).toBe("May 7, 2026");
    expect(config.headlines).toEqual([]);
    expect(config.jokes).toEqual([]);
  });

  it("loads the live backend payload when an http origin is available", async () => {
    const fetchStub = vi.fn(async (input: RequestInfo | URL) => {
      const target = String(input);
      if (target.includes("/api/dashboard")) {
        return {
          ok: true,
          json: async () => ({
            dateLabel: "2026-05-09",
            feedUrls: ["https://feeds.bbci.co.uk/news/rss.xml"],
            statusMessage: "Loaded live data.",
            headlines: [
              {
                id: "headline-1",
                title: "Mayor unveils glitter bike lane",
                source: "BBC News",
                url: "https://example.com/1",
                publishedAt: "2026-05-09T00:00:00Z",
              },
            ],
            jokes: [
              {
                id: "joke-1",
                text: "Glitter lane, glitter pain.",
                headlineIds: ["headline-1"],
                votes: 0,
                createdAt: "2026-05-09T01:00:00Z",
              },
            ],
            initialScores: {
              "joke-1": {
                "voter-a": 4,
              },
            },
          }),
        } as Response;
      }

      return {
        ok: true,
        json: async () => ({
          initialScores: {
            "joke-1": {
              "voter-b": 5,
            },
          },
          statusMessage: "Saved 5 for joke-1.",
        }),
      } as Response;
    });

    globalThis.window = {
      location: { protocol: "https:" },
    } as never;
    vi.stubGlobal("fetch", fetchStub);

    const config = await loadDashboardConfig();
    expect(config.dateLabel).toBe("2026-05-09");
    expect(config.persistScore).not.toBeNull();
    expect(config.feedUrls).toEqual(["https://feeds.bbci.co.uk/news/rss.xml"]);
    expect(config.headlines).toHaveLength(1);
    expect(config.jokes).toHaveLength(1);

    const result = await config.persistScore?.({
      jokeId: "joke-1",
      score: 5,
      voterId: "voter-b",
    });
    expect(result).not.toBeNull();
    expect(result!.initialScores["joke-1"]?.["voter-b"]).toBe(5);
    expect(fetchStub).toHaveBeenCalledWith(
      "/api/dashboard",
      expect.objectContaining({ headers: { Accept: "application/json" } }),
    );
  });

  it("auto bootstraps when the document is still loading", async () => {
    const root = createRoot();
    const storage = createMemoryStorage();
    const documentStub = {
      readyState: "loading",
      getElementById: vi.fn(() => root),
      addEventListener: vi.fn(
        (_event: string, callback: EventListenerOrEventListenerObject) => {
          if (typeof callback === "function") {
            callback(new Event("DOMContentLoaded"));
          } else {
            callback.handleEvent(new Event("DOMContentLoaded"));
          }
        },
      ),
    };
    const windowStub = {
      JOKERAG_DASHBOARD: {
        storage,
      },
      location: { protocol: "file:" },
    };

    globalThis.document = documentStub as never;
    globalThis.window = windowStub as never;
    vi.resetModules();
    await import("../../src/dashboard-browser.js");

    expect(documentStub.addEventListener).toHaveBeenCalledWith(
      "DOMContentLoaded",
      expect.any(Function),
    );
    expect(root.innerHTML).toContain("Score headline-grounded humor");
  });

  it("auto bootstraps immediately when the document is ready", async () => {
    const root = createRoot();
    const storage = createMemoryStorage();
    const documentStub = {
      readyState: "complete",
      getElementById: vi.fn(() => root),
      addEventListener: vi.fn(),
    };
    const windowStub = {
      JOKERAG_DASHBOARD: {
        storage,
      },
      location: { protocol: "file:" },
    };

    globalThis.document = documentStub as never;
    globalThis.window = windowStub as never;
    vi.resetModules();
    await import("../../src/dashboard-browser.js");

    expect(documentStub.addEventListener).not.toHaveBeenCalled();
    expect(root.innerHTML).toContain("Score headline-grounded humor");
  });

  it("rejects bootstrap attempts without a document", async () => {
    globalThis.document = undefined as never;

    await expect(bootstrapDashboardApp()).rejects.toThrow(
      "Dashboard bootstrap requires a browser document.",
    );
  });

  it("rejects bootstrap attempts when the dashboard root is missing", async () => {
    const documentStub = {
      readyState: "complete",
      getElementById: vi.fn(() => null),
      addEventListener: vi.fn(),
    };
    globalThis.document = documentStub as never;
    globalThis.window = {
      location: { protocol: "file:" },
    } as never;

    await expect(bootstrapDashboardApp()).rejects.toThrow(
      "Could not find dashboard root element #dashboard-root.",
    );
  });
});
