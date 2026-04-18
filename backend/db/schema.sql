CREATE SEQUENCE IF NOT EXISTS pr_snapshots_seq START 1;
CREATE SEQUENCE IF NOT EXISTS prs_seq START 1;
CREATE SEQUENCE IF NOT EXISTS pr_comments_seq START 1;

CREATE TABLE IF NOT EXISTS pr_snapshots (
    id INTEGER PRIMARY KEY DEFAULT nextval('pr_snapshots_seq'),
    snapshot_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    repo_owner VARCHAR NOT NULL,
    repo_name VARCHAR NOT NULL,
    total_prs INTEGER,
    unassigned_count INTEGER,
    old_prs_count INTEGER
);

CREATE TABLE IF NOT EXISTS prs (
    id INTEGER PRIMARY KEY DEFAULT nextval('prs_seq'),
    snapshot_id INTEGER,
    pr_number INTEGER,
    title VARCHAR,
    url VARCHAR,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    age_days INTEGER,
    reviewers VARCHAR,
    state VARCHAR,
    FOREIGN KEY (snapshot_id) REFERENCES pr_snapshots(id)
);

CREATE TABLE IF NOT EXISTS pr_comments (
    id INTEGER PRIMARY KEY DEFAULT nextval('pr_comments_seq'),
    pr_id INTEGER,
    reviewer VARCHAR,
    comment_count INTEGER,
    FOREIGN KEY (pr_id) REFERENCES prs(id)
);

CREATE INDEX IF NOT EXISTS idx_snapshot_date ON pr_snapshots(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_pr_snapshot ON prs(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_comment_pr ON pr_comments(pr_id);
