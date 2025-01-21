# Test setup script for Jira Version Manager
Write-Host "Testing Jira Version Manager Setup" -ForegroundColor Green

# Create and activate virtual environment
Write-Host "`nCreating virtual environment..." -ForegroundColor Yellow
python -m venv venv
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to create virtual environment" -ForegroundColor Red
    exit 1
}

Write-Host "Activating virtual environment..." -ForegroundColor Yellow
.\venv\Scripts\Activate.ps1

# Install development dependencies
Write-Host "`nInstalling package with development dependencies..." -ForegroundColor Yellow
pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to install package" -ForegroundColor Red
    exit 1
}

# Run tests with coverage
Write-Host "`nRunning tests..." -ForegroundColor Yellow
pytest --cov=jira_version_manager tests/
if ($LASTEXITCODE -ne 0) {
    Write-Host "Tests failed" -ForegroundColor Red
    exit 1
}

# Run code quality checks
Write-Host "`nRunning code quality checks..."
flake8 jira_version_manager tests
mypy jira_version_manager

# Test CLI
Write-Host "`nTesting CLI..." -ForegroundColor Yellow
jira-version-manager --help
if ($LASTEXITCODE -ne 0) {
    Write-Host "CLI test failed" -ForegroundColor Red
    exit 1
}

Write-Host "`nTest environment setup complete!"

# Suggested GitHub Repository Settings
Write-Host "`nSuggested GitHub Repository Settings:" -ForegroundColor Cyan
Write-Host "1. Branch Protection Rules for 'main':"
Write-Host "   - Require pull request reviews"
Write-Host "   - Require status checks to pass"
Write-Host "   - Require branches to be up to date"
Write-Host "   - Include administrators"
Write-Host "2. Security:"
Write-Host "   - Enable Dependabot alerts"
Write-Host "   - Enable automated security fixes"
Write-Host "3. Actions:"
Write-Host "   - Enable GitHub Actions"
Write-Host "   - Add PYPI_API_TOKEN secret for automated releases"
Write-Host "4. Pages:"
Write-Host "   - Enable GitHub Pages for documentation"
Write-Host "5. Issues:"
Write-Host "   - Enable issue templates for bugs and features"
Write-Host "6. Labels:"
Write-Host "   - Add labels for issue categorization" 