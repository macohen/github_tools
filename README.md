# GitHub PR Tracker

Tracks open pull requests, generates a markdown file, and publishes a summary to Quip with approval status and age.

## Setup

### Required Environment Variables

```bash
export GITHUB_TOKEN="your_github_token"
export QUIP_API_TOKEN="your_quip_token"
```

### Optional Environment Variables

```bash
export GITHUB_REPO_OWNER="awslabs"  # Default: awslabs
export GITHUB_REPO_NAME="aws-athena-query-federation"  # Default: aws-athena-query-federation
export QUIP_DOC_ID="doc_id"  # If set, updates existing doc; otherwise creates new
export QUIP_BASE_URL="https://platform.quip.com"  # Default: https://platform.quip.com
```

## Usage

```bash
python track_open_prs.py
```

## Output

Generates a Quip document with:
- Total PR count, unassigned PRs, PRs older than 30 days
- Table showing each PR's title, age, reviewers, and merge readiness
- Color-coded status: 🔴 (needs 2 approvals), 🟡 (needs 1), 🟢 (ready to merge)

## Requirements

```bash
pip install requests
```
