$ErrorActionPreference = "Stop"

$RepoDir  = Split-Path $PSScriptRoot -Parent
$VenvDir  = Join-Path $RepoDir ".venv"
$Python   = Join-Path $VenvDir "Scripts\python.exe"

Write-Host "Setting up file-search-mcp from: $RepoDir"

# Setup virtual env
if (-not (Test-Path $VenvDir)) {
    python -m venv $VenvDir
    Write-Host "Created venv at $VenvDir"
}

& $Python -m pip install --quiet --upgrade pip
& $Python -m pip install --quiet mcp
Write-Host "Dependencies installed."

# modify claude_desktop_config.json
$ConfigDir  = Join-Path $env:APPDATA "Claude"
$ConfigFile = Join-Path $ConfigDir "claude_desktop_config.json"

if (-not (Test-Path $ConfigDir)) {
    New-Item -ItemType Directory -Path $ConfigDir | Out-Null
}

$NewEntry = @{
    command = $Python
    args    = @("$RepoDir\src\main.py", "$env:USERPROFILE\")
}

if (-not (Test-Path $ConfigFile)) {
    $Config = @{ mcpServers = @{ "file-search" = $NewEntry } }
} else {
    $Config = Get-Content $ConfigFile -Raw | ConvertFrom-Json
    if (-not $Config.mcpServers) {
        $Config | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{})
    }
    $Config.mcpServers | Add-Member -NotePropertyName "file-search" -NotePropertyValue $NewEntry -Force
}

$Config | ConvertTo-Json -Depth 10 | Set-Content $ConfigFile -Encoding UTF8
Write-Host "Updated $ConfigFile"

Write-Host ""
Write-Host "Done. Restart Claude Desktop to pick up the new MCP server."
