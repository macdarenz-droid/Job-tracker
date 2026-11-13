CREATE TABLE IF NOT EXISTS records (
  id TEXT PRIMARY KEY,
  position INTEGER NOT NULL,
  version INTEGER NOT NULL,
  summary TEXT NOT NULL,
  body TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS records_position ON records (position);

CREATE TABLE IF NOT EXISTS tracker_state_backup (
  version INTEGER PRIMARY KEY,
  payload TEXT NOT NULL,
  saved_at TEXT NOT NULL
);
