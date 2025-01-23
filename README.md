# Jira Version Manager

A Python tool to manage Jira versions, supporting automatic version creation, listing, cleanup, and archiving.

## Features

- Create versions for specific dates or next month's weekdays
- List existing versions with detailed issue information
- Delete versions with optional issue migration
- Automatic cleanup of old versions with no issues
- Automatic archiving of old released versions
- Project-specific configurations for:
  - Version formats
  - Issue types
  - Release days
  - Archive settings
- Support for multiple version name formats with variables
- Dry-run mode for safe testing
- Debug mode for troubleshooting
- SSL verification control for self-signed certificates

## Installation

### From PyPI
```bash
pip install jira-version-manager
```

### From Source
```bash
git clone https://github.com/jackalski/jira-version-manager.git
cd jira-version-manager
pip install -e .
```

## Configuration

The tool can be configured in three ways (in order of precedence):

1. Environment variables (only for basic connectivity):
   ```bash
   JIRA_BASE_URL="https://your-jira-instance.com"
   JIRA_API_TOKEN="your-api-token"
   JIRA_VERIFY_SSL="false"  # Optional: disable SSL verification
   ```

2. Configuration file (located in the user's data directory):
   - Windows: `%LOCALAPPDATA%\1500100xyz\jira-version-manager\config.json`
   - Linux: `~/.local/share/jira-version-manager/config.json`
   - macOS: `~/Library/Application Support/jira-version-manager/config.json`

   Example configuration:
   ```json
   {
     "jira_base_url": "https://your-jira-instance.com",
     "jira_api_token": "your-api-token",
     "project_keys": ["PROJECT1", "PROJECT2"],
     "version_formats": {
       "standard": "{PROJECT}.W{WEEK:02d}.{YEAR}.{MONTH:02d}.{DAY:02d}",
       "intake": "{PROJECT}.INTAKE.W{WEEK:02d}.{YEAR}.{MONTH:02d}.{DAY:02d}",
       "release": "{PROJECT}.{YEAR}.{MONTH:02d}.{DAY:02d}.RELEASE"
     },
     "project_formats": {
       "default": ["standard"],
       "PROJECT1": ["standard", "release"],
       "PROJECT2": ["intake"]
     },
     "issue_types": {
       "default": ["Epic"],
       "PROJECT1": ["Epic", "Story"],
       "PROJECT2": ["Epic", "Task"]
     },
     "release_days": {
       "default": [0, 1, 2, 3],  # Monday to Thursday
       "PROJECT1": {
         "days": [0, 2, 4],      # Monday, Wednesday, Friday
         "frequency": 1          # Every week (use 2 for every two weeks)
       }
     },
     "archive_settings": {
       "default": {
         "months": 3,     # Archive after 3 months by default
         "enabled": true  # Enable archiving by default
       },
       "PROJECT1": {
         "months": 6,     # Archive after 6 months for PROJECT1
         "enabled": true
       },
       "PROJECT2": {
         "months": 1,     # Archive after 1 month for PROJECT2
         "enabled": false # Disable archiving for PROJECT2
       }
     },
     "jira_verify_ssl": true
   }
   ```

3. Default values (not recommended for production)

### Configuration Options

- `jira_base_url`: Your Jira instance URL
- `jira_api_token`: Your Jira API token
- `project_keys`: List of project keys to manage
- `version_formats`: Format patterns for version names using variables:
  - `{PROJECT}`: Project key
  - `{WEEK}`: Week number
  - `{YEAR}`: Year
  - `{MONTH}`: Month
  - `{DAY}`: Day
- `project_formats`: Format assignments per project
- `issue_types`: Issue types to include in version details
- `release_days`: Days to create versions for (0=Monday to 6=Sunday)
- `archive_settings`: Project-specific archive configuration
- `jira_verify_ssl`: Whether to verify SSL certificates

## Usage

### Common Options
All commands support:
- `--debug`: Enable debug mode
- `--dry-run`: Simulate actions without making changes
- `--no-verify-ssl`: Disable SSL certificate verification

### Show Configuration
```bash
jira-version-manager info
```

### List Versions
```bash
# List unreleased versions
jira-version-manager list PROJECT1

# Show released versions
jira-version-manager list PROJECT1 --show-released

# Show all versions
jira-version-manager list PROJECT1 --show-all

# Show detailed information with issues
jira-version-manager list PROJECT1 --detailed
```

### Create Versions
```bash
# Create for next month using default formats
jira-version-manager create

# Create for current month
jira-version-manager create --current-month

# Create with specific formats
jira-version-manager create --formats standard,release

# Create for specific date
jira-version-manager create --project-key PROJECT1 --date 2024-02-01 --formats intake,release
```

### Cleanup Versions
```bash
# Clean single project
jira-version-manager cleanup PROJECT1

# Clean all projects
jira-version-manager cleanup

# Include released versions
jira-version-manager cleanup PROJECT1 --include-released
```

Cleanup criteria:
- More than 1 week old
- No issues assigned
- Unreleased (unless --include-released is used)

### Archive Versions
```bash
# Archive using project settings
jira-version-manager archive PROJECT1

# Override archive age
jira-version-manager archive PROJECT1 --months 2

# Archive all projects
jira-version-manager archive
```

Archive criteria:
- Released versions only
- Older than specified months (project setting or override)
- Project must have archiving enabled

When archived:
1. Description prefixed with "[ARCHIVED]"
2. Marked as archived in Jira
3. Hidden from most Jira views