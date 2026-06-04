import {
  FUNNINESS_SCORES,
  type DashboardSnapshot,
  type JokeScoreSummary,
} from "./dashboard-model.js";

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatAverageScore(value: number | null): string {
  return value === null ? "No scores yet" : `${value.toFixed(1)} / 5`;
}

function formatHeadlineList(summary: JokeScoreSummary): string {
  if (summary.headlineTitles.length === 0) {
    return "No source headlines attached.";
  }

  return summary.headlineTitles.map(escapeHtml).join(" / ");
}

function renderFeedLinks(feedUrls: readonly string[]): string {
  if (feedUrls.length === 0) {
    return `<p class="feed-links__empty">No RSS feed configured.</p>`;
  }

  return `
    <div class="feed-links">
      ${feedUrls
        .map(
          (feedUrl) => `
            <a
              class="feed-link"
              href="${escapeHtml(feedUrl)}"
              target="_blank"
              rel="noreferrer noopener"
            >
              ${escapeHtml(feedUrl)}
            </a>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderScoreButtons(summary: JokeScoreSummary): string {
  return FUNNINESS_SCORES.map(
    (score) => `
      <button
        type="button"
        class="score-button${summary.userScore === score ? " is-selected" : ""}"
        data-role="score-button"
        data-joke-id="${escapeHtml(summary.joke.id)}"
        data-score="${score}"
        aria-pressed="${summary.userScore === score ? "true" : "false"}"
      >
        ${score}
      </button>
    `,
  ).join("");
}

function renderJokeCard(summary: JokeScoreSummary): string {
  return `
    <article class="joke-card" data-joke-id="${escapeHtml(summary.joke.id)}">
      <div class="joke-card__header">
        <div>
          <p class="eyebrow">Joke ${escapeHtml(summary.joke.id)}</p>
          <h2>${escapeHtml(summary.joke.text)}</h2>
        </div>
        <div class="joke-card__score">
          <strong>${formatAverageScore(summary.averageScore)}</strong>
          <span>${summary.scoreCount} score${summary.scoreCount === 1 ? "" : "s"}</span>
        </div>
      </div>
      <p class="joke-card__sources">${formatHeadlineList(summary)}</p>
      <div class="joke-card__actions" aria-label="Rate this joke from 1 to 5">
        ${renderScoreButtons(summary)}
      </div>
    </article>
  `;
}

function renderLeaderboardRow(
  summary: DashboardSnapshot["leaderboard"][number],
): string {
  return `
    <li class="leaderboard-row">
      <div class="leaderboard-row__rank">${summary.rank}</div>
      <div class="leaderboard-row__body">
        <strong>${escapeHtml(summary.joke.text)}</strong>
        <span>${formatAverageScore(summary.averageScore)} / ${summary.scoreCount} score${summary.scoreCount === 1 ? "" : "s"}</span>
      </div>
    </li>
  `;
}

export function renderDashboard(snapshot: DashboardSnapshot): string {
  const style = `
    <style>
      :root {
        color-scheme: light;
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        --bg: #f5f0e8;
        --panel: #fffdf8;
        --panel-2: #f0ebe1;
        --text: #1f1a17;
        --muted: #6b5f57;
        --border: #ddd2c4;
        --accent: #184e77;
        --accent-strong: #0b3556;
        --good: #0f7a4f;
      }

      .dashboard-shell {
        max-width: 1200px;
        margin: 0 auto;
        padding: 32px 20px 48px;
        color: var(--text);
        background: linear-gradient(180deg, var(--bg), #fff 60%);
      }

      .dashboard-header {
        display: grid;
        gap: 12px;
        margin-bottom: 24px;
      }

      .dashboard-header h1 {
        margin: 0;
        font-size: clamp(2rem, 4vw, 3rem);
        letter-spacing: -0.04em;
      }

      .dashboard-header p {
        margin: 0;
        color: var(--muted);
      }

      .status-banner {
        padding: 12px 16px;
        border: 1px solid var(--border);
        border-radius: 14px;
        background: rgba(255, 255, 255, 0.75);
      }

      .feed-card {
        display: grid;
        gap: 8px;
        margin-top: 12px;
        padding: 14px 16px;
        border: 1px solid var(--border);
        border-radius: 14px;
        background: rgba(255, 255, 255, 0.78);
      }

      .feed-links {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
      }

      .feed-link {
        display: inline-flex;
        align-items: center;
        padding: 8px 12px;
        border-radius: 999px;
        background: #fff;
        border: 1px solid var(--border);
        color: var(--accent-strong);
        text-decoration: none;
        font-weight: 700;
        word-break: break-all;
      }

      .feed-link:hover,
      .feed-link:focus-visible {
        border-color: var(--accent);
        outline: none;
      }

      .feed-links__empty {
        margin: 0;
        color: var(--muted);
      }

      .dashboard-grid {
        display: grid;
        grid-template-columns: minmax(0, 2fr) minmax(280px, 1fr);
        gap: 20px;
        align-items: start;
      }

      .panel {
        border: 1px solid var(--border);
        border-radius: 20px;
        background: var(--panel);
        box-shadow: 0 18px 45px rgba(28, 20, 12, 0.06);
      }

      .panel__header {
        padding: 20px 20px 0;
      }

      .panel__header h2,
      .panel__header h3 {
        margin: 0;
      }

      .panel__body {
        padding: 20px;
      }

      .stats-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 12px;
        margin-top: 16px;
      }

      .stat-card {
        padding: 14px;
        border-radius: 16px;
        background: var(--panel-2);
      }

      .stat-card span {
        display: block;
        color: var(--muted);
        font-size: 0.9rem;
      }

      .stat-card strong {
        display: block;
        margin-top: 6px;
        font-size: 1.25rem;
      }

      .joke-card {
        padding: 18px;
        border-radius: 18px;
        border: 1px solid var(--border);
        background: #fff;
      }

      .joke-card + .joke-card {
        margin-top: 16px;
      }

      .joke-card__header {
        display: flex;
        gap: 16px;
        justify-content: space-between;
        align-items: start;
      }

      .joke-card h2 {
        margin: 4px 0 0;
        font-size: 1.05rem;
        line-height: 1.45;
      }

      .joke-card__score {
        min-width: 130px;
        text-align: right;
      }

      .joke-card__score strong,
      .leaderboard-row__body strong {
        display: block;
      }

      .joke-card__score span,
      .joke-card__sources,
      .leaderboard-row__body span {
        color: var(--muted);
        font-size: 0.92rem;
      }

      .joke-card__sources {
        margin: 10px 0 0;
      }

      .joke-card__actions {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
        margin-top: 14px;
      }

      .score-button {
        min-width: 42px;
        padding: 10px 12px;
        border: 1px solid var(--border);
        border-radius: 999px;
        background: white;
        cursor: pointer;
        font-weight: 700;
      }

      .score-button.is-selected {
        border-color: var(--accent);
        background: var(--accent);
        color: white;
      }

      .leaderboard {
        margin: 0;
        padding: 0;
        list-style: none;
        display: grid;
        gap: 10px;
      }

      .leaderboard-row {
        display: grid;
        grid-template-columns: 44px minmax(0, 1fr);
        gap: 12px;
        align-items: center;
        padding: 12px;
        border: 1px solid var(--border);
        border-radius: 16px;
        background: #fff;
      }

      .leaderboard-row__rank {
        width: 44px;
        height: 44px;
        display: grid;
        place-items: center;
        border-radius: 14px;
        background: rgba(24, 78, 119, 0.12);
        color: var(--accent-strong);
        font-weight: 800;
      }

      .leaderboard-row__body {
        min-width: 0;
      }

      .note {
        margin: 0 0 16px;
        padding: 12px 14px;
        border-radius: 14px;
        background: rgba(15, 122, 79, 0.08);
        color: var(--good);
      }

      .eyebrow {
        margin: 0;
        color: var(--muted);
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
      }

      @media (max-width: 960px) {
        .dashboard-grid {
          grid-template-columns: 1fr;
        }
      }

      @media (max-width: 640px) {
        .dashboard-shell {
          padding-inline: 14px;
        }

        .stats-grid {
          grid-template-columns: 1fr;
        }

        .joke-card__header {
          flex-direction: column;
        }

        .joke-card__score {
          text-align: left;
          min-width: 0;
        }
      }
    </style>
  `;

  return `
    ${style}
    <main class="dashboard-shell">
      <header class="dashboard-header">
        <p class="eyebrow">JokeRAG</p>
        <h1>Score headline-grounded humor</h1>
        <p>Review joke candidates generated from current RSS headlines. Scores are anonymous and update the leaderboard immediately.</p>
        <div class="status-banner" aria-live="polite">${escapeHtml(
          `Voter ${snapshot.voterId} / ${snapshot.dateLabel}`,
        )}</div>
        <div class="feed-card" aria-label="RSS feed source">
          <p class="eyebrow">Source feeds</p>
          ${renderFeedLinks(snapshot.feedUrls)}
        </div>
        ${
          snapshot.statusMessage === null
            ? ""
            : `<div class="note" aria-live="polite">${escapeHtml(snapshot.statusMessage)}</div>`
        }
      </header>

      <section class="stats-grid" aria-label="Daily summary">
        <div class="stat-card">
          <span>Jokes in set</span>
          <strong>${snapshot.totalJokes}</strong>
        </div>
        <div class="stat-card">
          <span>Recorded scores</span>
          <strong>${snapshot.scoreCount}</strong>
        </div>
        <div class="stat-card">
          <span>Set average</span>
          <strong>${formatAverageScore(snapshot.overallAverage)}</strong>
        </div>
      </section>

      <div class="dashboard-grid">
        <section class="panel" aria-labelledby="daily-jokes-heading">
          <div class="panel__header">
            <h2 id="daily-jokes-heading">Generated joke set</h2>
          </div>
          <div class="panel__body">
            ${snapshot.jokes.map(renderJokeCard).join("")}
          </div>
        </section>

        <aside class="panel" aria-labelledby="leaderboard-heading">
          <div class="panel__header">
            <h3 id="leaderboard-heading">Live leaderboard</h3>
          </div>
          <div class="panel__body">
            <ol class="leaderboard">
              ${snapshot.leaderboard.map(renderLeaderboardRow).join("")}
            </ol>
          </div>
        </aside>
      </div>
    </main>
  `;
}
