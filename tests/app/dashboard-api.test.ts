import {
  createPersistScoreHandler,
  loadDashboardConfigFromServer,
} from "../../src/dashboard-api.js";

describe("dashboard api adapter", () => {
  const originalWindow = globalThis.window;

  afterEach(() => {
    globalThis.window = originalWindow;
    vi.unstubAllGlobals();
  });

  it("skips the live api when the browser origin is file://", async () => {
    globalThis.window = {
      location: { protocol: "file:" },
    } as never;
    vi.stubGlobal("fetch", undefined);

    await expect(loadDashboardConfigFromServer()).resolves.toBeNull();
    expect(createPersistScoreHandler()).toBeNull();
  });

  it("returns null when the dashboard endpoint responds with an error", async () => {
    globalThis.window = {
      location: { protocol: "https:" },
    } as never;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
      })),
    );

    await expect(loadDashboardConfigFromServer()).resolves.toBeNull();
  });

  it("normalizes live dashboard payloads and persists scores", async () => {
    const fetchStub = vi.fn(async (input: RequestInfo | URL) => {
      const target = String(input);
      if (target.includes("/api/dashboard")) {
        return {
          ok: true,
          json: async () => ({
            dateLabel: "2026-05-09",
            feedUrls: [
              "https://feeds.bbci.co.uk/news/rss.xml",
              42,
              "  https://example.com/news.rss  ",
            ],
            statusMessage: "Loaded live data.",
            headlines: [
              {
                id: "headline-1",
                title: "Mayor unveils glitter bike lane",
                source: "BBC News",
                url: "https://example.com/1",
                publishedAt: "2026-05-09T00:00:00Z",
                summary: "A shiny lane draws a crowd.",
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

    const config = await loadDashboardConfigFromServer();
    expect(config?.dateLabel).toBe("2026-05-09");
    expect(config?.feedUrls).toEqual([
      "https://feeds.bbci.co.uk/news/rss.xml",
      "https://example.com/news.rss",
    ]);
    expect(config?.statusMessage).toBe("Loaded live data.");
    expect(config?.headlines).toHaveLength(1);
    expect(config?.jokes).toHaveLength(1);
    expect(config?.initialScores?.["joke-1"]?.["voter-a"]).toBe(4);

    const persist = createPersistScoreHandler();
    expect(persist).not.toBeNull();
    const result = await persist!({
      jokeId: "joke-1",
      score: 5,
      voterId: "voter-b",
    });

    expect(result).not.toBeNull();
    expect(result!.initialScores["joke-1"]?.["voter-b"]).toBe(5);
    expect(result!.statusMessage).toBe("Saved 5 for joke-1.");
    expect(fetchStub).toHaveBeenCalledWith(
      "/api/dashboard",
      expect.objectContaining({ headers: { Accept: "application/json" } }),
    );
    expect(fetchStub).toHaveBeenCalledWith(
      "/api/votes",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          Accept: "application/json",
        }),
      }),
    );
  });

  it("drops malformed fields from live payloads", async () => {
    globalThis.window = {
      location: { protocol: "https:" },
    } as never;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const target = String(input);
        if (target.includes("/api/dashboard")) {
          return {
            ok: true,
            json: async () => ({
              dateLabel: 123,
              feedUrls: ["https://feeds.bbci.co.uk/news/rss.xml", 123, " "],
              statusMessage: 42,
              headlines: [
                null,
                {
                  id: "headline-1",
                  title: "Mayor unveils glitter bike lane",
                  source: "BBC News",
                  url: "https://example.com/1",
                  publishedAt: "2026-05-09T00:00:00Z",
                },
              ],
              jokes: [
                null,
                {
                  id: "joke-1",
                  text: "Glitter lane, glitter pain.",
                  headlineIds: "headline-1",
                  votes: "bad",
                  createdAt: 123,
                },
              ],
              initialScores: {
                "joke-1": {
                  "voter-a": 4.5,
                },
                "joke-2": null,
              },
            }),
          } as Response;
        }

        return {
          ok: false,
          status: 400,
        } as Response;
      }),
    );

    const config = await loadDashboardConfigFromServer();
    expect(config?.dateLabel).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(config?.feedUrls).toEqual(["https://feeds.bbci.co.uk/news/rss.xml"]);
    expect(config?.statusMessage).toBeNull();
    expect(config?.headlines).toHaveLength(1);
    expect(config?.jokes).toHaveLength(0);
    expect(config?.initialScores).toEqual({});

    const persist = createPersistScoreHandler();
    await expect(
      persist!({
        jokeId: "joke-1",
        score: 5,
        voterId: "voter-b",
      }),
    ).rejects.toThrow("Failed to persist score: 400");
  });
});
