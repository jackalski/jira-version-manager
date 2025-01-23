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
import logging
from appdirs import user_data_dir

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
            "standard": "{PROJECT}.W{WEEK:02d}.{YEAR}.{MONTH:02d}.{DAY:02d}",
            "intake": "{PROJECT}.INTAKE.W{WEEK:02d}.{YEAR}.{MONTH:02d}.{DAY:02d}"
        },
        "project_formats": {
            "default": ["standard"],  # Default format for all projects
            "PROJECT1": ["standard"],
            "PROJECT2": ["intake"]
        },
        "issue_types": {
            "default": ["Epic"],
            "PROJECT1": ["Epic", "Story"],
            "PROJECT2": ["Epic", "Task"]
        },
        "jira_verify_ssl": True,
        "release_days": {
            "default": [0, 1, 2, 3],  # Monday to Thursday
            "PROJECT1": {
                "days": [0, 2, 4],    # Monday, Wednesday, Friday
                "frequency": 1         # Every week (use 2 for every two weeks)
            }
        },
        "archive_settings": {
            "default": {
                "months": 3,  # Archive after 3 months by default
                "enabled": True  # Enable archiving by default
            },
            "PROJECT1": {
                "months": 6,  # Archive after 6 months for PROJECT1
                "enabled": True
            },
            "PROJECT2": {
                "months": 1,  # Archive after 1 month for PROJECT2
                "enabled": False  # Disable archiving for PROJECT2
            }
        }
    }

    ENV_MAPPING = {
        "JIRA_BASE_URL": "jira_base_url",
        "JIRA_API_TOKEN": "jira_api_token",
        "JIRA_VERIFY_SSL": "jira_verify_ssl"
    }

    def __init__(self, jira_verify_ssl: Optional[bool] = None) -> None:
        """Initialize JiraVersionManager with configuration and SSL settings.
        
        Args:
            jira_verify_ssl: Whether to verify SSL certificates. If None, uses config value.
        """
        self.config = self.DEFAULT_CONFIG.copy()
        self.load_config()
        
        # Initialize logger
        self.logger = logging.getLogger('jira_version_manager')
        if not self.logger.handlers:
            logging.basicConfig(
                level=logging.INFO,
                format='%(message)s',
                handlers=[
                    logging.FileHandler("jira_version_manager.log", mode='w'),  # 'w' mode overwrites the file
                    logging.StreamHandler()
                ]
            )
        
        if not self.config["jira_api_token"]:
            os.startfile(self.config["config_location"])
            raise ConfigurationError("API token not configured. Set JIRA_API_TOKEN environment variable.")
        
        self.headers = {
            "Authorization": f"Bearer {self.config['jira_api_token']}",
            "Content-Type": "application/json"
        }
        
        # Determine SSL verification in order:
        # 1. Command line argument (jira_verify_ssl parameter)
        # 2. Config file
        # 3. Environment variable
        # 4. Default (True)
        if jira_verify_ssl is not None:
            self.jira_verify_ssl = jira_verify_ssl
        elif 'jira_verify_ssl' in self.config:
            self.jira_verify_ssl = self.config['jira_verify_ssl']
        elif os.environ.get('JIRA_VERIFY_SSL'):
            self.jira_verify_ssl = os.environ.get('JIRA_VERIFY_SSL').lower() not in ('false', '0', 'no')
        else:
            self.jira_verify_ssl = True
        
        # Disable SSL verification warnings if SSL verification is disabled
        if not self.jira_verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            self.session = requests.Session()
            self.session.verify = False
        else:
            self.session = requests.Session()
            self.session.verify = True
        
        # Validate base URL
        if not self.config["jira_base_url"].startswith(("http://", "https://")):
            raise ConfigurationError("Invalid Jira base URL. Must start with http:// or https://")

    def create_sample_config(self):
        """Create sample configuration file if it doesn't exist"""
        config_dir = user_data_dir("jira-version-manager", "1500100xyz")
        config_file = os.path.join(config_dir, "config.json")
        
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, mode=0o700)
            
        if not os.path.exists(config_file):
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.DEFAULT_CONFIG, f, indent=4)

    def load_config(self) -> None:
        """Load configuration in order: file, environment, defaults"""
        self._load_config_from_file()
        self._load_config_from_env()

    def _load_config_from_file(self) -> None:
        """Load configuration from file"""
        config_dir = user_data_dir("jira-version-manager", "1500100xyz")
        config_file = os.path.join(config_dir, "config.json")
        
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
            
        if not os.path.exists(config_file):
            print("Configuration file not found. Creating sample configuration file...")
            self.create_sample_config()
            print(f"Created sample configuration file at {config_file}")
            os.startfile(config_file)
            self.config["config_location"] = config_file
            return

        try:
            with open(config_file, 'r') as f:
                loaded_config = json.load(f)
                # Validate required fields
                required_fields = ["jira_base_url", "project_keys"]
                missing_fields = [field for field in required_fields if field not in loaded_config]
                if missing_fields:
                    os.startfile(config_file)
                    raise ConfigurationError(f"Missing required fields in config: {', '.join(missing_fields)}")
                self.config.update(loaded_config)
                self.config["config_location"] = config_file
        except json.JSONDecodeError as e:
            os.startfile(config_file)
            raise ConfigurationError(f"Invalid JSON in config file: {e}")
        except Exception as e:
            raise Exception(f"Error loading config file: {e}")

    def _load_config_from_env(self) -> None:
        """Load configuration from environment variables"""
        for env_var, config_key in self.ENV_MAPPING.items():
            env_value = os.environ.get(env_var)
            if not env_value:
                continue

            if env_var == "JIRA_VERIFY_SSL":
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
        """Get version formats for a specific project"""
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
        
        # Use project's default format keys or fallback to default
        format_keys = self.config["project_formats"].get(project_key, 
                     self.config["project_formats"].get("default", ["standard"]))
        
        formats = []
        for key in format_keys:
            if key not in self.config["version_formats"]:
                raise ValueError(f"Unknown version format key for project {project_key}: {key}")
            formats.append(self.config["version_formats"][key])
        return formats

    def get_weekdays_for_month(self, project_key: str, start_date: Optional[str] = None, use_next_month: bool = True) -> List[datetime]:
        """Get release days based on project configuration"""
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

            # Get project-specific release days configuration
            release_config = self.config.get('release_days', {}).get(project_key, {})
            if not release_config:
                release_config = {'days': self.config['release_days']['default'], 'frequency': 1}

            release_days = release_config['days']
            frequency = release_config.get('frequency', 1)

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
            
        # Get issue types for the project
        issue_types = self.config.get("issue_types", {}).get(project_key, 
                     self.config.get("issue_types", {}).get("default", ["Epic"]))
        issue_types_jql = " OR ".join(f'issuetype = "{t}"' for t in issue_types)
            
        jql = f'project = "{project_key}" AND fixVersion = "{version_name}" AND ({issue_types_jql})'
        url = urljoin(self.config['jira_base_url'], "rest/api/2/search")
        
        try:
            response = self._make_request(
                'GET',
                url,
                headers=self.headers,
                params={'jql': jql, 'fields': 'key,summary,status,issuetype'},
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

    def create_version_name(self, format_str: str, project_key: str, date: datetime) -> str:
        """Create version name using format string and variables
        
        Args:
            format_str: Format string with variables {PROJECT}, {WEEK}, {YEAR}, {MONTH}, {DAY}
            project_key: Project key to use
            date: Date to use for the version
            
        Returns:
            Formatted version name
        """
        week_num = date.isocalendar()[1]
        return format_str.format(
            PROJECT=project_key,
            WEEK=week_num,
            YEAR=date.year,
            MONTH=date.month,
            DAY=date.day
        )

    def create_versions_for_dates(self, project_key: str, dates: List[datetime], debug: bool = False, 
                                dry_run: bool = False, format_keys: Optional[List[str]] = None) -> None:
        """Create versions for a list of dates"""
        if not project_key or not dates:
            raise ValueError("Project key and dates are required")
            
        for date in dates:
            for version_format in self.get_project_formats(project_key, format_keys):
                version_name = self.create_version_name(version_format, project_key, date)
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
            
        url = urljoin(self.config['jira_base_url'], f"rest/api/2/version/{version_id}/removeAndSwap")
        
        payload = {}
        if move_issues_to:
            payload = { 
                "moveFixIssuesTo": move_issues_to
            }
            
        try:
            response = self._make_request('POST', url, headers=self.headers, json=payload, timeout=30)
            
            if response.status_code == 204:
                print(f"Deleted version: {version_id}")
            else:
                raise JiraApiError(f"Unexpected status code: {response.status_code}")
                
        except requests.exceptions.Timeout:
            raise JiraApiError("Request timed out")
        except requests.exceptions.RequestException as e:
            raise JiraApiError(f"Error deleting version: {str(e)}")

    def cleanup_versions(self, project_key: Optional[str] = None, include_released: bool = False) -> Dict[str, List[str]]:
        """
        Remove versions that are:
        - More than 1 week in the past
        - Have no issues assigned
        - Are unreleased (or include released if include_released=True)
        
        Args:
            project_key: The Jira project key (if None, cleanup all configured projects)
            include_released: Whether to also remove released versions (default: False)
            
        Returns:
            Dictionary mapping project keys to lists of removed version names
        """
        removed_versions = {}
        current_date = datetime.now()
        
        # Get list of projects to process
        projects = [project_key] if project_key else self.config['project_keys']
        
        for proj_key in projects:
            removed_versions[proj_key] = []
            versions = self.list_versions(proj_key)
            
            for version in versions:
                # Skip if version is released and we're not including released versions
                if version.get('released', False) and not include_released:
                    continue
                    
                # Check if version has a date in its name using our format patterns
                try:
                    # Extract date from version name using available formats
                    version_date = None
                    for format_name, format_pattern in self.config['version_formats'].items():
                        try:
                            # Try to parse the date from the version name
                            if '.W' in format_pattern:  # Weekly format
                                parts = version['name'].split('.')
                                year = int(parts[-3])
                                month = int(parts[-2])
                                day = int(parts[-1])
                                version_date = datetime(year, month, day)
                                break
                            else:  # Standard format
                                parts = version['name'].split('.')
                                year = int([p for p in parts if len(p) == 4][0])
                                month = int([p for p in parts if len(p) == 2][0])
                                day = int([p for p in parts if len(p) == 2][1])
                                version_date = datetime(year, month, day)
                                break
                        except (ValueError, IndexError):
                            continue
                    
                    if version_date is None:
                        continue  # Skip if we couldn't parse the date
                    
                    # Check if version is more than 1 week old
                    if (current_date - version_date).days <= 7:
                        continue
                    
                    # Check if version has any issues
                    issues = self.get_issues_for_version(proj_key, version['name'])
                    if issues:
                        continue
                    
                    # If we got here, the version meets all criteria for removal
                    self.delete_version(version['id'])
                    removed_versions[proj_key].append(version['name'])
                    
                except Exception as e:
                    logging.warning(f"Error processing version {version['name']} for project {proj_key}: {str(e)}")
                    continue
        
        return removed_versions

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

    def list_versions_with_details(self, project_key: str, show_all: bool = False, 
                                 show_released: bool = False, detailed: bool = False) -> None:
        """List versions with optional detailed issue information"""
        versions = self.list_versions(project_key)
        
        # Filter versions based on release status
        if not show_all:
            versions = [v for v in versions if v.get('released', False) == show_released]
            
        if not versions:
            status_type = "released" if show_released else "unreleased"
            self.logger.info(f"No {status_type if not show_all else ''} versions found.")
            return
            
        # Get issue types for the project
        issue_types = self.config.get("issue_types", {}).get(project_key, 
                     self.config.get("issue_types", {}).get("default", ["Epic"]))
            
        for version in versions:
            status = "Released" if version.get('released', False) else "Unreleased"
            self.logger.info(f"\n{version['name']} ({status}) [ID: {version['id']}]")
            
            if detailed:
                issues = self.get_issues_for_version(project_key, version['name'])
                if issues:
                    self.logger.info(f"Issues ({len(issues)}) [Types: {', '.join(issue_types)}]:")
                    for issue in issues:
                        issue_type = issue['fields']['issuetype']['name']
                        self.logger.info(f"  - [{issue_type}] {issue['key']}: {issue['fields']['summary']}")
                        self.logger.info(f"    Status: {issue['fields']['status']['name']}")
                else:
                    self.logger.info(f"No issues of types [{', '.join(issue_types)}] assigned")

    def archive_releases(self, project_key: Optional[str] = None, months: Optional[int] = None) -> Dict[str, List[str]]:
        """
        Archive released versions that are older than the specified number of months.
        
        Args:
            project_key: The Jira project key (if None, archive for all configured projects)
            months: Number of months after which to archive releases (if None, use project settings)
            
        Returns:
            Dictionary mapping project keys to lists of archived version names
        """
        archived_versions = {}
        current_date = datetime.now()
        
        # Get list of projects to process
        projects = [project_key] if project_key else self.config['project_keys']
        
        for proj_key in projects:
            # Get project-specific archive settings
            archive_config = self.config.get('archive_settings', {}).get(proj_key, 
                self.config['archive_settings']['default'])
            
            # Skip if archiving is disabled for this project
            if not archive_config.get('enabled', True):
                archived_versions[proj_key] = []
                continue
            
            # Use provided months or project-specific setting
            archive_months = months if months is not None else archive_config.get('months', 3)
            cutoff_date = current_date - timedelta(days=archive_months * 30)  # Approximate months
            
            archived_versions[proj_key] = []
            versions = self.list_versions(proj_key)
            
            for version in versions:
                # Only process released versions
                if not version.get('released', False):
                    continue
                    
                # Check if version has a date in its name using our format patterns
                try:
                    # Extract date from version name using available formats
                    version_date = None
                    for format_name, format_pattern in self.config['version_formats'].items():
                        try:
                            # Try to parse the date from the version name
                            if '.W' in format_pattern:  # Weekly format
                                parts = version['name'].split('.')
                                year = int(parts[-3])
                                month = int(parts[-2])
                                day = int(parts[-1])
                                version_date = datetime(year, month, day)
                                break
                            else:  # Standard format
                                parts = version['name'].split('.')
                                year = int([p for p in parts if len(p) == 4][0])
                                month = int([p for p in parts if len(p) == 2][0])
                                day = int([p for p in parts if len(p) == 2][1])
                                version_date = datetime(year, month, day)
                                break
                        except (ValueError, IndexError):
                            continue
                    
                    if version_date is None:
                        continue  # Skip if we couldn't parse the date
                    
                    # Check if version is older than cutoff date
                    if version_date > cutoff_date:
                        continue
                    
                    # Archive the version by updating its description
                    url = f"{self.config['jira_base_url']}/rest/api/2/version/{version['id']}"
                    description = version.get('description', '') or ''
                    if not description.startswith('[ARCHIVED]'):
                        new_description = f"[ARCHIVED] {description}"
                        data = {
                            'description': new_description,
                            'archived': True
                        }
                        self._make_request('PUT', url, json=data)
                        archived_versions[proj_key].append(version['name'])
                    
                except Exception as e:
                    logging.warning(f"Error processing version {version['name']} for project {proj_key}: {str(e)}")
                    continue
        
        return archived_versions

def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser"""
    parser = argparse.ArgumentParser(description="Manage Jira versions")
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--dry-run', action='store_true', help='Simulate actions without making changes')
    parser.add_argument('--no-verify-ssl', action='store_true', help='Disable SSL certificate verification')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Info command
    subparsers.add_parser('info', help='Show configuration information')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List versions')
    list_parser.add_argument('project_key', nargs='?', help='Jira project key')
    list_parser.add_argument('--show-released', action='store_true', help='Show only released versions')
    list_parser.add_argument('--show-all', action='store_true', help='Show all versions')
    list_parser.add_argument('--detailed', action='store_true', help='Show detailed information including issues')
    
    # Create command
    create_parser = subparsers.add_parser('create', help='Create versions')
    create_parser.add_argument('--project-key', help='Jira project key')
    create_parser.add_argument('--date', help='Specific date (YYYY-MM-DD)')
    create_parser.add_argument('--current-month', action='store_true', help='Create versions for current month')
    create_parser.add_argument('--formats', help='Comma-separated list of format names to use')
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Remove old versions with no issues')
    cleanup_parser.add_argument('project_key', nargs='?', help='Jira project key')
    cleanup_parser.add_argument('--include-released', action='store_true', help='Include released versions in cleanup')
    
    # Archive command
    archive_parser = subparsers.add_parser('archive', help='Archive old released versions')
    archive_parser.add_argument('project_key', nargs='?', help='Jira project key')
    archive_parser.add_argument('--months', type=int, help='Archive versions older than this many months')
    
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
    projects = [args.project_key] if args.project_key else manager.config['project_keys']
    
    for project_key in projects:
        versions = manager.list_versions(project_key)
        
        # Filter versions based on release status
        if not args.show_all:
            versions = [v for v in versions if args.show_released == v.get('released', False)]
        
        if versions:
            print(f"\n{project_key}:")
            for version in versions:
                print(f"  - {version['name']} ({'Released' if version.get('released', False) else 'Unreleased'})")
                
                if args.detailed:
                    issues = manager.get_issues_for_version(project_key, version['name'])
                    if issues:
                        print("    Issues:")
                        for issue in issues:
                            print(f"      - {issue['key']}: {issue['fields']['summary']} ({issue['fields']['status']['name']})")
                    else:
                        print("    No issues assigned")
        else:
            print(f"\n{project_key}: No versions found")

def handle_create_command(manager: JiraVersionManager, args: argparse.Namespace) -> None:
    """Handle the create command"""
    projects = [args.project_key] if args.project_key else manager.config['project_keys']
    
    for project_key in projects:
        try:
            if args.date:
                # Create versions for specific date
                manager.create_versions_for_dates(project_key, [datetime.strptime(args.date, "%Y-%m-%d")], args.debug, args.dry_run, args.formats.split(',') if args.formats else None)
            else:
                # Create versions for next month or current month
                weekdays = manager.get_weekdays_for_month(project_key, use_next_month=not args.current_month)
                manager.create_versions_for_dates(project_key, weekdays, args.debug, args.dry_run, args.formats.split(',') if args.formats else None)
            print(f"Created versions for {project_key}")
        except Exception as e:
            print(f"Error creating versions for {project_key}: {str(e)}")

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

def handle_cleanup_command(manager: JiraVersionManager, args: argparse.Namespace) -> None:
    """Handle the cleanup command"""
    removed = manager.cleanup_versions(args.project_key, args.include_released)
    
    if any(versions for versions in removed.values()):
        print("Removed versions:")
        for project, versions in removed.items():
            if versions:
                print(f"\n{project}:")
                for version in versions:
                    print(f"  - {version}")
    else:
        print("No versions were removed.")

def handle_archive_command(manager: JiraVersionManager, args: argparse.Namespace) -> None:
    """Handle the archive command"""
    archived = manager.archive_releases(args.project_key, args.months)
    
    if any(versions for versions in archived.values()):
        print("Archived versions:")
        for project, versions in archived.items():
            if versions:
                print(f"\n{project}:")
                for version in versions:
                    print(f"  - {version}")
    else:
        print("No versions were archived.")

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
            'delete': lambda: handle_delete_command(manager, args),
            'cleanup': lambda: handle_cleanup_command(manager, args),
            'archive': lambda: handle_archive_command(manager, args)
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

