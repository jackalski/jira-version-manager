# Jira Version Manager

A Python tool to manage Jira versions, supporting automatic version creation, listing, and deletion.

## Features

- Create versions for specific dates or next month's weekdays (Mon-Thu)
- List existing versions for a project
- Delete versions with optional issue migration
- Check for existing versions and their associated issues
- Support for multiple version name formats
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

1. Environment variables:
   ```bash
   JIRA_BASE_URL="https://your-jira-instance.com"
   JIRA_API_TOKEN="your-api-token"
   JIRA_PROJECT_KEYS="PROJECT1,PROJECT2"
   JIRA_VERSION_FORMATS='{"standard": "{PROJECT}.W{WEEK:02d}.{YEAR}.{MONTH:02d}.{DAY:02d}", "intake": "{PROJECT}.INTAKE.W{WEEK:02d}.{YEAR}.{MONTH:02d}.{DAY:02d}", "release": "{PROJECT}.{YEAR}.{MONTH:02d}.{DAY:02d}.RELEASE"}'
   JIRA_VERIFY_SSL="false"  # Optional: disable SSL verification
   JIRA_PROJECT_FORMATS='{"default": ["standard"], "PROJECT1": ["standard", "release"], "PROJECT2": ["intake"]}'  # Optional: project-specific formats
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
       "default": [0, 1, 2, 3],
       "PROJECT1": {
         "days": [0, 2, 4],
         "frequency": 1
       }
     },
     "jira_verify_ssl": false
   }
   ```

3. Default values (not recommended for production)

### Configuration Options

- `jira_base_url`: Your Jira instance URL
- `jira_api_token`: Your Jira API token
- `project_keys`: List of Jira project keys to manage
- `version_formats`: Dictionary of named version format patterns
- `project_formats`: Map of project keys to lists of format names to use
- `issue_types`: Configuration for issue types to show in detailed view
  - `default`: Default issue types to show (defaults to ["Epic"])
  - Per-project settings override the default
- `release_days`: Configuration for version creation days
  - `default`: Default days (0=Monday to 6=Sunday)
  - Per-project settings with custom days and frequency
- `verify_ssl`: Whether to verify SSL certificates (default: true)

### Version Format Patterns

Version formats are defined as named patterns in the `version_formats` configuration. Each pattern uses named variables:
- `{PROJECT}` - Project key
- `{WEEK}` - Week number (can use :02d for zero padding)
- `{YEAR}` - Year
- `{MONTH}` - Month (can use :02d for zero padding)
- `{DAY}` - Day (can use :02d for zero padding)

The variables can be used in any order and combined with static text. The "standard" format must always be defined as it serves as the default format when no other format is specified.

Example format definitions:
```json
{
  "version_formats": {
    "standard": "{PROJECT}.W{WEEK:02d}.{YEAR}.{MONTH:02d}.{DAY:02d}",         // PROJECT1.W01.2024.01.15
    "intake": "{PROJECT}.INTAKE.W{WEEK:02d}.{YEAR}.{MONTH:02d}.{DAY:02d}",    // PROJECT1.INTAKE.W01.2024.01.15
    "release": "{PROJECT}.{YEAR}.{MONTH:02d}.{DAY:02d}.RELEASE",              // PROJECT1.2024.01.15.RELEASE
    "custom": "V{YEAR}{MONTH:02d}{DAY:02d}-{PROJECT}-W{WEEK:02d}"            // V20240115-PROJECT1-W01
  }
}
```

### Project-Specific Formats

You can specify which format patterns to use for each project using the `project_formats` configuration:

```json
{
  "project_formats": {
    "default": ["standard"],                // Default format for all projects
    "PROJECT1": ["standard", "release"],    // Uses both standard and release formats
    "PROJECT2": ["intake"]                  // Uses only intake format
  }
}
```

If a project isn't listed in `project_formats`, it will use the formats specified in `project_formats.default`. If no default is specified, it will use the "standard" format.

### Issue Type Filtering

You can configure which issue types to show in the detailed view:

```json
{
  "issue_types": {
    "default": ["Epic"],                    // Show only Epics by default
    "PROJECT1": ["Epic", "Story"],          // Show Epics and Stories for PROJECT1
    "PROJECT2": ["Epic", "Task"]            // Show Epics and Tasks for PROJECT2
  }
}
```

### Release Days Configuration

Configure which days versions should be created for:

```json
{
  "release_days": {
    "default": [0, 1, 2, 3],               // Monday to Thursday by default
    "PROJECT1": {
      "days": [0, 2, 4],                   // Monday, Wednesday, Friday
      "frequency": 1                        // Every week (use 2 for every two weeks)
    }
  }
}
```

## Usage

### SSL Verification

SSL verification can be controlled in three ways (in order of precedence):

1. Command line argument:
   ```bash
   jira-version-manager --no-verify-ssl list PROJECT1
   ```

2. Environment variable:
   ```bash
   JIRA_VERIFY_SSL="false"
   ```

3. Configuration file:
   ```json
   {
     "jira_verify_ssl": false
   }
   ```

If not specified, SSL verification is enabled by default. When disabled through any method, SSL certificate verification warnings will be suppressed.

### Common Options
All commands support the following options:
- `--debug`: Enable debug mode
- `--dry-run`: Simulate actions without making changes
- `--no-verify-ssl`: Disable SSL certificate verification (overrides config file and environment settings)

### Show Configuration
```bash
jira-version-manager info
```

### List Versions

By default, only unreleased versions are shown:
```bash
jira-version-manager list PROJECT1
```

Show only released versions:
```bash
jira-version-manager list PROJECT1 --show-released
```

Show all versions (both released and unreleased):
```bash
jira-version-manager list PROJECT1 --show-all
```

Show detailed information including issues (filtered by configured issue types):
```bash
jira-version-manager list PROJECT1 --detailed
```

List with SSL verification disabled:
```bash
jira-version-manager list PROJECT1 --no-verify-ssl
```

### Create Versions

Create versions for next month using project's default formats:
```bash
jira-version-manager create
```

Create versions for current month:
```bash
jira-version-manager create --current-month
```

Create versions using specific formats:
```bash
jira-version-manager create --formats standard,release
```

Create version for specific date and formats:
```bash
jira-version-manager create --project-key PROJECT1 --date 2024-02-01 --formats intake,release
```