$ErrorActionPreference = "Stop"
$repoFullName = "Mishaadevv/ZeqouHCLI"
$repoUrl = "https://github.com/$repoFullName.git"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is not installed. Install Git for Windows first."
}

if (-not (Test-Path ".git")) {
    git init
    if ($LASTEXITCODE -ne 0) { throw "git init failed." }
}
git branch -M main
if ($LASTEXITCODE -ne 0) { throw "Could not select the main branch." }

git add -A
if ($LASTEXITCODE -ne 0) { throw "git add failed." }
git diff --cached --quiet
$hasStagedChanges = ($LASTEXITCODE -ne 0)
if ($hasStagedChanges) {
    git commit -m "Initial public release: ZeqouHCLI 0.5.0"
    if ($LASTEXITCODE -ne 0) { throw "Commit failed. Configure git user.name and user.email, then retry." }
}

# Prefer GitHub CLI: it can create the requested public repository and push in one step.
if (Get-Command gh -ErrorAction SilentlyContinue) {
    gh auth status
    if ($LASTEXITCODE -eq 0) {
        gh repo view $repoFullName *> $null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Creating public repository $repoFullName ..."
            gh repo create $repoFullName --public --source . --remote origin --push
            if ($LASTEXITCODE -ne 0) { throw "GitHub repository creation/push failed. Check gh auth and repository name." }
            Write-Host "Published: https://github.com/$repoFullName"
            exit 0
        }
    }
    else {
        Write-Warning "GitHub CLI is installed but not authenticated. Run: gh auth login"
    }
}

# Fallback: a repository must be created through the GitHub website first.
$remote = git remote get-url origin 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Create an EMPTY public repository named ZeqouHCLI at https://github.com/new (do not add a README/license), then continue."
    git remote add origin $repoUrl
}
elseif ($remote -ne $repoUrl) {
    throw "Origin is set to '$remote', not '$repoUrl'. Review it before pushing."
}

Write-Host "Pushing main to $repoUrl"
git push -u origin main
if ($LASTEXITCODE -ne 0) { throw "Push failed. Ensure the empty repository exists and GitHub authentication works." }
Write-Host "Published: https://github.com/$repoFullName"
