<#
PowerShell script to push current branch, create "status:queued-for-merge" label if needed,
and add the label to a PR to trigger the merge queue workflow once QA and maintainer approvals are present.

Usage:
  # from repo root
  .\automerge-apply.ps1               # defaults: repo francis18georges-png/Watcher, PR 253
  .\automerge-apply.ps1 -Pr 123      # specify PR number
  .\automerge-apply.ps1 -Repo "owner/repo" -Pr 45

Requirements:
 - git available in PATH
 - Preferably gh (GitHub CLI) authenticated; otherwise set environment variable GITHUB_TOKEN
   to a PAT or fine-grained token with repo access.
#>

param(
  [string] $Repo = "francis18georges-png/Watcher",
  [int] $Pr = 253
)

function Write-Info($m){ Write-Host "[info] $m" -ForegroundColor Cyan }
function Write-Err($m){ Write-Host "[error] $m" -ForegroundColor Red }

# determine current branch
$branch = (git rev-parse --abbrev-ref HEAD) 2>$null
if (-not $branch) {
  Write-Err "Cannot determine current git branch. Run this script from inside a git repo."
  exit 1
}
Write-Info "Current branch: $branch"

# push current branch
Write-Info "Pushing branch $branch to origin..."
$push = git push origin $branch
if ($LASTEXITCODE -ne 0) {
  Write-Err "git push failed. Inspect output above. Aborting."
  exit 2
}
Write-Info "Push OK."

$labelName = "status:queued-for-merge"
$labelColor = "6F42C1"
$labelDesc = "Queue PR for auto-merge when QA & maintainer approvals are done"

# Try GitHub CLI first
$ghPath = Get-Command gh -ErrorAction SilentlyContinue
if ($ghPath) {
  Write-Info "gh CLI found. Using gh to create/add label (if possible)."

  # ensure gh is authenticated for github.com
  $authOk = $true
  try {
    gh auth status --hostname github.com > $null 2>&1
    if ($LASTEXITCODE -ne 0) { $authOk = $false }
  } catch { $authOk = $false }

  if (-not $authOk) {
    Write-Info "gh is not authenticated. You can run 'gh auth login' or set GITHUB_TOKEN env var. Falling back to API if token present."
  } else {
    # create label (ignore error if already exists)
    Write-Info "Creating label '$labelName' (if not exists)..."
    gh label create $labelName --color $labelColor --description $labelDesc --repo $Repo 2>$null
    if ($LASTEXITCODE -eq 0) {
      Write-Info "Label created (or existed)."
    } else {
      Write-Info "Label create may have failed (it might already exist), continuing..."
    }

    # add label to PR
    Write-Info "Adding label to PR #$Pr..."
    gh pr edit $Pr --add-label $labelName --repo $Repo
    if ($LASTEXITCODE -eq 0) {
      Write-Info "Label '$labelName' added to PR #$Pr. Ensure `status:maintainer-approved` and `status:qa-approved` are also present."
      exit 0
    } else {
      Write-Err "Failed to add label to PR via gh. Fall back to API if token present."
    }
  }
}

# Fallback: use GitHub API via GITHUB_TOKEN env var
$token = $env:GITHUB_TOKEN
if (-not $token) {
  Write-Err "No gh CLI authenticated and GITHUB_TOKEN not set. Please set GITHUB_TOKEN (or use gh) and re-run."
  Write-Host ""
  Write-Host "Examples:"
  Write-Host "  # set in current shell (Windows PowerShell):"
  Write-Host "  $env:GITHUB_TOKEN = 'ghp_xxx...'"
  Write-Host "  .\\automerge-apply.ps1"
  exit 3
}

# Parse repo owner/name
if ($Repo -notmatch "/") {
  Write-Err "Repo must be in 'owner/name' format."
  exit 4
}
$parts = $Repo.Split('/')
$owner = $parts[0]
$repoName = $parts[1]

$apiBase = "https://api.github.com"

# Create label via API (ignore 422 if exists)
Write-Info "Creating label via REST API (if not exists)..."
$labelBody = @{
  name = $labelName
  color = $labelColor
  description = $labelDesc
} | ConvertTo-Json

try {
  $resp = Invoke-RestMethod -Method Post -Uri "$apiBase/repos/$owner/$repoName/labels" -Headers @{
    Authorization = "token $token"
    Accept = "application/vnd.github+json"
    "User-Agent" = "queued-for-merge-script"
  } -Body $labelBody -ErrorAction Stop
  Write-Info "Label created."
} catch {
  $status = $null
  try { $status = $_.Exception.Response.StatusCode.Value__ } catch {}
  if ($status -eq 422) {
    Write-Info "Label already exists (HTTP 422). Continuing."
  } else {
    Write-Info "Label create request failed with status $status. Continuing to try adding label to PR."
  }
}

# Add label to PR via Issues API
Write-Info "Adding label to PR #$Pr via REST API..."
$labelAddBody = @($labelName) | ConvertTo-Json

try {
  $resp2 = Invoke-RestMethod -Method Post -Uri "$apiBase/repos/$owner/$repoName/issues/$Pr/labels" -Headers @{
    Authorization = "token $token"
    Accept = "application/vnd.github+json"
    "User-Agent" = "queued-for-merge-script"
  } -Body $labelAddBody -ErrorAction Stop
  Write-Info "Label added to PR #$Pr. Ensure `status:maintainer-approved` and `status:qa-approved` are also present."
  exit 0
} catch {
  Write-Err "Failed to add label to PR #$Pr via API: $($_.Exception.Message)"
  exit 5
}