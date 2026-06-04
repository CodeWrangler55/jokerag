PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  run_date TEXT NOT NULL,
  topic TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  winner_joke_id TEXT,
  FOREIGN KEY (winner_joke_id) REFERENCES jokes (joke_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS headlines (
  headline_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  position INTEGER NOT NULL,
  title TEXT NOT NULL,
  normalized_title TEXT NOT NULL,
  source TEXT NOT NULL,
  url TEXT NOT NULL,
  published_at TEXT NOT NULL,
  retrieval_context TEXT NOT NULL DEFAULT "",
  FOREIGN KEY (run_id) REFERENCES runs (run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS jokes (
  joke_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  primary_headline_id TEXT,
  position INTEGER NOT NULL,
  text TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES runs (run_id) ON DELETE CASCADE,
  FOREIGN KEY (primary_headline_id) REFERENCES headlines (headline_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS joke_headlines (
  joke_id TEXT NOT NULL,
  headline_id TEXT NOT NULL,
  position INTEGER NOT NULL,
  PRIMARY KEY (joke_id, headline_id),
  UNIQUE (joke_id, position),
  FOREIGN KEY (joke_id) REFERENCES jokes (joke_id) ON DELETE CASCADE,
  FOREIGN KEY (headline_id) REFERENCES headlines (headline_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ratings (
  joke_id TEXT NOT NULL,
  voter_id TEXT NOT NULL,
  rating INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (joke_id, voter_id),
  FOREIGN KEY (joke_id) REFERENCES jokes (joke_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_headlines_run_position
  ON headlines (run_id, position, headline_id);

CREATE INDEX IF NOT EXISTS idx_jokes_run_position
  ON jokes (run_id, position, joke_id);

CREATE INDEX IF NOT EXISTS idx_joke_headlines_joke_position
  ON joke_headlines (joke_id, position, headline_id);
