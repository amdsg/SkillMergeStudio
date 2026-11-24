PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS skills (
    id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    real_path TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    body_preview TEXT NOT NULL DEFAULT '',
    search_blob TEXT NOT NULL DEFAULT '',
    frontmatter_json TEXT NOT NULL DEFAULT '{}',
    headings_json TEXT NOT NULL DEFAULT '[]',
    resources_json TEXT NOT NULL DEFAULT '[]',
    dependencies_json TEXT NOT NULL DEFAULT '[]',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    category TEXT NOT NULL DEFAULT '未分类',
    category_source TEXT NOT NULL DEFAULT 'keyword' CHECK (category_source IN ('keyword','ai','manual')),
    confidence REAL NOT NULL DEFAULT 0 CHECK (confidence >= 0 AND confidence <= 1),
    platform_origin TEXT NOT NULL DEFAULT 'unknown',
    size_bytes INTEGER NOT NULL DEFAULT 0 CHECK (size_bytes >= 0),
    lines INTEGER NOT NULL DEFAULT 0,
    chars INTEGER NOT NULL DEFAULT 0,
    mtime REAL NOT NULL DEFAULT 0,
    content_hash TEXT NOT NULL,
    quality_score INTEGER NOT NULL DEFAULT 0 CHECK (quality_score >= 0 AND quality_score <= 100),
    quality_json TEXT NOT NULL DEFAULT '[]',
    parse_error TEXT,
    missing INTEGER NOT NULL DEFAULT 0 CHECK (missing IN (0,1)),
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_skills_hash ON skills(content_hash);
CREATE INDEX IF NOT EXISTS idx_skills_cat ON skills(category);
CREATE INDEX IF NOT EXISTS idx_skills_src ON skills(category_source);
CREATE INDEX IF NOT EXISTS idx_skills_quality ON skills(quality_score);
CREATE INDEX IF NOT EXISTS idx_skills_mtime ON skills(mtime);
CREATE INDEX IF NOT EXISTS idx_skills_missing ON skills(missing);
CREATE INDEX IF NOT EXISTS idx_skills_origin ON skills(platform_origin);
CREATE INDEX IF NOT EXISTS idx_skills_name ON skills(name COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS skill_locations (
    skill_id TEXT NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    real_path TEXT NOT NULL PRIMARY KEY,
    platform TEXT NOT NULL DEFAULT 'unknown',
    is_primary INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1)),
    mtime REAL NOT NULL DEFAULT 0,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    last_seen TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_loc_primary ON skill_locations(skill_id) WHERE is_primary = 1;
CREATE INDEX IF NOT EXISTS idx_loc_skill ON skill_locations(skill_id);
CREATE INDEX IF NOT EXISTS idx_loc_platform ON skill_locations(platform);

CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT,
    mode TEXT NOT NULL CHECK (mode IN ('probe','full')),
    roots_json TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    stats_json TEXT NOT NULL DEFAULT '{}',
    coverage_json TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_scans_started ON scans(started_at DESC);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('scan','full_scan','classify','merge','export')),
    status TEXT NOT NULL CHECK (status IN ('queued','running','succeeded','failed','cancelled')),
    params_json TEXT NOT NULL,
    progress_json TEXT NOT NULL DEFAULT '{}',
    result_json TEXT,
    error_json TEXT,
    cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK (cancel_requested IN (0,1)),
    cancel_reason TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);

CREATE TABLE IF NOT EXISTS job_events (
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    phase TEXT NOT NULL,
    current INTEGER NOT NULL DEFAULT 0,
    total INTEGER,
    message TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    PRIMARY KEY (job_id, seq)
);

CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    job_id TEXT,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT 'none',
    kind TEXT NOT NULL CHECK (kind IN ('skill','prompt')),
    dir_path TEXT NOT NULL,
    zip_path TEXT,
    installed_path TEXT,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    manifest_json TEXT NOT NULL,
    plan_summary_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','undone','missing')),
    trash_path TEXT,
    created_at TEXT NOT NULL,
    undone_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_art_created ON artifacts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_art_platform ON artifacts(platform);
CREATE INDEX IF NOT EXISTS idx_art_status ON artifacts(status);

CREATE TABLE IF NOT EXISTS merge_sources (
    artifact_id TEXT NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    skill_id TEXT NOT NULL REFERENCES skills(id) ON DELETE RESTRICT,
    source_hash TEXT NOT NULL,
    path TEXT NOT NULL,
    PRIMARY KEY (artifact_id, skill_id, source_hash)
);

CREATE INDEX IF NOT EXISTS idx_ms_skill ON merge_sources(skill_id);
CREATE INDEX IF NOT EXISTS idx_ms_hash ON merge_sources(source_hash);