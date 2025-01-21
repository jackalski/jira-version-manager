import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import calendar
import argparse
import os
import json
import sys
import urllib3
from urllib.parse import urljoin, quote

class JiraApiError(Exception):
    """Custom exception for Jira API errors"""
    pass

class ConfigurationError(Exception):
    """Custom exception for configuration errors"""
    pass

class JiraVersionManager:
    DEFAULT_CONFIG = {
        "jira_base_url": "https://your-jira-instance.com",
        "jira_api_token": "",  # Don't set default token
        "project_keys": ["PROJECT1", "PROJECT2"],
        "version_formats": {
            "standard": "{}.W{:02d}.{}.{:02d}.{:02d}",
            "intake": "{}.INTAKE.W{:02d}.{}.{:02d}.{:02d}"
        },
        "project_formats": {
            "PROJECT1": ["standard"],
            "PROJECT2": ["intake"]
        },
        "jira_verify_ssl": True
    }

    ENV_MAPPING = {
        "JIRA_BASE_URL": "jira_base_url",
        "JIRA_API_TOKEN": "jira_api_token",
        "JIRA_PROJECT_KEYS": "project_keys",
        "JIRA_VERSION_FORMATS": "version_formats",
        "JIRA_VERIFY_SSL": "jira_verify_ssl",
        "JIRA_PROJECT_FORMATS": "project_formats"
    }

    def __init__(self, jira_verify_ssl: Optional[bool] = None) -> None:
        """Initialize JiraVersionManager with configuration and SSL settings.
        
        Args:
            jira_verify_ssl: Whether to verify SSL certificates. If None, uses config value.
        """
        self.config = self.DEFAULT_CONFIG.copy()
        self.load_config()
        
        if not self.config["jira_api_token"]:
            raise ConfigurationError("API token not configured. Set JIRA_API_TOKEN environment variable.")
        
        self.headers = {
            "Authorization": f"Bearer {self.config['jira_api_token']}",
            "Content-Type": "application/json"
        }
        
        # Determine SSL verification:
        # 1. Command line argument (jira_verify_ssl parameter)
        # 2. Environment variable
        # 3. Config file
        # 4. Default (True)
        self.jira_verify_ssl = jira_verify_ssl if jira_verify_ssl is not None else self.config.get('jira_verify_ssl', True)
        
        # Disable SSL verification warnings if SSL verification is disabled
        if not self.jira_verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Validate base URL
        if not self.config["jira_base_url"].startswith(("http://", "https://")):
            raise ConfigurationError("Invalid Jira base URL. Must start with http:// or https://")

    def load_config(self) -> None:
        """Load configuration in order: file, environment, defaults"""
        self._load_config_from_file()
        self._load_config_from_env()

    def _load_config_from_file(self) -> None:
        """Load configuration from file"""
        config_file = os.path.expanduser("~/.jira_version_manager.json")
        if not os.path.exists(config_file):
            return

        try:
            with open(config_file, 'r') as f:
                loaded_config = json.load(f)
                # Validate required fields
                required_fields = ["jira_base_url", "project_keys", "version_formats", "project_formats"]
                missing_fields = [field for field in required_fields if field not in loaded_config]
                if missing_fields:
                    raise ConfigurationError(f"Missing required fields in config: {', '.join(missing_fields)}")
                self.config.update(loaded_config)
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in config file: {e}")
        except Exception as e:
            raise ConfigurationError(f"Error loading config file: {e}")

    def _load_config_from_env(self) -> None:
        """Load configuration from environment variables"""
        for env_var, config_key in self.ENV_MAPPING.items():
            env_value = os.getenv(env_var)
            if not env_value:
                continue

            if env_var == "JIRA_PROJECT_FORMATS":
                try:
                    self.config[config_key] = json.loads(env_value)
                except json.JSONDecodeError:
                    raise ConfigurationError("Invalid JSON in JIRA_PROJECT_FORMATS environment variable")
            elif env_var in ["JIRA_PROJECT_KEYS", "JIRA_VERSION_FORMATS"]:
                self.config[config_key] = env_value.split(',')
            elif env_var == "JIRA_jira_verify_ssl":
                self.config[config_key] = env_value.lower() not in ('false', '0', 'no')
            else:
                self.config[config_key] = env_value

    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Make HTTP request with SSL verification configuration"""
        kwargs['verify'] = self.jira_verify_ssl
        response = requests.request(method, url, **kwargs)
        response.raise_for_status()
        return response

    def get_project_formats(self, project_key: str, format_keys: Optional[List[str]] = None) -> List[str]:
        """Get version formats for a specific project
        
        Args:
            project_key: Jira project key
            format_keys: Optional list of format keys to use instead of project defaults
            
        Returns:
            List of format strings to use
            
        Raises:
            ValueError: If a format key is not found
            ConfigurationError: If standard format is not defined
        """
        # Ensure standard format exists
        if "standard" not in self.config["version_formats"]:
            raise ConfigurationError("Standard version format must be defined")

        if format_keys:
            # Use specified format keys
            formats = []
            for key in format_keys:
                if key not in self.config["version_formats"]:
                    raise ValueError(f"Unknown version format key: {key}")
                formats.append(self.config["version_formats"][key])
            return formats
        
        # Use project's default format keys or fallback to standard
        format_keys = self.config["project_formats"].get(project_key)
        if not format_keys:
            return [self.config["version_formats"]["standard"]]

        formats = []
        for key in format_keys:
            if key not in self.config["version_formats"]:
                raise ValueError(f"Unknown version format key for project {project_key}: {key}")
            formats.append(self.config["version_formats"][key])
        return formats

    def get_weekdays_for_month(self, start_date: Optional[str] = None, use_next_month: bool = True) -> List[datetime]:
        """
        Get all Monday-Thursday dates for current or next month
        
        Args:
            start_date: Optional start date in YYYY-MM-DD format
            use_next_month: If True, get dates for next month, otherwise current month
            
        Returns:
            List of datetime objects representing weekdays
        """
        try:
            if start_date:
                base_date = datetime.strptime(start_date, "%Y-%m-%d")
            else:
                base_date = datetime.now()
                if use_next_month:
                    if base_date.month == 12:
                        next_month = 1
                        year = base_date.year + 1
                    else:
                        next_month = base_date.month + 1
                        year = base_date.year
                    base_date = datetime(year, next_month, 1)

            _, num_days = calendar.monthrange(base_date.year, base_date.month)
            dates = []
            
            for day in range(1, num_days + 1):
                date = datetime(base_date.year, base_date.month, day)
                if date.weekday() in range(4):  # Monday = 0, Thursday = 3
                    dates.append(date)
            
            return dates
        except ValueError as e:
            raise ValueError(f"Invalid date format. Please use YYYY-MM-DD: {e}")

    def get_issues_for_version(self, project_key: str, version_name: str) -> List[Dict[str, Any]]:
        """
        Get all issues associated with a version
        
        Args:
            project_key: Jira project key
            version_name: Name of the version
            
        Returns:
            List of issue objects
            
        Raises:
            JiraApiError: If the API call fails
        """
        if not project_key or not version_name:
            raise ValueError("Project key and version name are required")
            
        jql = f'project = {project_key} AND fixVersion = "{version_name}"'
        url = urljoin(self.config['jira_base_url'], "rest/api/2/search")
        
        try:
            response = self._make_request(
                'GET',
                url,
                headers=self.headers,
                params={'jql': jql, 'fields': 'key,summary,status'},
                timeout=30
            )
            
            data = response.json()
            if not isinstance(data, dict) or 'issues' not in data:
                raise JiraApiError("Invalid response format from Jira API")
                
            return data['issues']
            
        except requests.exceptions.Timeout:
            raise JiraApiError("Request timed out")
        except requests.exceptions.RequestException as e:
            raise JiraApiError(f"Error getting issues: {str(e)}")

    def check_version_exists(self, project_key: str, version_name: str) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Check if version exists and get associated issues
        
        Args:
            project_key: Jira project key
            version_name: Name of the version to check
            
        Returns:
            Tuple of (exists: bool, issues: List[Dict])
            
        Raises:
            JiraApiError: If the API call fails
        """
        version = self.get_version_by_name(project_key, version_name)
        if not version:
            return False, []
            
        issues = self.get_issues_for_version(project_key, version_name)
        return True, issues

    def create_version(self, project_key: str, version_name: str, dry_run: bool = False, debug: bool = False) -> None:
        """
        Create a version in Jira project if it doesn't exist
        
        Args:
            project_key: Jira project key
            version_name: Name of the version to create
            dry_run: If True, simulate the creation
            debug: If True, print debug information
            
        Raises:
            ValueError: If project_key or version_name is empty
            JiraApiError: If the API call fails
        """
        if not project_key or not version_name:
            raise ValueError("Project key and version name are required")
            
        # Check if version exists
        exists, issues = self.check_version_exists(project_key, version_name)
        if exists:
            self._print_version_exists_message(version_name, issues)
            return
            
        if debug:
            print(f"DEBUG: Creating version with name: {version_name}")
        
        if dry_run:
            print(f"DRY RUN: Would create version: {version_name}")
            return
            
        url = urljoin(self.config['jira_base_url'], "rest/api/2/version")
        payload = {
            "name": version_name,
            "project": project_key,
            "released": False
        }
        
        try:
            response = self._make_request('POST', url, headers=self.headers, json=payload, timeout=30)
            if response.status_code == 201:
                print(f"Created version: {version_name}")
            else:
                raise JiraApiError(f"Unexpected status code: {response.status_code}")
                
        except requests.exceptions.Timeout:
            raise JiraApiError("Request timed out")
        except requests.exceptions.RequestException as e:
            raise JiraApiError(f"Error creating version {version_name}: {str(e)}")

    def _print_version_exists_message(self, version_name: str, issues: List[Dict[str, Any]]) -> None:
        """Print message about existing version and its issues"""
        if issues:
            print(f"\nVersion {version_name} already exists with {len(issues)} issues:")
            for issue in issues:
                print(f"  - {issue['key']}: {issue['fields']['summary']} ({issue['fields']['status']['name']})")
        else:
            print(f"Version {version_name} already exists (no issues assigned)")

    def create_versions_for_dates(self, project_key: str, dates: List[datetime], debug: bool = False, dry_run: bool = False, format_keys: Optional[List[str]] = None) -> None:
        """
        Create versions for a list of dates
        
        Args:
            project_key: Jira project key
            dates: List of dates to create versions for
            debug: If True, print debug information
            dry_run: If True, simulate the creation
            format_keys: Optional list of format keys to use instead of project defaults
            
        Raises:
            ValueError: If project_key is empty or dates is empty
            JiraApiError: If version creation fails
        """
        if not project_key or not dates:
            raise ValueError("Project key and dates are required")
            
        for date in dates:
            week_num = date.isocalendar()[1]
            for version_format in self.get_project_formats(project_key, format_keys):
                version_name = version_format.format(
                    project_key,
                    week_num,
                    date.year,
                    date.month,
                    date.day
                )
                self.create_version(project_key, version_name, dry_run, debug)

    def create_custom_version(self, project_key: str, date_str: str, debug: bool = False, dry_run: bool = False, format_keys: Optional[List[str]] = None) -> None:
        """
        Create a version for a specific date
        
        Args:
            project_key: Jira project key
            date_str: Date string in YYYY-MM-DD format
            debug: If True, print debug information
            dry_run: If True, simulate the creation
            format_keys: Optional list of format keys to use instead of project defaults
            
        Raises:
            ValueError: If date format is invalid or project_key is empty
            JiraApiError: If version creation fails
        """
        if not project_key or not date_str:
            raise ValueError("Project key and date are required")
            
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
            self.create_versions_for_dates(project_key, [date], debug, dry_run, format_keys)
        except ValueError as e:
            raise ValueError(f"Invalid date format. Please use YYYY-MM-DD: {str(e)}")

    def validate_api_response(self, response: requests.Response, expected_fields: List[str]) -> Dict[str, Any]:
        """
        Validate API response and ensure required fields are present
        
        Args:
            response: Response object from requests
            expected_fields: List of fields that should be present in response
            
        Returns:
            Dict containing the JSON response
            
        Raises:
            JiraApiError: If response validation fails
        """
        try:
            data = response.json()
        except ValueError:
            raise JiraApiError("Invalid JSON response from API")
            
        if not isinstance(data, dict):
            raise JiraApiError("Expected JSON object in response")
            
        missing_fields = [field for field in expected_fields if field not in data]
        if missing_fields:
            raise JiraApiError(f"Missing required fields in API response: {', '.join(missing_fields)}")
            
        return data

    def list_versions(self, project_key: str) -> List[Dict[str, Any]]:
        """
        List all versions for a project
        
        Args:
            project_key: Jira project key
            
        Returns:
            List of version objects
            
        Raises:
            JiraApiError: If the API call fails
        """
        if not project_key:
            raise ValueError("Project key is required")
            
        url = urljoin(self.config['jira_base_url'], f"rest/api/2/project/{project_key}/versions")
        
        try:
            response = self._make_request('GET', url, headers=self.headers, timeout=30)
            versions = response.json()
            if not isinstance(versions, list):
                raise JiraApiError("Expected array of versions in response")
                
            return versions
            
        except requests.exceptions.Timeout:
            raise JiraApiError("Request timed out")
        except requests.exceptions.RequestException as e:
            raise JiraApiError(f"Error listing versions: {str(e)}")

    def delete_version(self, version_id: str, move_issues_to: Optional[str] = None) -> None:
        """
        Delete a version
        
        Args:
            version_id: ID of the version to delete
            move_issues_to: Optional ID of version to move issues to
            
        Raises:
            JiraApiError: If the API call fails
        """
        if not version_id:
            raise ValueError("Version ID is required")
            
        url = urljoin(self.config['jira_base_url'], f"rest/api/2/version/{version_id}")
        
        params = {}
        if move_issues_to:
            params['moveFixIssuesTo'] = move_issues_to
            
        try:
            response = self._make_request('DELETE', url, headers=self.headers, params=params, timeout=30)
            
            if response.status_code == 204:
                print(f"Deleted version: {version_id}")
            else:
                raise JiraApiError(f"Unexpected status code: {response.status_code}")
                
        except requests.exceptions.Timeout:
            raise JiraApiError("Request timed out")
        except requests.exceptions.RequestException as e:
            raise JiraApiError(f"Error deleting version: {str(e)}")

    def get_version_by_name(self, project_key: str, version_name: str) -> Optional[Dict[str, Any]]:
        """
        Find a version by its name
        
        Args:
            project_key: Jira project key
            version_name: Name of the version to find
            
        Returns:
            Version object if found, None otherwise
        """
        versions = self.list_versions(project_key)
        return next((v for v in versions if v['name'] == version_name), None)

def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser"""
    parser = argparse.ArgumentParser(
        description="Jira Version Manager - Create and manage Jira versions",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Add global arguments
    parser.add_argument("--no-verify-ssl", action="store_true", help="Disable SSL certificate verification")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--dry-run", action="store_true", help="Simulate actions without making changes")
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Info command
    subparsers.add_parser('info', help='Display current configuration')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List versions for a project')
    list_parser.add_argument("project_key", help="Jira project key")
    list_parser.add_argument("--show-all", action="store_true", help="Show both released and unreleased versions")
    list_parser.add_argument("--show-released", action="store_true", help="Show only released versions")
    
    # Create command
    create_parser = subparsers.add_parser('create', help='Create new version(s)')
    create_parser.add_argument("--project-key", help="Jira project key")
    create_parser.add_argument("--date", help="Specific date for version (YYYY-MM-DD)")
    create_parser.add_argument("--current-month", action="store_true", help="Create versions for current month instead of next month")
    create_parser.add_argument("--formats", help="Comma-separated list of format keys to use (e.g. 'standard,intake')")
    
    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete a version')
    delete_parser.add_argument("project_key", help="Jira project key")
    delete_parser.add_argument("version_name", help="Name of the version to delete")
    delete_parser.add_argument("--move-to", help="Name of version to move issues to")
    
    return parser

def handle_info_command(manager: JiraVersionManager) -> None:
    """Handle the info command"""
    print("Current Configuration:")
    safe_config = manager.config.copy()
    if 'jira_api_token' in safe_config:
        safe_config['jira_api_token'] = '***'
    for key, value in safe_config.items():
        print(f"{key}: {value}")

def handle_list_command(manager: JiraVersionManager, args: argparse.Namespace) -> None:
    """Handle the list command"""
    versions = manager.list_versions(args.project_key)
    
    # Filter versions based on release status
    if not args.show_all:
        if args.show_released:
            versions = [v for v in versions if v.get('released', False)]
        else:
            versions = [v for v in versions if not v.get('released', False)]
    
    # Sort versions by release status and name
    versions.sort(key=lambda v: (v.get('released', False), v['name']))
    
    print(f"\nVersions for project {args.project_key}:")
    if not versions:
        status_type = "released" if args.show_released else "unreleased"
        print(f"No {status_type if not args.show_all else ''} versions found.")
        return
        
    for version in versions:
        status = "Released" if version.get('released', False) else "Unreleased"
        print(f"- {version['name']} ({status}) [ID: {version['id']}]")

def handle_create_command(manager: JiraVersionManager, args: argparse.Namespace) -> None:
    """Handle the create command"""
    format_keys = args.formats.split(',') if args.formats else None
    
    if args.project_key and args.date:
        manager.create_custom_version(args.project_key, args.date, args.debug, args.dry_run, format_keys)
    else:
        # Create versions for current or next month
        weekdays = manager.get_weekdays_for_month(use_next_month=not args.current_month)
        project_keys = [args.project_key] if args.project_key else manager.config['project_keys']
        
        for project_key in project_keys:
            manager.create_versions_for_dates(project_key, weekdays, args.debug, args.dry_run, format_keys)

def handle_delete_command(manager: JiraVersionManager, args: argparse.Namespace) -> None:
    """Handle the delete command"""
    version = manager.get_version_by_name(args.project_key, args.version_name)
    if not version:
        raise ValueError(f"Version not found: {args.version_name}")
        
    move_to_version = None
    if args.move_to:
        move_to_version = manager.get_version_by_name(args.project_key, args.move_to)
        if not move_to_version:
            raise ValueError(f"Target version not found: {args.move_to}")
            
    if not args.dry_run:
        manager.delete_version(version['id'], move_to_version['id'] if move_to_version else None)
    else:
        print(f"DRY RUN: Would delete version: {args.version_name}")

def main() -> None:
    """Main entry point for the CLI application"""
    parser = create_parser()
    args = parser.parse_args()
    
    try:
        # If --no-verify-ssl is used, it overrides config
        jira_verify_ssl = False if args.no_verify_ssl else None
        manager = JiraVersionManager(jira_verify_ssl=jira_verify_ssl)
        
        command_handlers = {
            'info': lambda: handle_info_command(manager),
            'list': lambda: handle_list_command(manager, args),
            'create': lambda: handle_create_command(manager, args),
            'delete': lambda: handle_delete_command(manager, args)
        }
        
        handler = command_handlers.get(args.command)
        if handler:
            handler()
        else:
            parser.print_help()
                    
    except (ConfigurationError, JiraApiError, ValueError) as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {str(e)}", file=sys.stderr)
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

