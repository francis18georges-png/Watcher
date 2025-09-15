#!/usr/bin/env bash
# automation-playbook.sh
# Usage:
#   TOKEN must be exported as $TOKEN (fine-grained token with repo admin rights)
#   ./automation-playbook.sh [--dry-run] [--yes] [--branch main] [--contexts "ci/test,ci/lint"] [--pr 123] [--bot-token BOT_TOKEN]
#
# Example:
#   TOKEN="$TOKEN" ./automation-playbook.sh --yes --pr 253 --bot-token "ghp_xxx..."
set -euo pipefail

OWNER="francis18georges-png"
REPO="Watcher"
BRANCH="main"
DRY_RUN=0
ASSUME_YES=0
CONTEXTS=""
PR_TO_LABEL=""
BOT_TOKEN=""
USE_GH=0

print() { printf "%s\n" "$*"; }
err() { printf "ERROR: %s\n" "$*" >&2; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --yes) ASSUME_YES=1; shift ;;
    --branch) BRANCH="$2"; shift 2 ;;
    --contexts) CONTEXTS="$2"; shift 2 ;;
    --pr) PR_TO_LABEL="$2"; shift 2 ;;
    --bot-token) BOT_TOKEN="$2"; shift 2 ;;
    --token) export TOKEN="$2"; shift 2 ;;
    --help|-h) echo "See header of script for usage"; exit 0 ;;
    *) err "Unknown arg: $1"; exit 2 ;;
  esac
done

if command -v gh >/dev/null 2>&1; then
  if gh auth status >/dev/null 2>&1; then
    USE_GH=1
  else
    # gh present but not logged in
    USE_GH=0
  fi
fi

if [[ -z "${TOKEN-}" && "$USE_GH" -eq 0 ]]; then
  err "TOKEN not set and gh not authenticated. Export TOKEN or run 'gh auth login'."
  exit 3
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  print "[dry-run] Enabled. No destructive actions will be sent."
fi

confirm_or_exit() {
  if [[ "$ASSUME_YES" -eq 1 || "$DRY_RUN" -eq 1 ]]; then
    return 0
  fi
  read -r -p "$1 [y/N] " ans
  case "$ans" in
    [yY]|[yY][eE][sS]) return 0 ;;
    *) echo "Aborting."; exit 4 ;;
  esac
}

do_api() {
  # usage: do_api METHOD PATH DATA_JSON
  local method=$1
  local path=$2
  local data=${3-}
  if [[ "$USE_GH" -eq 1 ]]; then
    if [[ -z "$data" ]]; then
      gh api --method "$method" "$path"
    else
      gh api --method "$method" "$path" -f body="$data"
    fi
  else
    if [[ -z "$data" ]]; then
      curl -sS -H "Authorization: token $TOKEN" -H "Accept: application/vnd.github+json" "https://api.github.com/$path"
    else
      curl -sS -X "$method" -H "Authorization: token $TOKEN" -H "Accept: application/vnd.github+json" "https://api.github.com/$path" -d "$data"
    fi
  fi
}

echo "Owner: $OWNER  Repo: $REPO  Branch: $BRANCH"
echo "Using gh CLI: $USE_GH"
if [[ "$DRY_RUN" -eq 1 ]]; then echo "(dry-run)"; fi

# 1) Set default workflow permissions to write and allow approvals
echo
echo "1) Setting default workflow permissions -> write; allow approv. reviews"
confirm_or_exit "Proceed to set default workflow permissions to write?"
if [[ "$DRY_RUN" -eq 0 ]]; then
  if [[ "$USE_GH" -eq 1 ]]; then
    # NOTE: use --raw-field so boolean true is sent as a JSON boolean (not as a string)
    gh api --method PUT repos/"$OWNER"/"$REPO"/actions/permissions/workflow -f default_workflow_permissions=write --raw-field can_approve_pull_request_reviews=true
  else
    curl -S -X PUT \
      -H "Authorization: token $TOKEN" \
      -H "Accept: application/vnd.github+json" \
      "https://api.github.com/repos/$OWNER/$REPO/actions/permissions/workflow" \
      -d '{
        "default_workflow_permissions": "write",
        "can_approve_pull_request_reviews": true
      }'
  fi
else
  echo "(dry-run) would PUT /repos/$OWNER/$REPO/actions/permissions/workflow {default_workflow_permissions: write, can_approve_pull_request_reviews: true}"
fi

# 2) Allow actions (choose all for convenience; you can change to local_only for higher security)
echo
echo "2) Setting allowed actions -> all (change if you prefer 'local_only')"
confirm_or_exit "Proceed to allow actions = all?"
if [[ "$DRY_RUN" -eq 0 ]]; then
  if [[ "$USE_GH" -eq 1 ]]; then
    gh api --method PUT repos/"$OWNER"/"$REPO"/actions/permissions -f enabled=true -f allowed_actions=all
  else
    curl -S -X PUT \
      -H "Authorization: token $TOKEN" \
      -H "Accept: application/vnd.github+json" \
      "https://api.github.com/repos/$OWNER/$REPO/actions/permissions" \
      -d '{
        "enabled": true,
        "allowed_actions": "all"
      }'
  fi
else
  echo "(dry-run) would PUT /repos/$OWNER/$REPO/actions/permissions {enabled:true, allowed_actions: all}"
fi

# 3) Configure branch protection
echo
echo "3) Configuring branch protection for $BRANCH"
if [[ -n "$CONTEXTS" ]]; then
  IFS=',' read -r -a ctxs <<< "$CONTEXTS"
  contexts_json=$(printf '"%s",' "${ctxs[@]}")
  contexts_json="[${contexts_json%,}]"
else
  contexts_json="null"
fi

# Build JSON body respecting contexts presence
if [[ "$contexts_json" == "null" ]]; then
  protection_payload=$(
cat <<'JSON'
{
  "required_status_checks": null,
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 1
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON
)
else
  protection_payload=$(
cat <<JSON
{
  "required_status_checks": {
    "strict": true,
    "contexts": $contexts_json
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 1
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON
)
fi

echo "Branch protection payload:"
echo "$protection_payload" | sed 's/./&/g'  # show payload
confirm_or_exit "Proceed to apply branch protection to $BRANCH?"
if [[ "$DRY_RUN" -eq 0 ]]; then
  if [[ "$USE_GH" -eq 1 ]]; then
    gh auth status >/dev/null 2>&1 && curl -S -X PUT -H "Authorization: token $TOKEN" -H "Accept: application/vnd.github+json" "https://api.github.com/repos/$OWNER/$REPO/branches/$BRANCH/protection" -d "$protection_payload"
  else
    curl -S -X PUT -H "Authorization: token $TOKEN" -H "Accept: application/vnd.github+json" "https://api.github.com/repos/$OWNER/$REPO/branches/$BRANCH/protection" -d "$protection_payload"
  fi
else
  echo "(dry-run) would PUT /repos/$OWNER/$REPO/branches/$BRANCH/protection with above payload"
fi

# 4) Create / update bot secret if provided
if [[ -n "$BOT_TOKEN" ]]; then
  echo
  echo "4) Creating/updating repo secret ACTIONS_BOT_TOKEN"
  confirm_or_exit "Proceed to create/update the secret ACTIONS_BOT_TOKEN?"
  if [[ "$DRY_RUN" -eq 0 ]]; then
    if command -v gh >/dev/null 2>&1 && [[ "$USE_GH" -eq 1 ]]; then
      printf "%s" "$BOT_TOKEN" | gh secret set ACTIONS_BOT_TOKEN --repo "$OWNER/$REPO" --body -
    else
      err "No gh authenticated to set secret automatically. Please run: gh secret set ACTIONS_BOT_TOKEN --repo $OWNER/$REPO"
    fi
  else
    echo "(dry-run) would set ACTIONS_BOT_TOKEN"
  fi
fi

# 5) List workflows and recent runs
echo
echo "5) Listing workflows and recent runs (automerge/auto-label)"
if [[ "$DRY_RUN" -eq 0 ]]; then
  if [[ "$USE_GH" -eq 1 ]]; then
    gh workflow list --repo "$OWNER/$REPO" || true
    echo
    gh run list --repo "$OWNER/$REPO" --limit 20 || true
  else
    curl -sS -H "Authorization: token $TOKEN" -H "Accept: application/vnd.github+json" "https://api.github.com/repos/$OWNER/$REPO/actions/workflows" | python3 -m json.tool || true
    echo
    curl -sS -H "Authorization: token $TOKEN" -H "Accept: application/vnd.github+json" "https://api.github.com/repos/$OWNER/$REPO/actions/runs?per_page=20" | python3 -m json.tool || true
  fi
else
  echo "(dry-run) would list workflows and runs"
fi

# 6) Optionally label a PR to test automerge workflow
if [[ -n "$PR_TO_LABEL" ]]; then
  echo
  echo "6) Adding label 'automerge' to PR #$PR_TO_LABEL (test trigger)"
  confirm_or_exit "Proceed to add label 'automerge' to PR #$PR_TO_LABEL?"
  if [[ "$DRY_RUN" -eq 0 ]]; then
    if [[ "$USE_GH" -eq 1 ]]; then
      gh pr edit "$PR_TO_LABEL" --add-label automerge --repo "$OWNER/$REPO"
    else
      curl -sS -X POST -H "Authorization: token $TOKEN" -H "Accept: application/vnd.github+json" "https://api.github.com/repos/$OWNER/$REPO/issues/$PR_TO_LABEL/labels" -d '["automerge"]'
    fi
    echo "Label added (check Actions tab / PR checks)"
  else
    echo "(dry-run) would add label automerge to PR #$PR_TO_LABEL"
  fi
fi

echo
echo "Playbook completed. Review output above for API responses and errors."
echo "If you didn't run in dry-run and didn't pass --yes, the script asked before making changes."