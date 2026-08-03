$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    $env:PYTHONPATH = Join-Path $projectRoot "src"
    python -m pytest -q
    python -m compileall -q src
    git diff --check

    $trackedPdfs = git ls-files "*.pdf"
    if ($trackedPdfs) {
        throw "Restricted PDF files are tracked by Git: $trackedPdfs"
    }

    $sensitivePatterns = "Samira|Rauf|Fox Hollow|SSN|231,239|181,519|text_preview"
    $publicArtifacts = @(
        Get-ChildItem -LiteralPath "submission" -File
        Get-Item -LiteralPath "docs/index.html"
    )
    $hits = $publicArtifacts |
        Select-String -Pattern $sensitivePatterns -CaseSensitive:$false
    if ($hits) {
        throw "Potential PII found in submission artifacts: $hits"
    }

    Write-Host "Submission verification passed." -ForegroundColor Green
}
finally {
    Pop-Location
}
