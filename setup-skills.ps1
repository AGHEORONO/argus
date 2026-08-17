# Setup and install all skills automatically for Claude Code and Antigravity agents
$HOME_DIR = [System.Environment]::GetFolderPath('UserProfile')
$TEMP_DIR = Join-Path $env:TEMP "agent-skills-temp"

$claudeSkills = Join-Path $HOME_DIR ".claude\skills"
$agentsSkills = Join-Path $HOME_DIR ".agents\skills"
$agentsRules  = Join-Path $HOME_DIR ".agents\rules"

foreach ($dir in @($claudeSkills, $agentsSkills, $agentsRules, $TEMP_DIR)) {
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
}

# 1. AI Second Brain
$sbRepo = "https://github.com/charlie947/ai-second-brain"
foreach ($target in @($claudeSkills, $agentsSkills)) {
    $dest = Join-Path $target "ai-second-brain"
    if (-not (Test-Path $dest)) {
        Write-Host "Cloning ai-second-brain into $dest..."
        git clone $sbRepo $dest
    } else {
        Write-Host "Updating ai-second-brain in $dest..."
        git -C $dest pull
    }
}

# 2. Post-Karpathy Agentic Engineering
$pkRepo = "https://github.com/ramsani/Post-Karpathy-Agentic-Engineering"
foreach ($target in @($claudeSkills, $agentsSkills)) {
    $dest = Join-Path $target "post-karpathy"
    if (-not (Test-Path $dest)) {
        Write-Host "Cloning post-karpathy into $dest..."
        git clone $pkRepo $dest
    } else {
        Write-Host "Updating post-karpathy in $dest..."
        git -C $dest pull
    }
}

# 3. Ponytail (Lazy Senior Dev Mode)
$ptRepo = "https://github.com/dietrichgebert/ponytail"
$ptTemp = Join-Path $TEMP_DIR "ponytail"
if (-not (Test-Path $ptTemp)) {
    Write-Host "Cloning ponytail into temp cache..."
    git clone $ptRepo $ptTemp
} else {
    Write-Host "Updating ponytail temp cache..."
    git -C $ptTemp pull
}

Write-Host "Installing Ponytail skills & rules..."
Copy-Item -Recurse -Force (Join-Path $ptTemp "skills\*") $agentsSkills
Copy-Item -Recurse -Force (Join-Path $ptTemp "skills\*") $claudeSkills
if (Test-Path (Join-Path $ptTemp ".agents\rules\ponytail.md")) {
    Copy-Item -Force (Join-Path $ptTemp ".agents\rules\ponytail.md") (Join-Path $agentsRules "ponytail.md")
}

Write-Host "`nAll skills (ai-second-brain, post-karpathy, ponytail) installed and updated successfully!" -ForegroundColor Green
