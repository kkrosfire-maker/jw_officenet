# Shared utilities for Claude Code backup/restore scripts

function Get-MemoryKey {
    param([string]$WorkspacePath)
    $drive = $WorkspacePath.Substring(0, 1)
    $rest  = $WorkspacePath.Substring(2) -replace '\\', '-'
    return "$drive-$rest"
}

function Get-SkillNames {
    param([string]$WorkspacePath)
    $lockFile = "$WorkspacePath\skills-lock.json"
    if (-not (Test-Path $lockFile)) { return @() }
    return (Get-Content $lockFile -Raw | ConvertFrom-Json).skills.PSObject.Properties.Name
}
