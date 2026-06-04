import {
  buildHeadlineBrief,
  dedupeHeadlines,
  limitHeadlines,
  normalizeHeadlineTitle,
  type Headline,
} from "../../src/domain/headlines.js";

describe("headline helpers", () => {
  const headlines: Headline[] = [
    {
      id: "h1",
      title: "Apple launches new headset",
      source: "News",
      url: "https://example.com/a",
      publishedAt: "2026-04-07T00:00:00.000Z",
    },
    {
      id: "h2",
      title: "  Apple   launches new headset  ",
      source: "Alt",
      url: "https://example.com/b",
      publishedAt: "2026-04-07T00:01:00.000Z",
    },
    {
      id: "h3",
      title: "Market falls on inflation worries",
      source: "News",
      url: "https://example.com/c",
      publishedAt: "2026-04-07T00:02:00.000Z",
    },
  ];

  it("normalizes headline titles for comparison", () => {
    expect(normalizeHeadlineTitle("  Hello   World  ")).toBe("hello world");
  });

  it("deduplicates headlines by normalized title", () => {
    expect(dedupeHeadlines(headlines)).toHaveLength(2);
  });

  it("limits the headline list", () => {
    expect(limitHeadlines(headlines, 1)).toEqual([headlines[0]]);
  });

  it("rejects invalid headline limits", () => {
    expect(() => limitHeadlines(headlines, -1)).toThrow(RangeError);
  });

  it("builds a readable headline brief", () => {
    expect(buildHeadlineBrief(headlines.slice(0, 2))).toContain(
      "1. Apple launches new headset (News)",
    );
  });
});
