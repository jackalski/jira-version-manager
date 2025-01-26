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

## Interactive Mode

When started without parameters, the tool launches an interactive menu system:

```bash
jira-version-manager
```

### Navigation Guide:
```
Jira Version Manager Interactive Mode

Available commands:
  'h' - Help         : Show help menu
  'c' - Config       : Edit configuration
  'l' - List         : List versions
  'n' - New          : Create new versions
  'd' - Delete       : Delete version
  'm' - Maintenance  : Perform maintenance tasks
  's' - Scan and fix : Scan and fix version formats
  'x' - Cleanup      : Cleanup old versions
  'a' - Archive      : Archive old versions
  'q' - Quit         : Exit the program
  ESC                : Exit the program
```

Example workflow:
1. Press 'x' to start cleanup process
2. Select project(s) or use all configured projects
3. Enter number of days back to consider (e.g. 7 for versions older than 1 week)
4. Choose whether to remove future versions with no issues (y/n)
5. Decide if released versions should be included in cleanup (y/n)
6. Review cleanup plan and confirm execution

## Configuration

### Obtaining Jira API Token
1. Log in to your Jira instance
2. Navigate to: 
   ```
   https://<your-jira-url>/secure/ViewProfile.jspa?selectedTab=com.atlassian.pats.pats-plugin:jira-user-personal-access-tokens
   ```
3. Click "Create new token"
4. Set permissions:
   - Version management: Read/Write
   - Projects: Browse
   - Issues: Read
5. Store token securely

### Configuration File
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
       "standard": "{PROJECT}.W{WEEK:02d}.{YEAR}.{MONTH:02d}",
       "intake": "{PROJECT}.INTAKE.W{WEEK:02d}.{YEAR}.{MONTH:02d}",
       "release": "{PROJECT}.{YEAR}.{MONTH:02d}.{DAY:02d}.RELEASE",
       "semantic_project": "{PROJECT}.{MAJOR}.{MINOR}.{PATCH}{PRE_RELEASE}{BUILD}{METADATA}",
       "emergency": "{PROJECT}.W{WEEK:02d}.{YEAR}.{MONTH:02d}.{DAY:02d}_EMERGENCY"
     },
     "project_formats": {
       "default": ["standard"],
       "PROJECT1": ["standard", "release", "semantic_project"],
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
# Show configuration
jira-version-manager config

# Edit configuration
jira-version-manager config --edit
```

### List Versions
```bash
# List versions for a specific project
jira-version-manager list PROJECT1

# List versions for all configured projects
jira-version-manager list

# Show released versions (for all projects)
jira-version-manager list --show-released

# Show all versions (for all projects)
jira-version-manager list --show-all

# Show detailed information with issues (for all projects)
jira-version-manager list --detailed
```

### Create Versions
```bash
# Create versions for all configured projects (next month)
jira-version-manager create

# Create versions for a specific project (next month)
jira-version-manager create --project-key PROJECT1

# Create for current month (all projects)
jira-version-manager create --current-month

# Create with specific formats (all projects)
jira-version-manager create --formats standard,release

# Create for specific project and date
jira-version-manager create --project-key PROJECT1 --date 2024-02-01 --formats intake,release
```

### Delete Versions
```bash
# Delete a version
jira-version-manager delete PROJECT1 --version-name "PROJECT1.2025.02.01.RELEASE"

# Delete a version and move issues to another version
jira-version-manager delete PROJECT1 --version-name "PROJECT1.2025.02.01.RELEASE" --move-to "PROJECT1.2025.02.05.RELEASE"
```

### Cleanup Versions
```bash
# Clean up versions for all configured projects
jira-version-manager cleanup

# Clean up versions for a specific project
jira-version-manager cleanup PROJECT1

# Include released versions (all projects)
jira-version-manager cleanup --include-released

# Include released versions for specific project
jira-version-manager cleanup PROJECT1 --include-released
```

Cleanup criteria:
- More than 1 week old
- No issues assigned
- Unreleased (unless --include-released is used)

### Archive Versions
```bash
# Archive versions for all configured projects
jira-version-manager archive

# Archive versions for a specific project
jira-version-manager archive PROJECT1

# Override archive age (all projects)
jira-version-manager archive --months 2

# Override archive age for specific project
jira-version-manager archive PROJECT1 --months 2
```

Archive criteria:
- Released versions only
- Older than specified months (project setting or override)
- Project must have archiving enabled

When archived:
1. Description prefixed with "[ARCHIVED]"
2. Marked as archived in Jira
3. Hidden from most Jira views

Note: When no project key is provided, commands will operate on all projects defined in the `project_keys` configuration. This allows for easy batch operations across multiple projects.

## Semantic Versioning

The tool supports semantic versioning with pre-release versions, build numbers, and metadata. You can create semantic versions in several ways:

### Creating New Versions

```bash
# Create next major version (e.g., 1.2.3 => 2.0.0)
jira-version-manager create PROJECT1 --new-major

# Create next minor version (e.g., 1.2.3 => 1.3.0)
jira-version-manager create PROJECT1 --new-minor

# Create next patch version (e.g., 1.1.2 => 1.1.3)
jira-version-manager create PROJECT1 --new-patch

# Create specific version
jira-version-manager create PROJECT1 --major 2 --minor 1 --patch 3
```

### Pre-release Versions

```bash
# Create alpha version
jira-version-manager create PROJECT1 --new-pre-release alpha
# Creates: 1.2.3-alpha.1

# Create next alpha version
jira-version-manager create PROJECT1 --new-pre-release alpha
# Creates: 1.2.3-alpha.2

# Create beta version
jira-version-manager create PROJECT1 --new-pre-release beta
# Creates: 1.2.3-beta.1

# Create release candidate
jira-version-manager create PROJECT1 --new-pre-release rc
# Creates: 1.2.3-rc.1

# Create specific pre-release version
jira-version-manager create PROJECT1 --major 2 --minor 0 --pre-release "beta.3"
# Creates: 2.0.0-beta.3
```

### Build Numbers and Metadata

```bash
# Add build number
jira-version-manager create PROJECT1 --new-patch --build 42
# Creates: 1.2.4+b42

# Add metadata
jira-version-manager create PROJECT1 --new-patch --metadata "+sha.5114f85"
# Creates: 1.2.4+sha.5114f85

# Combine pre-release, build, and metadata
jira-version-manager create PROJECT1 --major 2 --minor 0 --pre-release "beta.1" --build 42 --metadata "+exp.sha.5114f85"
# Creates: 2.0.0-beta.1+b42+exp.sha.5114f85
```

### Project-Specific Semantic Versions

You can also include the project key in semantic versions using the `semantic_project` format:

```json
{
  "version_formats": {
    "semantic_project": "{PROJECT}.{MAJOR}.{MINOR}.{PATCH}{PRE_RELEASE}{BUILD}{METADATA}"
  },
  "project_formats": {
    "PROJECT1": ["semantic_project"]
  }
}
```

This will create versions like `PROJECT1.1.2.3-beta.1+b42`.

For versions prefixed with "v" (e.g., v1.2.3), use the `semantic_with_v_before_major` format:

```json
{
  "version_formats": {
    "semantic_with_v_before_major": "v{MAJOR}.{MINOR}.{PATCH}{PRE_RELEASE}{BUILD}{METADATA}"
  },
  "project_formats": {
    "PROJECT1": ["semantic_with_v_before_major"]
  }
}
```

This will create versions like `v1.2.3-rc.1+b42`.

The semantic versioning system is highly flexible and supports:
- Project-key prefixed versions (PROJECT.1.2.3)
- Standard semantic versions (1.2.3)
- "v" prefixed versions (v1.2.3)
- Custom pre-release formats (alpha, beta, rc, or custom labels)
- Build numbers and metadata tags
- Any combination of the above elements

Example configuration combinations:
1. Project-key with semantic version and pre-release:
   `PROJECT.2.1.0-beta.1`
2. Pure semantic version with build number:
   `2.1.0+b123`
3. "v" prefix with metadata:
   `v2.1.0+exp.sha.5114f85`
4. Custom pre-release format:
   `2.1.0-feature.123`

## Date-Based Versioning

The tool supports flexible date-based versioning patterns with multiple format options:

### Format Patterns
- **Weekly versions**: `{PROJECT}.W{WEEK:02d}.{YEAR}.{MONTH:02d}.{DAY:02d}`  
  Example: `PROJECT1.W02.2024.01.08`
- **Intake versions**: `{PROJECT}.INTAKE.W{WEEK:02d}.{YEAR}.{MONTH:02d}.{DAY:02d}`  
  Example: `PROJECT1.INTAKE.W03.2024.01.15`
- **Emergency versions**: `{PROJECT}.W{WEEK:02d}.{YEAR}.{MONTH:02d}.{DAY:02d}_EMERGENCY`  
  Example: `PROJECT1.W02.2024.01.09_EMERGENCY`
- **Daily versions**: `{PROJECT}.{YEAR}.{MONTH:02d}.{DAY:02d}`  
  Example: `PROJECT1.2024.01.10`

### Key Features
1. **Automatic Scheduling**:
   - Creates versions for upcoming release days based on project configuration
   - Avoids Friday releases by default (configurable)
   - Supports different release cadences per project

2. **Date Variables**:
   ```plaintext
   {WEEK}    - ISO week number (01-53)
   {YEAR}    - 4-digit year
   {MONTH}   - 2-digit month (01-12)
   {DAY}     - 2-digit day (01-31)
   {PROJECT} - Jira project key
   ```

3. **Configuration Example**:
   ```json
   {
     "version_formats": {
       "standard": "{PROJECT}.W{WEEK:02d}.{YEAR}.{MONTH:02d}.{DAY:02d}",
       "emergency": "{PROJECT}.W{WEEK:02d}.{YEAR}.{MONTH:02d}.{DAY:02d}_EMERGENCY"
     },
     "release_days": {
       "PROJECT1": {
         "days": [0, 2, 4],  // Monday, Wednesday, Friday
         "frequency": 2       // Every other week
       }
     }
   }
   ```

4. **Automatic Generation**:
   ```bash
   # Create versions for next month's release days
   jira-version-manager create --project-key PROJECT1
   
   # Create specific date version
   jira-version-manager create --project-key PROJECT1 --date 2024-01-15
   ```

The system automatically skips weekends (configurable) and handles different release schedules per project while maintaining consistent version naming.
