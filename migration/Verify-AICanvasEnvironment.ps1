[CmdletBinding()]
param(
    [string]$WorkspaceRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
)

$projectRoot = Join-Path ([Environment]::GetFolderPath("MyDocuments")) "AI Canvas Projects"
$settingsFile = Join-Path (Join-Path $env:LOCALAPPDATA "AI Canvas") "settings.json"

function Find-CommandPath([string[]]$Names) {
    foreach ($name in $Names) {
        $command = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($command) { return $command.Source }
    }
    return $null
}

function Find-WorkingPython {
    $launchers = @(
        @{ Name = "py.exe"; Arguments = @("-3") },
        @{ Name = "python.exe"; Arguments = @() },
        @{ Name = "python3.exe"; Arguments = @() }
    )
    foreach ($launcher in $launchers) {
        $command = Get-Command $launcher.Name -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $command) { continue }
        try {
            $arguments = @($launcher.Arguments) + @("--version")
            & $command.Source $arguments 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                return [pscustomobject]@{ Path = $command.Source; Arguments = @($launcher.Arguments) }
            }
        } catch { }
    }
    $codexRuntimeRoot = Join-Path $env:USERPROFILE ".cache\codex-runtimes"
    if (Test-Path -LiteralPath $codexRuntimeRoot) {
        $bundled = Get-ChildItem -LiteralPath $codexRuntimeRoot -Recurse -File -Filter "python.exe" -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($bundled) {
            return [pscustomobject]@{ Path = $bundled.FullName; Arguments = @() }
        }
    }
    return $null
}

$python = Find-WorkingPython
$node = Find-CommandPath @("node.exe", "node")
if (-not $node) {
    $codexRuntimeRoot = Join-Path $env:USERPROFILE ".cache\codex-runtimes"
    if (Test-Path -LiteralPath $codexRuntimeRoot) {
        $node = (Get-ChildItem -LiteralPath $codexRuntimeRoot -Recurse -File -Filter "node.exe" -ErrorAction SilentlyContinue |
            Select-Object -First 1).FullName
    }
}
$ffmpeg = Find-CommandPath @("ffmpeg.exe", "ffmpeg")
$requiredFiles = @(
    "prototype\index.html",
    "prototype\styles.css",
    "prototype\app.js",
    "prototype\server.py",
    "AI_CANVAS_MVP_SPEC.md",
    "MIGRATION_HANDOFF.md",
    "CONTINUE_WITH_CODEX.md",
    "requirements-phase2.txt"
)

$fileChecks = $requiredFiles | ForEach-Object {
    [pscustomobject]@{
        Item = $_
        Present = Test-Path -LiteralPath (Join-Path $WorkspaceRoot $_)
    }
}

Write-Host "AI Canvas environment"
[pscustomobject]@{
    Workspace = $WorkspaceRoot
    Python = $python.Path
    NodeOptional = $node
    FFmpegPhase2 = $ffmpeg
    ProjectRoot = $projectRoot
    ProjectRootPresent = Test-Path -LiteralPath $projectRoot
    SettingsPresent = Test-Path -LiteralPath $settingsFile
} | Format-List

Write-Host "Required workspace files"
$fileChecks | Format-Table -AutoSize

if (-not $python) {
    Write-Error "Python 3.11 or newer is required to run AI Canvas."
}
if ($fileChecks.Present -contains $false) {
    Write-Error "One or more required workspace files are missing. Re-extract the migration bundle."
}

if ($python) {
    Write-Host "Python version"
    $arguments = @($python.Arguments) + @("--version")
    & $python.Path $arguments
}

if ($ffmpeg) {
    Write-Host "FFmpeg is available for the future yt-dlp integration."
} else {
    Write-Warning "FFmpeg is not installed or not on PATH. It is optional now but may be required by Phase 2 downloads."
}
