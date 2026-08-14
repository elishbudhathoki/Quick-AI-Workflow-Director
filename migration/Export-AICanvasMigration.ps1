[CmdletBinding()]
param(
    [string]$DestinationDirectory,
    [switch]$IncludeCredentials
)

$ErrorActionPreference = "Stop"
$workspaceRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$projectRoot = Join-Path ([Environment]::GetFolderPath("MyDocuments")) "AI Canvas Projects"
$settingsRoot = Join-Path $env:LOCALAPPDATA "AI Canvas"

if (-not $DestinationDirectory) {
    $DestinationDirectory = Join-Path $workspaceRoot "migration-bundles"
}
$destination = [System.IO.Path]::GetFullPath($DestinationDirectory)
New-Item -ItemType Directory -Path $destination -Force | Out-Null

$stamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$archivePath = Join-Path $destination "AI-Canvas-Migration-$stamp.zip"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) "ai-canvas-migration-$([Guid]::NewGuid().ToString('N'))"
$temporaryRoot = [System.IO.Path]::GetFullPath($temporaryRoot)
$systemTemp = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())

if (-not $temporaryRoot.StartsWith($systemTemp, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Temporary migration path is outside the system temporary directory."
}

try {
    $workspaceTarget = Join-Path $temporaryRoot "workspace\AI Canvas"
    $projectTarget = Join-Path $temporaryRoot "project-data\AI Canvas Projects"
    New-Item -ItemType Directory -Path $workspaceTarget -Force | Out-Null

    $excludedRootNames = @("migration-bundles", "docx_render")
    Get-ChildItem -LiteralPath $workspaceRoot -Force |
        Where-Object { $excludedRootNames -notcontains $_.Name } |
        ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $workspaceTarget -Recurse -Force
        }

    Get-ChildItem -LiteralPath $workspaceTarget -Recurse -Directory -Force |
        Where-Object { $_.Name -eq "__pycache__" } |
        ForEach-Object {
            if ($_.FullName.StartsWith($workspaceTarget, [System.StringComparison]::OrdinalIgnoreCase)) {
                Remove-Item -LiteralPath $_.FullName -Recurse -Force
            }
        }
    Get-ChildItem -LiteralPath $workspaceTarget -Recurse -File -Force |
        Where-Object { $_.Name -like "server-test*.log" } |
        Remove-Item -Force

    if (Test-Path -LiteralPath $projectRoot) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $projectTarget) -Force | Out-Null
        Copy-Item -LiteralPath $projectRoot -Destination $projectTarget -Recurse -Force
    }

    $credentialsIncluded = $false
    if ($IncludeCredentials) {
        $settingsFile = Join-Path $settingsRoot "settings.json"
        if (Test-Path -LiteralPath $settingsFile) {
            $settingsTarget = Join-Path $temporaryRoot "sensitive-settings\AI Canvas"
            New-Item -ItemType Directory -Path $settingsTarget -Force | Out-Null
            Copy-Item -LiteralPath $settingsFile -Destination (Join-Path $settingsTarget "settings.json") -Force
            $credentialsIncluded = $true
        }
    } else {
        @"
API credentials were intentionally excluded from this archive.
Re-enter provider keys in AI Canvas Settings on the destination computer, or securely copy:
%LOCALAPPDATA%\AI Canvas\settings.json
"@ | Set-Content -LiteralPath (Join-Path $temporaryRoot "CREDENTIALS_NOT_INCLUDED.txt") -Encoding UTF8
    }

    $files = Get-ChildItem -LiteralPath $temporaryRoot -Recurse -File -Force | ForEach-Object {
        [pscustomobject]@{
            path = $_.FullName.Substring($temporaryRoot.Length + 1).Replace("\", "/")
            bytes = $_.Length
            sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
    $manifest = [ordered]@{
        schemaVersion = 1
        createdAt = (Get-Date).ToUniversalTime().ToString("o")
        sourceWorkspace = $workspaceRoot
        sourceProjectRoot = $projectRoot
        credentialsIncluded = $credentialsIncluded
        fileCount = @($files).Count
        files = @($files)
    }
    $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $temporaryRoot "bundle-manifest.json") -Encoding UTF8

    Compress-Archive -Path (Join-Path $temporaryRoot "*") -DestinationPath $archivePath -CompressionLevel Optimal
    $archiveHash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    Write-Host "Migration bundle created: $archivePath"
    Write-Host "SHA256: $archiveHash"
    if ($credentialsIncluded) {
        Write-Warning "This archive contains plaintext provider API keys. Store and transfer it securely."
    } else {
        Write-Host "Provider credentials were excluded."
    }
} finally {
    if ((Test-Path -LiteralPath $temporaryRoot) -and $temporaryRoot.StartsWith($systemTemp, [System.StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

