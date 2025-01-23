# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2024-01-24

### Changed
- Improved handling of project-wide operations
  - All commands now support operating on all configured projects when no project key is provided
  - Enhanced output formatting for multi-project operations
  - Better error handling for batch operations
- Updated command-line interface
  - Made project key parameter optional for all commands
  - Improved help text and command descriptions
  - Consistent parameter naming across commands

## [0.2.0] - 2024-01-23

### Added
- Automatic version cleanup functionality
  - Remove versions older than 1 week with no issues
  - Option to include released versions in cleanup
  - Support for cleaning up all configured projects at once
  - Safe cleanup with version date parsing
- Version archiving functionality
  - Project-specific archive settings (months and enabled flag)
  - Default archive settings (3 months, enabled)
  - Command-line override for archive age
  - Support for archiving all configured projects at once
  - Automatic marking of archived versions in Jira
- Enhanced version format patterns
  - Support for variables: PROJECT, WEEK, YEAR, MONTH, DAY
  - Project-specific format configuration
  - Default format fallback for projects
- Project-specific configurations
  - Issue type filtering per project
  - Release days configuration per project
  - Archive settings per project

### Changed
- Renamed SSL verification setting from `verify_ssl` to `jira_verify_ssl`
- Updated publisher information and repository links
- Improved configuration structure with project-specific settings
- Enhanced error handling and logging

### Fixed
- Resource leaks in file handling with proper encoding and permissions
- Improved error handling for API requests
- Fixed version date parsing for different format patterns

## [0.1.0] - 2024-03-21

### Added
- Initial release of Jira Version Manager
- Support for creating and managing Jira versions
- SSL verification control for self-signed certificates
- Basic logging functionality

[0.2.1]: https://github.com/jackalski/jira-version-manager/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/jackalski/jira-version-manager/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/jackalski/jira-version-manager/releases/tag/v0.1.0 