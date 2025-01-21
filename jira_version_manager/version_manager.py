import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import calendar
import argparse
import os
import json
import sys
from urllib.parse import urljoin, quote

class JiraApiError(Exception):
    """Custom exception for Jira API errors"""
    pass

class ConfigurationError(Exception):
    """Custom exception for configuration errors"""
    pass

class JiraVersionManager:
    def __init__(self) -> None:
        self.config: Dict[str, Any] = {
            "jira_base_url": "https://your-jira-instance.com",
            "jira_api_token": "",  # Don't set default token
            "project_keys": ["PROJECT1", "PROJECT2"],
            "version_formats": [
                "{}.W{:02d}.{}.{:02d}.{:02d}",
                "{}.INTAKE.W{:02d}.{}.{:02d}.{:02d}"
            ]
        }
        self.load_config()
        
        if not self.config["jira_api_token"]:
            raise ConfigurationError("API token not configured. Set JIRA_API_TOKEN environment variable.")
        
        self.headers = {
            "Authorization": f"Bearer {self.config['jira_api_token']}",
            "Content-Type": "application/json"
        }
        
        # Validate base URL
        if not self.config["jira_base_url"].startswith(("http://", "https://")):
            raise ConfigurationError("Invalid Jira base URL. Must start with http:// or https://")
        
    def load_config(self) -> None:
        """Load configuration in order: file, environment, defaults"""
        config_file = os.path.expanduser("~/.jira_version_manager.json")
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    loaded_config = json.load(f)
                    # Validate required fields
                    required_fields = ["jira_base_url", "project_keys", "version_formats"]
                    missing_fields = [field for field in required_fields if field not in loaded_config]
                    if missing_fields:
                        raise ConfigurationError(f"Missing required fields in config: {', '.join(missing_fields)}")
                    self.config.update(loaded_config)
            except json.JSONDecodeError as e:
                raise ConfigurationError(f"Invalid JSON in config file: {e}")
            except Exception as e:
                raise ConfigurationError(f"Error loading config file: {e}")

        # Override with environment variables
        env_mapping = {
            "JIRA_BASE_URL": "jira_base_url",
            "JIRA_API_TOKEN": "jira_api_token",
            "JIRA_PROJECT_KEYS": "project_keys",
            "JIRA_VERSION_FORMATS": "version_formats"
        }
        
        for env_var, config_key in env_mapping.items():
            env_value = os.getenv(env_var)
            if env_value:
                if env_var in ["JIRA_PROJECT_KEYS", "JIRA_VERSION_FORMATS"]:
                    self.config[config_key] = env_value.split(',')
                else:
                    self.config[config_key] = env_value

    def get_weekdays_for_next_month(self, start_date: Optional[str] = None) -> List[datetime]:
        """
        Get all Monday-Thursday dates starting from given date or next month
        
        Args:
            start_date: Optional start date in YYYY-MM-DD format
            
        Returns:
            List of datetime objects representing weekdays
        """
        try:
            if start_date:
                base_date = datetime.strptime(start_date, "%Y-%m-%d")
            else:
                base_date = datetime.now()
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
            response = requests.get(
                url,
                headers=self.headers,
                params={'jql': jql, 'fields': 'key,summary,status'},
                timeout=30
            )
            response.raise_for_status()
            
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
            JiraApiError: If the API call fails
        """
        if not project_key or not version_name:
            raise ValueError("Project key and version name are required")
            
        # Check if version exists
        exists, issues = self.check_version_exists(project_key, version_name)
        if exists:
            if issues:
                print(f"\nVersion {version_name} already exists with {len(issues)} issues:")
                for issue in issues:
                    print(f"  - {issue['key']}: {issue['fields']['summary']} ({issue['fields']['status']['name']})")
            else:
                print(f"Version {version_name} already exists (no issues assigned)")
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
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()
            
            if response.status_code == 201:
                print(f"Created version: {version_name}")
            else:
                raise JiraApiError(f"Unexpected status code: {response.status_code}")
                
        except requests.exceptions.Timeout:
            raise JiraApiError("Request timed out")
        except requests.exceptions.RequestException as e:
            raise JiraApiError(f"Error creating version {version_name}: {str(e)}")

    def create_custom_version(self, project_key: str, date_str: str, debug: bool = False, dry_run: bool = False) -> None:
        """
        Create a version for a specific date
        
        Args:
            project_key: Jira project key
            date_str: Date string in YYYY-MM-DD format
            debug: If True, print debug information
            dry_run: If True, simulate the creation
            
        Raises:
            ValueError: If date format is invalid
            JiraApiError: If version creation fails
        """
        if not project_key or not date_str:
            raise ValueError("Project key and date are required")
            
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
            week_num = date.isocalendar()[1]
            
            for version_format in self.config['version_formats']:
                version_name = version_format.format(
                    project_key,
                    week_num,
                    date.year,
                    date.month,
                    date.day
                )
                self.create_version(project_key, version_name, dry_run, debug)
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
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
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
            response = requests.delete(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            
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

def main() -> None:
    """Main entry point for the CLI application"""
    parser = argparse.ArgumentParser(
        description="Jira Version Manager - Create and manage Jira versions",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Common arguments
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parent_parser.add_argument("--dry-run", action="store_true", help="Simulate actions without making changes")
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Display current configuration', parents=[parent_parser])
    
    # List command
    list_parser = subparsers.add_parser('list', help='List versions for a project', parents=[parent_parser])
    list_parser.add_argument("project_key", help="Jira project key")
    
    # Create command
    create_parser = subparsers.add_parser('create', help='Create new version(s)', parents=[parent_parser])
    create_parser.add_argument("--project-key", help="Jira project key")
    create_parser.add_argument("--date", help="Specific date for version (YYYY-MM-DD)")
    
    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete a version', parents=[parent_parser])
    delete_parser.add_argument("project_key", help="Jira project key")
    delete_parser.add_argument("version_name", help="Name of the version to delete")
    delete_parser.add_argument("--move-to", help="Name of version to move issues to")
    
    args = parser.parse_args()
    
    try:
        manager = JiraVersionManager()
        
        if args.command == 'info':
            print("Current Configuration:")
            safe_config = manager.config.copy()
            if 'jira_api_token' in safe_config:
                safe_config['jira_api_token'] = '***'
            for key, value in safe_config.items():
                print(f"{key}: {value}")
                
        elif args.command == 'list':
            versions = manager.list_versions(args.project_key)
            print(f"\nVersions for project {args.project_key}:")
            for version in versions:
                status = "Released" if version.get('released', False) else "Unreleased"
                print(f"- {version['name']} ({status}) [ID: {version['id']}]")
                
        elif args.command == 'create':
            if args.project_key and args.date:
                manager.create_custom_version(args.project_key, args.date, args.debug, args.dry_run)
            else:
                # Default behavior: create versions for next month
                weekdays = manager.get_weekdays_for_next_month()
                for project_key in manager.config['project_keys']:
                    for date in weekdays:
                        week_num = date.isocalendar()[1]
                        for version_format in manager.config['version_formats']:
                            version_name = version_format.format(
                                project_key,
                                week_num,
                                date.year,
                                date.month,
                                date.day
                            )
                            manager.create_version(project_key, version_name, args.dry_run, args.debug)
                            
        elif args.command == 'delete':
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

