param(
    [Parameter(Mandatory = $true)]
    [string]$ProfileDir,

    [Parameter(Mandatory = $true)]
    [string]$ExtractFile,

    [ValidateSet("linkedin", "dice")]
    [string]$Source = "linkedin",

    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$profilePath = (Resolve-Path -LiteralPath $ProfileDir).Path
$extractPath = (Resolve-Path -LiteralPath $ExtractFile).Path
$configPath = Join-Path $profilePath "config.json"
if (-not (Test-Path -LiteralPath $configPath)) {
    throw "Profile config not found: $configPath"
}

$config = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json
$outputRelative = if ($config.paths.output) { $config.paths.output } else { "output" }
$outputDirectory = Join-Path $profilePath $outputRelative
$dateStamp = Get-Date -Format "yyyy-MM-dd"

if ($Source -eq "linkedin") {
    & $Python (Join-Path $PSScriptRoot "search_linkedin.py") --profile-dir $profilePath --input $extractPath
    $filteredPath = Join-Path $outputDirectory "linkedin_jobs_$dateStamp.json"
} else {
    & $Python (Join-Path $PSScriptRoot "search_dice.py") --profile-dir $profilePath --input $extractPath
    $filteredPath = Join-Path $outputDirectory "dice_extract.json"
}
if ($LASTEXITCODE -ne 0) { throw "Filtering failed with exit code $LASTEXITCODE" }

& $Python (Join-Path $PSScriptRoot "journal.py") --profile-dir $profilePath --add $filteredPath
if ($LASTEXITCODE -ne 0) { throw "Journal update failed with exit code $LASTEXITCODE" }

& $Python (Join-Path $PSScriptRoot "run_scoring.py") --profile-dir $profilePath
if ($LASTEXITCODE -ne 0) { throw "Scoring failed with exit code $LASTEXITCODE" }

Write-Host "Profile workflow complete. No applications were submitted."

