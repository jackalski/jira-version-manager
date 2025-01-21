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
git clone https://github.com/pszmitkowski/jira-version-manager.git
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
   JIRA_VERSION_FORMATS='{"standard": "{}.W{:02d}.{}.{:02d}.{:02d}", "intake": "{}.INTAKE.W{:02d}.{}.{:02d}.{:02d}", "release": "{}.RELEASE.{}.{:02d}.{:02d}"}'
   JIRA_VERIFY_SSL="false"  # Optional: disable SSL verification
   JIRA_PROJECT_FORMATS='{"PROJECT1": ["standard", "release"], "PROJECT2": ["intake"]}'  # Optional: project-specific formats
   ```

2. Configuration file (`~/.jira_version_manager.json`):
   ```json
   {
     "jira_base_url": "https://your-jira-instance.com",
     "jira_api_token": "your-api-token",
     "project_keys": ["PROJECT1", "PROJECT2"],
     "version_formats": {
       "standard": "{}.W{:02d}.{}.{:02d}.{:02d}",
       "intake": "{}.INTAKE.W{:02d}.{}.{:02d}.{:02d}",
       "release": "{}.RELEASE.{}.{:02d}.{:02d}"
     },
     "verify_ssl": false,
     "project_formats": {
       "PROJECT1": ["standard", "release"],
       "PROJECT2": ["intake"]
     }
   }
   ```

3. Default values (not recommended for production)

### Configuration Options

- `jira_base_url`: Your Jira instance URL
- `jira_api_token`: Your Jira API token
- `project_keys`: List of Jira project keys to manage
- `version_formats`: Dictionary of named version format patterns
- `project_formats`: Map of project keys to lists of format names to use
- `verify_ssl`: Whether to verify SSL certificates (default: true)

### Version Format Patterns

Version formats are defined as named patterns in the `version_formats` configuration. Each pattern uses Python's string formatting with the following placeholders:
- `{}` - Project key (first placeholder)
- `{:02d}` - Week number (padded with zero)
- `{}` - Year
- `{:02d}` - Month (padded with zero)
- `{:02d}` - Day (padded with zero)

The "standard" format must always be defined as it serves as the default format when no other format is specified.

Example format definitions:
```json
{
  "version_formats": {
    "standard": "{}.W{:02d}.{}.{:02d}.{:02d}",         // PROJECT1.W01.2024.01.15
    "intake": "{}.INTAKE.W{:02d}.{}.{:02d}.{:02d}",    // PROJECT1.INTAKE.W01.2024.01.15
    "release": "{}.RELEASE.{}.{:02d}.{:02d}"           // PROJECT1.RELEASE.2024.01.15
  }
}
```

### Project-Specific Formats

You can specify which format patterns to use for each project using the `project_formats` configuration:

```json
{
  "project_formats": {
    "PROJECT1": ["standard", "release"],  // Will create two versions using both formats
    "PROJECT2": ["intake"],               // Will create one version using the intake format
    "PROJECT3": null                      // Will use the standard format by default
  }
}
```

If a project isn't listed in `project_formats` or has no formats specified, it will automatically use the "standard" format. The "standard" format must be defined in `version_formats` as it serves as the default format.

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
     "verify_ssl": false
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

Create versions for specific project using its default formats:
```bash
jira-version-manager create --project-key PROJECT1
```

Use dry-run mode to test:
```bash
jira-version-manager create --dry-run --project-key PROJECT1 --formats standard
```

### Delete Versions

Delete a version:
```bash
jira-version-manager delete PROJECT1 "1.0.0"
```

Delete and move issues to another version:
```bash
jira-version-manager delete PROJECT1 "1.0.0" --move-to "1.0.1"
```

## Development

### Setup Development Environment
```bash
# Clone the repository
git clone https://github.com/pszmitkowski/jira-version-manager.git
cd jira-version-manager

# Create and activate virtual environment (Windows PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install development dependencies
pip install -e ".[dev]"
```

### Running Tests
```bash
pytest
```

With coverage:
```bash
pytest --cov=jira_version_manager tests/
```

### Code Style
```bash
flake8 jira_version_manager tests
mypy jira_version_manager
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

Piotr Szmitkowski (pszmitkowski@gmail.com)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
