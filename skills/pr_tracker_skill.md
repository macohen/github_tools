---
name: pr-tracker
description: Generate a color-coded HTML report of open pull requests for a GitHub repository, with summary cards, an age histogram, and a review-status table. Optionally publish the report to SharePoint. Use when asked to report on, triage, or summarize open PRs and their review or approval status.
---

# PR Tracker


## Overview

Generates a visual report of open pull requests for a GitHub repository, color-coded by review/approval status. Includes a summary card row, an age distribution histogram (Highcharts), and a detailed table of PRs matching the criteria. PRs are sorted oldest to newest. Optionally publishes the report to a SharePoint page.

**Color logic:**
- 🟢 **Green** — ≥2 human reviewer approvals (ready to merge)
- 🟡 **Yellow** — exactly 1 human reviewer approval (needs one more)
- 🔴 **Red** — 2+ reviewers assigned but 0 human approvals (blocked)

## Workflow

### Step 1: Parse the repo URL
- **Mode**: `agentic`
- **Input**: `{{repo_url}}`
- **Output**: `owner` and `repo` strings extracted from the URL
- **Validate**: URL matches pattern `https://github.com/{owner}/{repo}`
- **On failure**: Ask the user for a valid GitHub repo URL

Extract the owner and repo name from the URL. Handle trailing slashes or `.git` suffixes gracefully.

### Step 2: Fetch all open PRs
- **Mode**: `deterministic`
- **Tool**: `github_pat__list_pull_requests`
- **Input**: `owner`, `repo`, `state=open`, `sort=created`, `direction=asc`, `perPage=100`
- **Output**: List of open PRs with metadata (number, title, author, created_at, requested_reviewers, draft status)
- **Validate**: Response is a list (may be empty)
- **On failure**: Check repo exists and is accessible. If >100 PRs, paginate with `page` parameter.

Save the PR list to `tmp/prs.json` for downstream steps.

### Step 3: Fetch reviews for every PR
- **Mode**: `deterministic`
- **Tool**: `github_pat__pull_request_read` (method: `get_reviews`)
- **Input**: Each PR number from Step 2
- **Output**: Reviews per PR (user, state: APPROVED/COMMENTED/CHANGES_REQUESTED)
- **Validate**: Each call returns a list of review objects
- **On failure**: Log the error for that PR and continue to the next one

Use `run_python` with `tools=["github_pat__pull_request_read"]` to loop through all PRs in a single code execution. Save results to `tmp/reviews.json`.

For each PR, determine the **latest** review state per unique reviewer (a reviewer may submit multiple reviews — only the most recent state counts). Exclude the PR author from reviewer counts (self-reviews). Exclude bot accounts (login containing `[bot]`) from human approval counts.

### Step 4: Classify PRs by color
- **Mode**: `agentic`
- **Input**: PR list + reviews from Steps 2–3
- **Output**: Categorized PR report with color assignments

Apply the color logic:
- 🟢 Green: `human_approvals >= 2`
- 🟡 Yellow: `human_approvals == 1`
- 🔴 Red: `len(requested_reviewers) >= 2 AND human_approvals == 0`
- ⚪ Other: doesn't match any category (not shown in table, but counted in histogram)

Calculate age in days for each PR (today minus created_at date). Build histogram buckets: 0–7 days, 1–4 weeks, 1–3 months, 3–6 months, 6–12 months, 12+ months.

Sort all results oldest to newest by created_at.

### Step 5: Render the HTML report
- **Mode**: `agentic`
- **Tool**: Inline `<artifact type="html">` in the response
- **Input**: Classified PR data from Step 4
- **Output**: Interactive HTML report with:
  1. **Summary cards** — count of green/yellow/red/total PRs
  2. **Age histogram** — Highcharts column chart showing PR age distribution across ALL open PRs, colored from green (fresh) to red (stale)
  3. **Detail table** — rows for green/yellow/red PRs only, sorted oldest→newest, with columns: Status badge, PR number (linked), Title, Author, Created date, Age, Approvals (with approver names), Pending Reviewers

Load `html_design` and `highcharts` skills before rendering. Use theme CSS variables for colors and typography. Load Highcharts from `/vendor/highcharts/highcharts.js`.

Also save the standalone HTML report to `artifacts/pr_review_report.html` for potential SharePoint publishing.

### Step 6: Publish to SharePoint (optional)
- **Mode**: `agentic`
- **Tool**: `sharepoint_write_file` (from your SharePoint MCP server)
- **Input**: `{{sharepoint_url}}` (required, no default), the HTML report from Step 5
- **Output**: Confirmation that the report was published
- **Validate**: SharePoint write returns success
- **On failure**: Report the error to the user; the inline artifact is still available as fallback

If `{{sharepoint_url}}` is provided, publish the HTML report content to the specified SharePoint page. Extract the site and page path from the URL to construct the write call.

### Step 7: Summarize key findings
- **Mode**: `agentic`
- **Input**: Report data
- **Output**: 3–5 bullet summary below the artifact

Highlight: how many are ready to merge, how many need one more approval, how many are blocked, and call out any notably old PRs (>3 months). If published to SharePoint, confirm the URL.

## Output

An inline HTML artifact containing:
- Summary stat cards (green/yellow/red/total)
- Highcharts histogram of PR age distribution
- Color-coded table of PRs matching criteria (green/yellow/red only)
- A brief text summary of key findings
- (Optional) Published to SharePoint page

## Lessons Learned

### Do
- Use the `tools` parameter in `run_python` to batch-fetch reviews for all PRs in a single code cell — avoids 40+ sequential tool calls
- Track the **latest** review state per reviewer, not just any APPROVED review (a reviewer can approve then later request changes)
- Exclude bot approvals (like `github-actions[bot]`) from human approval counts
- Handle repos with >100 open PRs by paginating the list_pull_requests call
- Save the HTML report to `artifacts/` as a standalone file before publishing to SharePoint

### Don't
- Don't count the PR author's own reviews as approvals
- Don't use `pull_request_read` as the function name in run_python — the injected tool name is `github_pat__pull_request_read`
- Don't assume `requested_reviewers` items are dicts — they may be plain strings (logins)

### Common Failures
- **Tool name mismatch**: When using `tools=["github_pat__pull_request_read"]` in run_python, the callable is `github_pat__pull_request_read()`, not `pull_request_read()`
- **Large repos**: If >100 PRs, the first list call returns only 100 — must paginate
- **Review data shape**: Reviews are a list of dicts with `user.login` and `state` keys; handle missing fields defensively
- **SharePoint write failures**: Site permissions or URL parsing issues — always have the inline artifact as fallback

### When to Ask the User
- If the repo URL is invalid or inaccessible
- If the user wants different color criteria or thresholds
- If they want to include draft PRs in the report (currently included but could be filtered)
- If the SharePoint URL is inaccessible or returns permissions errors
