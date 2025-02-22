#Requires -Version 5.1
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

try {
    # Check for Nuitka installation
    if (-not (Get-Command nuitka -ErrorAction SilentlyContinue)) {
        Write-Host "Installing Nuitka..." -ForegroundColor Yellow
        pip install nuitka
    }

    # Build parameters
    $nuitkaArgs = @(
        "--standalone",
        "--onefile",
        "--follow-imports",
        "--output-filename=jira-version-manager.exe",
        "--windows-disable-console",
        "--lto=yes",
        "jira_version_manager\version_manager.py"
    )

    # Execute build
    Write-Host "Starting build process..." -ForegroundColor Cyan
    nuitka @nuitkaArgs -ErrorAction Stop
    
    # Verify output
    if (Test-Path -Path "jira-version-manager.dist\jira-version-manager.exe") {
        Write-Host "Build successful! Executable created in jira-version-manager.dist\" -ForegroundColor Green
    }
    else {
        Write-Host "Build failed - executable not found" -ForegroundColor Red
        exit 1
    }
}
catch {
    Write-Host "Build error: $_" -ForegroundColor Red
    exit 1
}