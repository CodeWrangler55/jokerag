import type { DashboardMountConfig } from "./app/dashboard.js";
import {
  mountDailyJokeDashboard,
  type DashboardController,
} from "./app/dashboard.js";
import {
  createPersistScoreHandler,
  loadDashboardConfigFromServer,
} from "./dashboard-api.js";
import { createDemoDashboardConfig } from "./dashboard-seed.js";

declare global {
  interface Window {
    JOKERAG_DASHBOARD?: Partial<DashboardMountConfig>;
    JOKERAG_DASHBOARD_CONTROLLER?: DashboardController;
  }
}

export interface DashboardBootstrapOptions {
  readonly rootId?: string;
  readonly config?: Partial<DashboardMountConfig>;
}

function mergeDashboardConfig(
  fallback: DashboardMountConfig,
  override: Partial<DashboardMountConfig>,
): DashboardMountConfig {
  return {
    ...fallback,
    ...override,
    feedUrls: override.feedUrls ?? fallback.feedUrls,
    headlines: override.headlines ?? fallback.headlines,
    jokes: override.jokes ?? fallback.jokes,
    initialScores: override.initialScores ?? fallback.initialScores,
    storage: override.storage ?? fallback.storage,
    voterId: override.voterId ?? fallback.voterId,
    dateLabel: override.dateLabel ?? fallback.dateLabel,
    statusMessage: override.statusMessage ?? fallback.statusMessage,
    persistScore: override.persistScore ?? fallback.persistScore,
  };
}

export function resolveDashboardConfig(
  options: DashboardBootstrapOptions = {},
): DashboardMountConfig {
  const fallback = createDemoDashboardConfig();
  const windowConfig =
    typeof window === "undefined" ? undefined : window.JOKERAG_DASHBOARD;

  return mergeDashboardConfig(fallback, {
    ...windowConfig,
    ...options.config,
  });
}

export async function loadDashboardConfig(
  options: DashboardBootstrapOptions = {},
): Promise<DashboardMountConfig> {
  const fallback = resolveDashboardConfig(options);
  const remoteConfig = await loadDashboardConfigFromServer();
  const persistScore = createPersistScoreHandler();

  return mergeDashboardConfig(fallback, {
    ...remoteConfig,
    persistScore:
      remoteConfig !== null ? (persistScore ?? undefined) : undefined,
  });
}

export async function bootstrapDashboardApp(
  options: DashboardBootstrapOptions = {},
): Promise<DashboardController> {
  if (typeof document === "undefined") {
    throw new Error("Dashboard bootstrap requires a browser document.");
  }

  const rootId = options.rootId ?? "dashboard-root";
  const root = document.getElementById(rootId);
  if (root === null) {
    throw new Error(`Could not find dashboard root element #${rootId}.`);
  }

  root.innerHTML = `<main style="max-width:720px;margin:48px auto;padding:24px;font-family:system-ui,sans-serif;color:#1f1a17;">Loading headline-grounded joke set...</main>`;
  const config = await loadDashboardConfig(options);
  const controller = mountDailyJokeDashboard(root, config);

  if (typeof window !== "undefined") {
    window.JOKERAG_DASHBOARD_CONTROLLER = controller;
  }

  return controller;
}

function autoBootstrap(): void {
  void bootstrapDashboardApp().catch((error) => {
    const message =
      error instanceof Error
        ? error.message
        : "Unknown dashboard bootstrap failure.";
    if (typeof document !== "undefined") {
      const root = document.getElementById("dashboard-root");
      if (root !== null) {
        root.innerHTML = `<pre style="white-space:pre-wrap;color:#8a1f11;background:#fff7f5;border:1px solid #e5b7b0;padding:16px;border-radius:12px;">${message}</pre>`;
      }
    }
    if (typeof console !== "undefined") {
      console.error(error);
    }
  });
}

if (typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      autoBootstrap();
    });
  } else {
    autoBootstrap();
  }
}
