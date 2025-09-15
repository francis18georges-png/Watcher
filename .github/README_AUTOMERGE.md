# Automerge workflow

This repository includes a workflow `.github/workflows/automerge.yml` that will attempt to automatically merge pull requests when they are labeled `automerge`.

How it works:
- The workflow listens to `pull_request_target` events (label added, opened, synchronize).
- When a PR is labeled `automerge`, the workflow runs the `pascalgn/automerge-action` action which will attempt to merge the PR once required checks pass.
- The workflow uses the repository `GITHUB_TOKEN` with `pull-requests: write` and `contents: write` permissions.

Usage:
1. Create a branch and open a PR targeting `main` with at least one commit different from `main`.
2. Add the label `automerge` to the PR (via CLI or UI):
   - CLI example: `gh pr edit <PR_NUMBER> --add-label automerge --repo francis18georges-png/Watcher`
3. The workflow will run and, once checks are green, attempt to merge the PR.

Troubleshooting:
- If the workflow does not run or fails to merge, check Actions > Runs and review the logs.
- If the PR cannot be merged due to branch rules (ruleset), you may need to add the GitHub Actions app or the repository's GitHub Actions principal to the ruleset bypass list or adjust the ruleset to allow workflow merges. To inspect rulesets via CLI:
  - `gh api repos/francis18georges-png/Watcher/rulesets --jq '.'`
  - `gh api repos/francis18georges-png/Watcher/rulesets/<ID> --jq '.'`

Security note:
- If you need the workflow to act with a custom PAT, store it as a secret (e.g., `ACTIONS_BOT_TOKEN`) and update the workflow to use that secret. Prefer using `GITHUB_TOKEN` where possible.

If merging remains blocked because the ruleset restricts updates, either add the `actions` principal or this repository's workflow runner to the bypass list in Settings → Branches → Rulesets (UI), or I can prepare the exact API calls to update the bypass list if you prefer.