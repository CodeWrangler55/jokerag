import type { DashboardMountConfig } from "./app/dashboard.js";
import type { Headline } from "./domain/headlines.js";
import type { JokeCandidate } from "./domain/jokes.js";

const DEFAULT_BBC_NEWS_FEED_URL = "https://feeds.bbci.co.uk/news/rss.xml";

const DEMO_HEADLINES: readonly Headline[] = [
  {
    id: "h1",
    title: "City council approves bike lane made entirely of glitter",
    source: "Morning Ledger",
    url: "https://example.com/headlines/h1",
    publishedAt: "2026-05-07T08:15:00.000Z",
  },
  {
    id: "h2",
    title: "Scientists confirm ducks are the original consultants",
    source: "National Desk",
    url: "https://example.com/headlines/h2",
    publishedAt: "2026-05-07T09:00:00.000Z",
  },
  {
    id: "h3",
    title: "New startup promises to automate your bad decisions",
    source: "Tech Wire",
    url: "https://example.com/headlines/h3",
    publishedAt: "2026-05-07T09:30:00.000Z",
  },
  {
    id: "h4",
    title: "Local library adds a karaoke section to the quiet floor",
    source: "City Desk",
    url: "https://example.com/headlines/h4",
    publishedAt: "2026-05-07T10:05:00.000Z",
  },
  {
    id: "h5",
    title: "Weather service warns of a 90 percent chance of microwaved coffee",
    source: "Weather Now",
    url: "https://example.com/headlines/h5",
    publishedAt: "2026-05-07T10:30:00.000Z",
  },
];

const DEMO_JOKES: readonly JokeCandidate[] = [
  {
    id: "j1",
    text: "The bike lane glitters so hard even the potholes asked for sunglasses.",
    headlineIds: ["h1"],
    votes: 0,
    createdAt: "2026-05-07T11:00:00.000Z",
  },
  {
    id: "j2",
    text: "Ducks have been consulting for years. They just keep saying it with a quack.",
    headlineIds: ["h2"],
    votes: 0,
    createdAt: "2026-05-07T11:03:00.000Z",
  },
  {
    id: "j3",
    text: "The startup is called ChaosOps. The product is a calendar that judges you.",
    headlineIds: ["h3"],
    votes: 0,
    createdAt: "2026-05-07T11:06:00.000Z",
  },
  {
    id: "j4",
    text: "The library karaoke floor is the first place where whisper singing is a felony.",
    headlineIds: ["h4"],
    votes: 0,
    createdAt: "2026-05-07T11:09:00.000Z",
  },
  {
    id: "j5",
    text: "Microwaved coffee is not weather, but it is a lifestyle with steam damage.",
    headlineIds: ["h5"],
    votes: 0,
    createdAt: "2026-05-07T11:12:00.000Z",
  },
  {
    id: "j6",
    text: "The glitter lane is the first infrastructure project visible from the moon and a parking ticket.",
    headlineIds: ["h1", "h4"],
    votes: 0,
    createdAt: "2026-05-07T11:15:00.000Z",
  },
  {
    id: "j7",
    text: "Duck consultants always leave a meeting with more questions and better bread crumbs.",
    headlineIds: ["h2", "h3"],
    votes: 0,
    createdAt: "2026-05-07T11:18:00.000Z",
  },
  {
    id: "j8",
    text: "Automation for bad decisions is just a faster way to be confidently wrong at scale.",
    headlineIds: ["h3", "h5"],
    votes: 0,
    createdAt: "2026-05-07T11:21:00.000Z",
  },
  {
    id: "j9",
    text: "A karaoke library is where the call number is just the key change.",
    headlineIds: ["h4", "h1"],
    votes: 0,
    createdAt: "2026-05-07T11:24:00.000Z",
  },
  {
    id: "j10",
    text: "A 90 percent chance of coffee steam means the barista is now the local climate.",
    headlineIds: ["h5", "h2"],
    votes: 0,
    createdAt: "2026-05-07T11:27:00.000Z",
  },
];

function formatDateLabel(date: Date = new Date()): string {
  return date.toISOString().slice(0, 10);
}

export function createDemoDashboardConfig(): DashboardMountConfig {
  return {
    dateLabel: formatDateLabel(),
    feedUrls: [DEFAULT_BBC_NEWS_FEED_URL],
    headlines: DEMO_HEADLINES,
    jokes: DEMO_JOKES,
  };
}
