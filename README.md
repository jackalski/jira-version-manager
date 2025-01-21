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
   JIRA_VERSION_FORMATS="{}.W{:02d}.{}.{:02d}.{:02d},{}.INTAKE.W{:02d}.{}.{:02d}.{:02d}"
   ```

2. Configuration file (`~/.jira_version_manager.json`):
   ```json
   {
     "jira_base_url": "https://your-jira-instance.com",
     "jira_api_token": "your-api-token",
     "project_keys": ["PROJECT1", "PROJECT2"],
     "version_formats": [
       "{}.W{:02d}.{}.{:02d}.{:02d}",
       "{}.INTAKE.W{:02d}.{}.{:02d}.{:02d}"
     ]
   }
   ```

3. Default values (not recommended for production)

## Usage

### Show Configuration
```bash
jira-version-manager info
```

### List Versions
```bash
jira-version-manager list PROJECT1
```

### Create Versions

Create versions for next month (default behavior):
```bash
jira-version-manager create
```

Create version for specific date:
```bash
jira-version-manager create --project-key PROJECT1 --date 2024-02-01
```

Use dry-run mode to test:
```bash
jira-version-manager create --dry-run --project-key PROJECT1 --date 2024-02-01
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
