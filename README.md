# Jira Version Manager

A command-line tool to automate the creation of Jira versions following specific naming patterns. This tool is particularly useful for teams that need to create multiple versions across different projects with consistent naming conventions.

## Features

- Create versions for multiple Jira projects
- Support for custom version naming patterns
- Create versions for specific dates or next month's weekdays (Monday-Thursday)
- Dry-run mode to preview changes
- Configuration via file or environment variables
- Debug mode for troubleshooting

## Installation

To install the Jira Version Manager, run the following command:

```bash
pip install jira-version-manager
```

## Configuration

The tool can be configured in multiple ways (in order of precedence):

1. Environment variables
2. Configuration file (`~/.jira_version_manager.json`)
3. Default values

### Environment Variables

- `JIRA_BASE_URL`: Your Jira instance URL
- `JIRA_API_TOKEN`: Your Jira API token
- `JIRA_PROJECT_KEYS`: Comma-separated list of project keys
- `JIRA_VERSION_FORMATS`: Comma-separated list of version format patterns

### Configuration File

A sample configuration file will be created at `~/.jira_version_manager.json` during installation. You can modify it according to your needs:

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

## Usage

### Basic Usage

Create versions for next month's weekdays for all configured projects:

```bash
jira-version-manager
```


### Create Custom Version

Create a version for a specific project and date:

```bash
jira-version-manager --custom-version PROJECT1 2024-03-15
```

### Dry Run

Preview version creation without making actual changes:

```bash
jira-version-manager --dry-run
```

### Debug Mode

Enable debug output:

```bash
jira-version-manager --debug
```

### Display Configuration

Show current configuration:

```bash
jira-version-manager --info
```

## Version Format Patterns

The tool supports custom version format patterns. The default patterns create versions like:
- `PROJECT1.W12.2024.03.15`
- `PROJECT1.INTAKE.W12.2024.03.15`

Format placeholders:
- First `{}`: Project key
- `W{:02d}`: Week number (zero-padded)
- Following `{}`: Year
- `{:02d}`: Month (zero-padded)
- Last `{:02d}`: Day (zero-padded)

## Development

To set up the development environment:

1. Clone the repository:

```bash
git clone https://github.com/jackalski/jira-version-manager.git
cd jira-version-manager
```

2. Install in development mode:

```bash
pip install -e .
```

## License

This project is licensed under the MIT License.

## Author

Piotr Szmitkowski (pszmitkowski@gmail.com)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
