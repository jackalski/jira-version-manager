import sys
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import calendar
import argparse
import os
import json
import urllib3
from urllib.parse import urljoin, quote
import logging
from appdirs import user_data_dir
import re
import yaml

class JiraApiError(Exception):
    """Custom exception for Jira API errors"""
    pass

class ConfigurationError(Exception):
    """Custom exception for configuration errors"""

    pass

class ConnectionError(Exception):
    """Custom exception for connection errors"""
    pass

class JiraVersionManager:
    DEFAULT_CONFIG = {
            "jira_base_url": "https://jira.server.example",
        "jira_api_token": "",  # Don't set default token
            "project_keys": ["PROJECT1", "PROJECT2"],
        "version_formats": {
            "default": "{MAJOR}.{MINOR}.{PATCH}",
            "standard": "{PROJECT}.W{WEEK:02d}.{YEAR}.{MONTH:02d}.{DAY:02d}",
            "intake": "{PROJECT}.INTAKE.W{WEEK:02d}.{YEAR}.{MONTH:02d}.{DAY:02d}",
            "emergency": "{PROJECT}.W{WEEK:02d}.{YEAR}.{MONTH:02d}.{DAY:02d}_EMERGENCY",
            "semantic": "{MAJOR}.{MINOR}.{PATCH}{PRE_RELEASE}{BUILD}{METADATA}",
            "semantic_project": "{PROJECT}.{MAJOR}.{MINOR}.{PATCH}{PRE_RELEASE}{BUILD}{METADATA}",
            "semantic_with_v_before_major": "v{MAJOR}.{MINOR}.{PATCH}{PRE_RELEASE}{BUILD}{METADATA}"
        },
        "project_version_formats": {
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
                "frequency": 1        # Every week (use 2 for every two weeks)
            }
        },
        "archive_settings": {
            "default": {
                "months": 3,  # Archive after 3 months by default
                "enabled": False  # Disable archiving by default
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
        
        # Validate base URL
        if not self.config["jira_base_url"].startswith(("http://", "https://")) \
                or "jira.server.example" in self.config["jira_base_url"]:
            os.startfile(self.config["config_location"])
            raise ConfigurationError("Invalid Jira base URL. Please check your configuration.")

        # Validate Jira API token
        if not self.config["jira_api_token"]:
            os.startfile(self.config["config_location"])
            os.startfile(urljoin(self.config["jira_base_url"], "secure/ViewProfile.jspa?selectedTab=com.atlassian.pats.pats-plugin:jira-user-personal-access-tokens"))
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
        kwargs['headers'] = self.headers
        kwargs['verify'] = self.jira_verify_ssl
        
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.ConnectionError as e:
            self.logger.error("\nNetwork connection lost during request")
            raise ConnectionError(f"Connection error: {str(e.args)}")
        except requests.exceptions.Timeout as e:
            self.logger.error("\nRequest timed out after 30 seconds")
            raise ConnectionError(f"Timeout error: {str(e)}")
        except requests.exceptions.RequestException as e:
            status_code = e.response.status_code if e.response else "Unknown"
            error_msg = e.response.text if e.response else str(e)
            self.logger.error(f"\nAPI Error {status_code}: {error_msg}")
            raise JiraApiError(f"Jira API Error ({status_code}): {error_msg}")

    def get_weekdays_for_month(self, project_keys: str, start_date: Optional[str] = None, use_next_month: bool = True) -> List[datetime]:
        """Get release days based on project configuration"""
    
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
        release_config = self.config.get('release_days', {}).get(project_keys, {})
        if not release_config:
            release_config = {'days': self.config['release_days']['default'], 'frequency': 1}

        release_days = release_config['days']
        frequency = release_config.get('frequency', 1)

        _, num_days = calendar.monthrange(base_date.year, base_date.month)
        dates = []
        
        for day in range(base_date.day, num_days + 1):
            date = datetime(base_date.year, base_date.month, day)
            if date.weekday() in range(4):  # Monday = 0, Thursday = 3
                dates.append(date)
        
        return dates

    def get_issues_for_version(self, project_key: str, version_name: str) -> List[Dict[str, Any]]:
        """
        Get all issues associated with a version
        
        Args:
            project_keys: Jira project key
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

    def check_version_exists(self, project_key: str, version_name: str) -> bool:
        """
        Check if version exists
        
        Args:
            project_key: Jira project key
            version_name: Name of the version to check
            
        Returns:
            bool
            
        Raises:
            JiraApiError: If the API call fails
        """
        list_versions = self.list_versions(project_key)
        for version in list_versions:
            if version['name'] == version_name:
                return True
        return False  

    def create_version(self, project_key: str, version_name: str, release_date: Optional[str] = None, dry_run: bool = False, debug: bool = False) -> None:
        """
        Create a version in Jira project if it doesn't exist
        
        Args:
            project_key: Jira project key
            version_name: Name of the version to create
            release_date: Date to release the version
            dry_run: If True, simulate the creation
            debug: If True, print debug information
            
        Raises:
            ValueError: If project_key or version_name is empty
            JiraApiError: If the API call fails
        """

        if not project_key or not version_name:
            raise ValueError("Project key and version name are required")
            
        # Check if version exists
        exists = self.check_version_exists(project_key, version_name)
        if exists:
            issues = self.get_issues_for_version(project_key, version_name)
            self._print_version_exists_message(version_name, issues)
            return
            
        self.logger.debug(f"DEBUG: Creating version with name: {version_name}")
        
        if dry_run:
            self.logger.warning(f"DRY RUN: Would create version: {version_name}")
            return
            
        url = urljoin(self.config['jira_base_url'], "rest/api/2/version")
        payload = {
            "name": version_name,
            "project": project_key,
            "released": False,
            "releaseDate": release_date
        }

        self.logger.debug(f"payload: {payload}")
        
        response = self._make_request('POST', url, headers=self.headers, json=payload, timeout=30)
        if response.status_code == 201:
            self.logger.info(f"Created version: {version_name}")
        else:
            raise JiraApiError(f"Unexpected status code: {response.status_code}")
                
    def _print_version_exists_message(self, version_name: str, issues: List[Dict[str, Any]]) -> None:
        """Print message about existing version and its issues"""
        if issues:
            self.logger.debug(f"\nVersion {version_name} already exists with {len(issues)} issues:")
            for issue in issues:
                self.logger.debug(f"  - {issue['key']}: {issue['fields']['summary']} ({issue['fields']['status']['name']})")
        else:
            self.logger.info(f"Version {version_name} already exists (no issues assigned)")

    def create_version_name(self, format_key: str, project_key: str, date: Optional[datetime] = None,
                           semantic_action: Optional[str] = None,
                           major: Optional[int] = None, minor: Optional[int] = None, 
                           patch: Optional[int] = None, pre_release: Optional[str] = None,
                           build_number: Optional[int] = None, metadata: Optional[str] = None) -> str:
        """Create version name using format string and variables
        
        Args:
            format_key: Format key to use
            project_key: Project key to use
            date: Date to use for date-based versions
            semantic_action: Semantic action to use
            major: Major version number for semantic versions
            minor: Minor version number for semantic versions
            patch: Patch version number for semantic versions
            pre_release: Pre-release version for semantic versions
            build_number: Build number for semantic versions
            metadata: Metadata for semantic versions
            
        Returns:
            Formatted version name
        """
        self.logger.debug(f"format_key: {format_key}, project_key: {project_key}, date: {date}, semantic_action: {semantic_action}, major: {major}, minor: {minor}, patch: {patch}, pre_release: {pre_release}, build_number: {build_number}, metadata: {metadata}")
        
        format_pattern = self.get_version_format(format_key)

        if not format_pattern:
            raise ValueError(f"Unknown format key: {format_key}")
 
        # Handle semantic versioning formats
        if semantic_action in ('new_major', 'new_minor', 'new_patch', 'semantic'):
            if major is None:
                # Get the next version numbers if not provided
                current_major, current_minor, current_patch, current_pre_release, current_build_number, current_metadata = self.get_latest_semantic_version(project_key, semantic_action)
                if semantic_action == 'new_major':
                    major = current_major + 1
                    minor = 0
                    patch = 0
                elif semantic_action == 'new_minor':
                    major = current_major
                    minor = current_minor + 1
                    patch = 0
                elif semantic_action == 'new_patch':
                    major = current_major
                    minor = current_minor
                    patch = current_patch + 1
                else:  # semantic
                    major = current_major
                    minor = current_minor
                    patch = current_patch
                
        self.logger.debug(f"semantic_action: {semantic_action}, major: {major}, minor: {minor}, patch: {patch}, pre_release: {pre_release}, build_number: {build_number}, metadata: {metadata}")

        pre_release_str = f"-{pre_release}" if pre_release else ""
        build_str = f"+b{build_number}" if build_number is not None else ""
        metadata_str = f"-{metadata}" if metadata else ""

        # Handle date-based versions
        if not date:
            date = datetime.now()
        
        week_num = date.isocalendar()[1]
        try:
            return format_pattern.format(
                PROJECT=project_key,
                WEEK=week_num,
                YEAR=date.year,
                MONTH=date.month,
                DAY=date.day,
                MAJOR=major,
                MINOR=minor,
                PATCH=patch,
                PRE_RELEASE=pre_release_str,
                BUILD=build_str,
                METADATA=metadata_str
            )
        except Exception as e:
            self.logger.error(e)
            return format_pattern

    def create_versions_for_dates(self, project_key: str, dates: List[datetime], debug: bool = False, 
                                dry_run: bool = False, format_key: Optional[str] = None) -> None:
        """Create versions for a list of dates"""
        self.logger.debug(f"Creating versions for project: {project_key}, dates: {dates}, debug: {debug}, dry_run: {dry_run}, format_key: {format_key}")

        if not project_key or not dates:
            raise ValueError("Project key and dates are required")
        
        for date in dates:
            release_date = date.strftime("%Y-%m-%d")
            version_name = self.create_version_name(format_key, project_key, date)
            self.create_version(project_key, version_name, release_date, dry_run, debug)

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
            
        self.logger.info(f"Creating version for project: {project_key}, date: {date_str}, debug: {debug}, dry_run: {dry_run}, format_keys: {format_keys}")
        date = datetime.strptime(date_str, "%Y-%m-%d")
        self.create_versions_for_dates(project_key, [date], debug, dry_run, format_keys)

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
        
        response = self._make_request('GET', url, headers=self.headers, timeout=30)
        versions = response.json()
        if not isinstance(versions, list):
            raise JiraApiError("Expected array of versions in response")
        return versions

    def delete_version(self, version_id: str, move_issues_to: Optional[str] = None, dry_run: bool = False, debug: bool = False) -> None:
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
        
        if not self.validate_version_name(version_id):
            raise ValueError("Invalid version ID format")
        
        if dry_run:
            self.logger.warning(f"DRY RUN: Would delete version: {version_id}")
            return
        
        url = urljoin(self.config['jira_base_url'], f"rest/api/2/version/{version_id}/removeAndSwap")
        
        payload = {}
        if move_issues_to:
            payload = { 
                "moveFixIssuesTo": move_issues_to
            }
            
        response = self._make_request('POST', url, headers=self.headers, json=payload, timeout=30)
        
        if response.status_code == 204:
            self.logger.info(f"Deleted version: version_id: {version_id}")
        else:
            raise JiraApiError(f"Unexpected status code: {response.status_code}")

    def cleanup_versions(self, project_key: Optional[str] = None, days: int = 1, include_future: bool = False, include_released: bool = False, dry_run: bool = False, debug: bool = False) -> Dict[str, List[str]]:
        """
        Remove versions that are:
        - Have no issues assigned
        - More than days days in the past
        - Are in the future (if include_future=True)
        - Are unreleased (or include released if include_released=True)
        
        Args:
            project_key: The Jira project key (if None, cleanup all configured projects)
            days: Number of days to consider a version old
            include_future: Whether to also remove versions in the future
            include_released: Whether to also remove released versions (default: False)
            dry_run: If True, only simulate the cleanup without making changes
            debug: If True, print debug information
        Returns:
            Dictionary mapping project keys to lists of removed version names
        """
        # Set default days to 1 if not provided
        days = days or 1
        removed_versions = {}
        current_date = datetime.now()
        
        # Get list of projects to process
        projects = project_key.split(',') if project_key else self.config['project_keys']
        
        for proj_key in projects:
            removed_versions[proj_key] = []
            versions = self.list_versions(proj_key)
            
            for version in versions:
                # Skip if version is released and we're not including released versions
                if version.get('released', False) and not include_released:
                    continue
                
                # Check if version has a date in its name using our format patterns
                parsed = self.parse_version_name(version['name'])
                if parsed:
                    version_date = datetime(
                        year=parsed['YEAR'],
                        month=parsed['MONTH'],
                        day=parsed['DAY']
                    )

                    # Check if version has any issues
                    issues = self.get_issues_for_version(proj_key, version['name'])
                    if issues:
                        continue

                    # Check if version is more than days days old or in the future
                    if not (include_future and version_date > current_date) or not ((current_date - version_date).days <= days):
                        continue
                    
                    self.logger.info(f"Removing version {version['name']}")

                    # If we got here, the version meets all criteria for removal
                    if not dry_run:
                        self.delete_version(version['id'])
                    removed_versions[proj_key].append(version['name'])
        
        return removed_versions

    def get_project_version_formats(self, project_key: str) -> List[str]:
        """Get version formats for a specific project"""
        return self.config['project_version_formats'].get(project_key, self.config['project_version_formats']['default'])
    
    def get_version_format(self, format_key: str) -> str:
        """Get a specific version format"""
        #print(self.config['version_formats'].get(format_key, '0'))
        return self.config['version_formats'].get(format_key, self.config['version_formats']['default'])

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

    def archive_releases(self, project_key: Optional[str] = None, months: Optional[int] = None, dry_run: bool = False, debug: bool = False) -> Dict[str, List[str]]:
        """
        Archive released versions that are older than the specified number of months.
        
        Args:
            project_key: The Jira project key (if None, archive for all configured projects)
            months: Number of months after which to archive releases (if None, use project settings)
            dry_run: If True, only simulate the archiving without making changes
            debug: If True, print debug information

        Returns:
            Dictionary mapping project keys to lists of archived version names
        """
        archived_versions = {}
        current_date = datetime.now()
        
        # Get list of projects to process
        projects = project_key.split(',') if project_key else self.config['project_keys']
        
        for proj_key in projects:
            # Get project-specific archive settings
            archive_config = self.config.get('archive_settings', {}).get(proj_key, 
                self.config['archive_settings']['default'])
            
            # Skip if archiving is disabled for this project
            if not archive_config.get('enabled', True):
                self.logger.info(f"Archiving is disabled for project {proj_key}")
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
                    
                # Check if version has a date in its name using our format 
                parsed = self.parse_version_name(version['name'])
                if parsed:
                    version_date = datetime(
                        year=parsed['YEAR'],
                        month=parsed['MONTH'],
                        day=parsed['DAY']
                    )
                    
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
                        if dry_run:
                            self.logger.warning(f"DRY RUN: Would archive version: {version['name']}")

                        if not dry_run:
                            self._make_request('PUT', url, json=data)
                        archived_versions[proj_key].append(version['name'])
        
        return archived_versions

    def parse_version_name(self, version_name: str) -> Optional[Dict[str, Any]]:
        """
        Parse a version name according to configured formats.
        
        Args:
            version_name: The version name to parse
            
        Returns:
            Dictionary containing parsed components (PROJECT, WEEK, YEAR, MONTH, DAY) 
            and the matched format, or None if no format matches
        """
        # Remove _emergency suffix if present
        base_name = version_name.split('_')[0]
        
        for format_name, format_pattern in self.config['version_formats'].items():
            try:
                # Convert format pattern to regex
                regex_pattern = (
                    format_pattern
                    .replace('{PROJECT}', '(?P<PROJECT>[^.]+)')
                    .replace('{WEEK:02d}', '(?P<WEEK>\d{2})')
                    .replace('{YEAR}', '(?P<YEAR>\d{4})')
                    .replace('{MONTH:02d}', '(?P<MONTH>\d{1,2})')
                    .replace('{DAY:02d}', '(?P<DAY>\d{1,2})')
                    .replace('.', '\.')
                )
                
                match = re.match(f'^{regex_pattern}$', base_name)
                if match:
                    result = match.groupdict()
                    # Convert numeric fields to integers
                    for field in ['WEEK', 'YEAR', 'MONTH', 'DAY']:
                        if field in result:
                            result[field] = int(result[field])

                    # Add metadata
                    result['format_name'] = format_name
                    result['format_pattern'] = format_pattern
                    result['original_name'] = version_name
                    result['has_emergency'] = '_emergency' in version_name
                    
                    return result
                    
            except re.error:
                continue
        
        return None

    def scanandfix_versions(self, project_key: Optional[str] = None, dry_run: bool = False, debug: bool = False) -> Dict[str, List[Tuple[str, str]]]:
        """Scan and fix version formats.
        
        Args:
            project_key (str, optional): Project key to fix versions for. If None, fixes all projects.
            dry_run (bool): If True, only simulate changes without applying them.
            debug (bool): If True, print debug information

        Returns:
            dict: Mapping of project keys to lists of tuples (old_name, new_name)
        """
        self.logger.debug(f"Scanning and fixing versions for project {project_key}")
        results = {}

        versions = self.list_versions(project_key)
        changes = []

        for version in versions:
            # Try to parse the version name
            parsed = self.parse_version_name(version['name'])
            if parsed:
                # Generate new version name using the detected format
                date = datetime(
                    year=parsed['YEAR'],
                    month=parsed['MONTH'],
                    day=parsed['DAY']
                )

                new_base_name = self.create_version_name(
                    parsed['format_name'],
                    parsed['PROJECT'],
                    date
                )
                
                # Preserve any prefixes/postfixes from original name
                original_base = version['name'].split('_')[0]  # Remove emergency suffix if present
                prefix = version['name'][:len(version['name'])-len(original_base)] if version['name'].endswith(original_base) else ''
                postfix = version['name'][len(original_base):] if version['name'].startswith(original_base) else ''
                new_name = f"{prefix}{new_base_name}{postfix}"
                
                # Check if the new name is different
                if new_name != version['name']:
                    if dry_run:
                        self.logger.warning(f"DRY RUN: Would rename version: {version['name']} -> {new_name}")
                    
                    if not dry_run:
                        # Update version name in Jira
                        if self.check_version_exists(project_key, new_name):
                            self.logger.warning(f"Skipping {version['name']} -> {new_name} because it already exists in Jira")
                            continue
                        self._make_request('PUT', f"{self.config['jira_base_url']}/rest/api/2/version/{version['id']}", json={'name': new_name})
                    changes.append((version['name'], new_name))
        
        if changes:
            results[project_key] = changes
        
        return results

    def parse_semantic_version(self, version_name: str) -> Optional[Dict[str, Any]]:
        """Parse a semantic version name.
        
        Args:
            version_name: Version name to parse (e.g. '1.2.3-alpha.1+b42', '2.0-beta.2')
            
        Returns:
            Dictionary with version components, or None if no match
        """
        self.logger.debug(f"Parsing semantic version: {version_name}")

        # Match full semantic version with optional pre-release, build number and metadata
        pattern = r'^(?P<MAJOR>\d+)\.(?P<MINOR>\d+)\.(?P<PATCH>\d+)(?P<PRE_RELEASE>-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?P<BUILD>\+b\d+)?(?P<METADATA>[-+][0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$'
        match = re.match(pattern, version_name)
        self.logger.debug(f"match: {match}")
        if match:
            result = match.groupdict()
            # Convert numeric fields
            for field in ['MAJOR', 'MINOR', 'PATCH']:
                result[field] = int(result[field])
            return result
        
        # Match major.minor version
        pattern = r'^(?P<MAJOR>\d+)\.(?P<MINOR>\d+)(?P<PRE_RELEASE>-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?P<BUILD>\+b\d+)?(?P<METADATA>[-+][0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$'
        match = re.match(pattern, version_name)
        self.logger.debug(f"match: {match}")
        if match:
            result = match.groupdict()
            for field in ['MAJOR', 'MINOR']:
                result[field] = int(result[field])
            return result
        
        # Match major version only
        pattern = r'^(?P<MAJOR>\d+)(?P<PRE_RELEASE>-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?P<BUILD>\+b\d+)?(?P<METADATA>[-+][0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$'
        match = re.match(pattern, version_name)
        self.logger.debug(f"match: {match}")
        if match:
            result = match.groupdict()
            result['MAJOR'] = int(result['MAJOR'])
            return result
        
        return None

    def get_latest_semantic_version(self, project_key: str, format_key: str) -> Tuple[int, int, int, Optional[str], Optional[int], Optional[str]]:
        """Get the latest semantic version numbers for a project.
        
        Args:
            project_key: Project key
            format_key: Format key ('semantic', 'semantic_minor', or 'semantic_major')
            
        Returns:
            Tuple of (major, minor, patch, pre_release, build, metadata) version numbers
        """
        versions = self.list_versions(project_key)
        latest_major = latest_minor = latest_patch = 0
        latest_pre_release = None
        latest_build = None
        latest_metadata = None
        
        for version in versions:
            parsed = self.parse_semantic_version(version['name'])
            if parsed:
                major = parsed.get('MAJOR', 0)
                minor = parsed.get('MINOR', 0)
                patch = parsed.get('PATCH', 0)
                pre_release = parsed.get('PRE_RELEASE', '')[1:] if parsed.get('PRE_RELEASE') else None
                build = int(parsed.get('BUILD', '+b0')[2:]) if parsed.get('BUILD') else None
                metadata = parsed.get('METADATA', '')[1:] if parsed.get('METADATA') else None
    
                if major > latest_major:
                    latest_major = major
                    latest_minor = minor
                    latest_patch = patch
                    latest_pre_release = pre_release
                    latest_build = build
                    latest_metadata = metadata
                elif major == latest_major:
                    if minor > latest_minor:
                        latest_minor = minor
                        latest_patch = patch
                        latest_pre_release = pre_release
                        latest_build = build
                        latest_metadata = metadata
                    elif minor == latest_minor and patch > latest_patch:
                        latest_patch = patch
                        latest_pre_release = pre_release
                        latest_build = build
                        latest_metadata = metadata
                    elif minor == latest_minor and patch == latest_patch:
                        if build and (not latest_build or build > latest_build):
                            latest_build = build
                            latest_pre_release = pre_release
                            latest_metadata = metadata
        

        return latest_major, latest_minor, latest_patch, latest_pre_release, latest_build, latest_metadata

    def validate_version_name(self, version_name: str) -> bool:
        """Validate version name format and characters."""
        if not version_name:
            return False
        
        # Check for invalid characters
        invalid_chars = '<>:"/\\|?*'
        if any(char in version_name for char in invalid_chars):
            return False
        
        # Check length
        if len(version_name) > 100:  # Jira's limit
            return False
        
        return True

    def create_release_calendar(self, project_key: str, frequency: Optional[str] = None,
                                start_date: Optional[str] = None, end_date: Optional[str] = None,
                                weekdays: Optional[str] = None, monthdays: Optional[str] = None,
                                yeardays: Optional[str] = None, days: Optional[str] = None,
                                interval: Optional[int] = None, current_month: bool = True,
                                next_month: bool = True, next_working_day: bool = False) -> List[datetime]:
        """Create a calendar of release dates based on various parameters.
        
        Args:
            project_key: The project key to get release configuration for
            frequency: Release frequency ('daily', 'weekly', 'monthly')
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            weekdays: Comma-separated list of weekdays (0-6, 0=Monday)
            monthdays: Comma-separated list of days of month (1-31)
            yeardays: Comma-separated list of days of year (1-366)
            days: Comma-separated list of specific days
            interval: Interval between releases in days
            current_month: Whether to include current month
            next_month: Whether to include next month
            next_working_day: Whether to move weekend releases to next working day
            
        Returns:
            List of datetime objects representing release dates
        """
        self.logger.debug(f"Creating release calendar with params: frequency={frequency}, start_date={start_date}, end_date={end_date},weekdays={weekdays}, "
                         f"monthdays={monthdays}, yeardays={yeardays}, days={days}, interval={interval}, "
                         f"current_month={current_month}, next_month={next_month}, next_working_day={next_working_day}")
        
        # Get project-specific release configuration
        release_config = self.config.get('release_days', '[0, 1, 2, 3]').get(project_key, 
                        self.config['release_days']['default'])
        
        # Parse weekdays from config or parameters
        if weekdays:
            allowed_weekdays = [int(d) for d in weekdays.split(',')]
        else:
            allowed_weekdays = release_config;
        
        # Validate weekdays
        if not all(0 <= d <= 6 for d in allowed_weekdays):
            raise ValueError("Weekdays must be between 0 and 6 (0=Monday, 6=Sunday)")
        
        # Get current date and calculate date ranges
        today = datetime.now()
        dates = []
        
        # Calculate start and end dates based on current/next month flags
        start_date = today  # Start from today
        
        # Calculate end date
        if next_month:
            if start_date.month == 12:
                end_date = datetime(start_date.year + 1, 1, 1)
            else:
                end_date = datetime(start_date.year, start_date.month + 2, 1)
        else:
            if start_date.month == 12:
                end_date = datetime(start_date.year + 1, 1, 1)
            else:
                end_date = datetime(start_date.year, start_date.month + 1, 1)
        
        current_date = start_date
        while current_date < end_date:
            # Check if the current date matches our criteria
            if frequency == 'weekly':
                # Only include dates that fall on specified weekdays
                if current_date.weekday() in allowed_weekdays:
                    dates.append(current_date)
                current_date += timedelta(days=1)
            
            elif frequency == 'monthly' and monthdays:
                # Include specified days of the month
                month_days = [int(d) for d in monthdays.split(',')]
                if current_date.day in month_days:
                    dates.append(current_date)
                current_date += timedelta(days=1)
            
            elif yeardays:
                # Include specified days of the year
                year_days = [int(d) for d in yeardays.split(',')]
                if current_date.timetuple().tm_yday in year_days:
                    dates.append(current_date)
                current_date += timedelta(days=1)
            
            elif days:
                # Include specific days
                day_list = [int(d) for d in days.split(',')]
                if (current_date - start_date).days in day_list:
                    dates.append(current_date)
                current_date += timedelta(days=1)
            
            elif interval:
                # Add dates based on interval
                if (current_date - start_date).days % interval == 0:
                    dates.append(current_date)
                current_date += timedelta(days=1)
            
            else:
                # Default: include all weekdays in allowed_weekdays
                if current_date.weekday() in allowed_weekdays:
                    dates.append(current_date)
                current_date += timedelta(days=1)
        
        # Handle next working day adjustment
        if next_working_day:
            adjusted_dates = []
            for date in dates:
                # If date falls on weekend, move to next working day
                while date.weekday() > 4:  # Saturday = 5, Sunday = 6
                    date += timedelta(days=1)
                adjusted_dates.append(date)
            dates = adjusted_dates
        
        # Sort and remove duplicates
        dates = sorted(list(set(dates)))
        
        self.logger.debug(f"Generated {len(dates)} release dates")
        self.logger.debug(f"Dates: {dates}")
        return dates

def print_menu():
    """Print the interactive mode menu"""
    menu_items = {
        'h': ('Help', 'Show help menu'),
        'c': ('Config', 'Edit configuration'),
        'l': ('List', 'List versions'),
        'n': ('New', 'Create new versions'),
        'd': ('Delete', 'Delete version'),
        'm': ('Maintenance', 'Perform maintenance tasks'),
        's': ('Scan and fix', 'Scan and fix version formats'),
        'x': ('Cleanup', 'Cleanup old versions'),
        'a': ('Archive', 'Archive old versions'),
        'q': ('Quit', 'Exit the program'),
        'ESC': ('', 'Exit the program')
    }
    
    clear_screen()
    print("\nJira Version Manager Interactive Mode")
    print("\nAvailable commands:")
    for key, (name, description) in menu_items.items():
        if name:  # Skip empty names (like ESC)
            print(f"  '{key}' - {name:<12} : {description}")
    print("\nCreation of new versions, maintanance, cleanup and archiving of old versions is executed with default configuration.")

def handle_key_input(key: str, manager: JiraVersionManager, args: argparse.Namespace) -> bool:
    """Handle a single key input in interactive mode
    
    Args:
        key: The key that was pressed
        manager: The JiraVersionManager instance
        args: The argument parser
        
    Returns:
        bool: True if the program should continue, False if it should exit
    """
    if hasattr(args, 'project_keys'):
        project_keys_str = args.project_keys
    else:
        args.project_keys = None
        project_keys_str = 'all'

    if key == 'q' or key == chr(27):  # q or ESC
        print("\nExiting...")
        return False
    elif key == 'h':
        clear_screen()
        manager.parser.print_help()
        print("\nExiting...")
        return False
    elif key == 'c':
        args.edit = True
        handle_config_command(manager, args)
        print("\nExiting...")
        return False
    elif key == 'l':
        print("\nEnter comma-separated project keys to list versions, * for all projects")
        project_keys = input(f"Project keys: {project_keys_str} or: ").strip() or args.project_keys
        released = input("Show released versions? (y/n): ").strip() or 'n'
        if released == 'y':
            args.show_released = True
        else:
            args.show_released = False
        detailed = input("Show detailed information? (y/n): ").strip() or 'n'
        if detailed == 'y':
            args.detailed = True
        else:
            args.detailed = False
        if project_keys == '*':
            args.project_keys =  None
            handle_list_command(manager, args)
        else:
            args.project_keys = project_keys
            handle_list_command(manager, args)
        print("\nExiting...")
        return False
    elif key == 'n':
        handle_create_command(manager, args)
        print("\nExiting...")        
        return False
    elif key == 'd':    
        print("\nEnter version name to delete (or press Enter to cancel):")
        version_name = input().strip()
        print("Move issues from removed version to:")
        move_to = input().strip()
        if version_name:
            args.version_name = version_name
            args.move_to = move_to
            handle_delete_command(manager, args)
        else:
            print("\nOperation cancelled")
            os.system('pause')
        print("\nExiting...")
        return False
    elif key == 'm':
        print("\nEnter comma-separated project keys to perform maintenance tasks, * for all projects):")
        project_keys = input(f"Project keys: {project_keys_str} or: ").strip() or args.project_keys
        if project_keys == '*':
            args.project_keys = None
            handle_maintenance_command(manager, args)
        else:
            args.project_keys = project_keys
            handle_maintenance_command(manager, args)
        print("\nExiting...")
        return False
    elif key == 's':
        print("\nEnter comma-separated project keys to scan and fix, * for all projects or press Enter to cancel):")
        project_keys = input(f"Project keys: {project_keys_str} or: ").strip() or args.project_keys
        if project_keys == '*':
            args.project_keys = None
            handle_scanandfix_command(manager, args)
        else:
            args.project_keys = project_keys
            handle_scanandfix_command(manager, args)
        print("\nExiting...")
        return False
    elif key == 'x':
        print("\nEnter comma-separated project keys to perform cleanup tasks, * for all projects or press Enter to cancel):")
        project_keys = input(f"Project keys: {project_keys_str} or: ").strip() or args.project_keys
        days = input("Remove empty versions older than this many days back (default: 1): ").strip() or 1
        future = input("Remove future versions with no issues? (y/n): ").strip() or 'n'
        if future == 'y':
            args.cleanup_future = True
        else:
            args.cleanup_future = False
        released = input("Include released versions in cleanup? (y/n): ").strip() or 'n'
        if released == 'y':
            args.include_released = True
        else:
            args.include_released = False
        if project_keys == '*':
            args.project_keys = None
            handle_cleanup_command(manager, args)
        else:
            args.project_keys = project_keys
            handle_cleanup_command(manager, args)
        print("\nExiting...")
        return False
    elif key == 'a':
        print("\nEnter comma-separated  project keys to perform archive tasks, * for all projects or press Enter to cancel):")
        project_keys = input(f"Project keys: {project_keys_str} or: ").strip() or args.project_keys
        archive_releases = input("Archive released versions? (y/n): ").strip() or 'n'
        if archive_releases == 'y':
            args.archive_releases = True
        else:
            args.archive_releases = False
        cleanup_future = input("Remove future versions with no issues? (y/n): ").strip() or 'n'
        if cleanup_future == 'y':
            args.cleanup_future = True
        else:
            args.cleanup_future = False
        if project_keys == '*':
            args.project_keys = None
            handle_archive_command(manager, args)
        else:
            args.project_keys = project_keys
            handle_archive_command(manager, args)
        print("\nExiting...")
        return False
    return True

def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser"""
    formatter = lambda prog: argparse.HelpFormatter(prog,max_help_position=33)
    parser = argparse.ArgumentParser(description="A Python tool to manage Jira versions, supporting automatic version creation, cleanup, and archiving.", epilog="Use --help for more information on each command.", formatter_class=formatter)
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--dry-run', action='store_true', help='Simulate actions without making changes')
    parser.add_argument('--no-verify-ssl', action='store_true', help='Disable SSL certificate verification')
    parser.add_argument('-q', '--quiet', action='store_true', help='Suppress informational output')
    parser.add_argument('--output-format', choices=['text', 'json', 'yaml'], default='text', help='Output format (default: text)')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Config command
    config_parser = subparsers.add_parser('config', help='Show or edit configuration', description='Show or edit configuration', formatter_class=formatter)
    config_parser.add_argument('config_key', nargs='?', help='Configuration key to show')
    config_parser.add_argument('--edit', action='store_true', help='Edit configuration')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List versions', description='List Unreleased versions for a project or all configured projects', formatter_class=formatter)
    list_parser.add_argument('--project-keys', help='Comma-separated list of Jira project keys (if not provided, list for all projects)')
    list_parser.add_argument('--show-released', action='store_true', default=False, help='Show only released versions (default: False)')
    list_parser.add_argument('--show-all', action='store_true', default=False, help='Show all versions (default: False)')
    list_parser.add_argument('--detailed', action='store_true', default=False, help='Show detailed information including issues (default: False)')
    
    # Create command
    create_parser = subparsers.add_parser('create', help='Create versions', description='Create versions for a project or all configured projects, semantic or date-based depending on the format', formatter_class=formatter)
    create_parser.add_argument('--project-keys', help='Comma-separated list of Jira project keys (if not provided, create for all projects)')
    create_parser.add_argument('-F', '--formats', help='Comma-separated list of format names to use (default: all formats)')

    # Add date-based versioning group
    date_group = create_parser.add_argument_group('date-based versioning')
    date_group.add_argument('-d', '--date', help='Specific date (YYYY-MM-DD)')
    date_group.add_argument('-s', '--start-date', help='Start date (YYYY-MM-DD)')
    date_group.add_argument('-e', '--end-date', help='End date (YYYY-MM-DD)')
    date_group.add_argument('-f', '--frequency', choices=['daily', 'weekly', 'monthly'], help='Frequency of version creation (default: daily)')
    date_group.add_argument('--weekdays', help='Comma-separated list of weekdays (0-6, 0=Monday, 6=Sunday) to create versions on (default: monday to thursday) // never release on Friday! ;D', metavar='[0,1,2…]')
    date_group.add_argument('--monthdays', help='Comma-separated list of monthdays (1-31) to create versions on (default: 1 to 28)', metavar='[1,2…]')
    date_group.add_argument('--yeardays', help='Comma-separated list of yeardays (1-366) to create versions on (default: 1 to 365)', metavar='[1,2…]')
    date_group.add_argument('-nd', '--next-working-day', action='store_true', default=True, help='Create versions on next working day if weekend (default: True)')
    date_group.add_argument('-dd', '--days', help='Comma-separated list of days (1-365) to create versions on (default: 1 to 365)')
    date_group.add_argument('-id', '--interval', type=int, help='Interval (in days) between versions (default: 1)')
    
    date_group.add_argument('-cm', '--current-month', action='store_true', default=True, help='Create versions for current month (default: True)')
    date_group.add_argument('-nm', '--next-month', action='store_true', default=True, help='Create versions for next month (default: True)')

    # Add semantic versioning group
    semantic_group = create_parser.add_argument_group('semantic versioning', description='Semantic versioning options, compatible with semantic versioning specification (https://semver.org/)')
    semantic_group.add_argument('-m', '--major', type=int, help='Major version number', metavar='int')
    semantic_group.add_argument('-n', '--minor', type=int, help='Minor version number', metavar='int')
    semantic_group.add_argument('-p', '--patch', type=int, help='Patch version number', metavar='int')
    semantic_group.add_argument('-r', '--pre-release', help='Pre-release version (e.g. alpha.1, beta.2, rc.1)', metavar='str')
    semantic_group.add_argument('-b', '--build', type=int, help='Build number (e.g. 42 for +b42)', metavar='int')
    semantic_group.add_argument('--metadata', help='Version metadata (e.g. rc.1)', metavar='str')
    # Automatic semantic versioning
    auto_semantic_group = create_parser.add_argument_group('automatic semantic versioning', description='Create next version based on the latest version')
    auto_semantic_group.add_argument('-M', '--new-major', action='store_true', help='Create next major version (1.2.3 ⇒ 2.0.0)')
    auto_semantic_group.add_argument('-N', '--new-minor', action='store_true', help='Create next minor version (1.2.3 ⇒ 1.3.0)')
    auto_semantic_group.add_argument('-P', '--new-patch', action='store_true', help='Create next patch version (1.2.3 ⇒  1.2.4)')
    auto_semantic_group.add_argument('-R', '--new-pre-release', choices=['alpha', 'beta', 'rc'], 
                          help='Create new pre-release version (alpha, beta, or rc)', metavar='str')

    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete a version', description='Delete a version for a project or all configured projects', formatter_class=formatter)
    delete_parser.add_argument('--project-keys', help='Comma-separated list of Jira project keys')
    delete_parser.add_argument('--version-name', required=True, help='Version name to delete')
    delete_parser.add_argument('--move-to', help='Version name to move issues to (optional)')

    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Remove old versions with no issues', description='Remove old versions with no issues for a project or all configured projects', formatter_class=formatter)
    cleanup_parser.add_argument('--project-keys', help='Comma-separated list of Jira project keys (if not provided, cleanup for all projects)')
    cleanup_parser.add_argument('--days', type=int, help='Remove versions older than this many days back (default: 1)')
    cleanup_parser.add_argument('--include-future', action='store_true', help='Include versions in the future (default: False)')
    cleanup_parser.add_argument('--include-released', action='store_true', help='Include released versions in cleanup (default: False)')
    
    # Archive command
    archive_parser = subparsers.add_parser('archive', help='Archive old released versions', description='Archive old released versions for a project or all configured projects', formatter_class=formatter)
    archive_parser.add_argument('--project-keys', help='Comma-separated list of Jira project keys (if not provided, archive for all projects)')
    archive_parser.add_argument('--months', type=int, help='Archive versions older than this many months (default: 3)')

    # Maintenance command
    maintenance_parser = subparsers.add_parser('maintenance', help='Perform maintenance tasks', description='Perform maintenance tasks: \n - scan and fix version formats \n - remove old versions with no issues \n - create versions for current and next month \n - [Optional] remove future versions with no issues \n - [Optional] archive old released versions', formatter_class=formatter)
    maintenance_parser.add_argument('--project-keys', help='Comma-separated list of Jira project keys (if not provided, perform maintenance for all projects)')
    maintenance_parser.add_argument('--archive-releases', action='store_true', help='Archive old released versions')
    maintenance_parser.add_argument('--cleanup-future', action='store_true', help='Remove future versions with no issues')
    maintenance_parser.add_argument('--include-released', action='store_true', help='Include released versions in cleanup (default: False)')

    # Scan and fix command
    scanandfix_parser = subparsers.add_parser('scanandfix', help='Scan and fix version formats', description='Scan and fix version formats for a project or all configured projects', formatter_class=formatter)
    scanandfix_parser.add_argument('--project-keys', help='Comma-separated list of Jira project keys (if not provided, scan all projects)')
    
    return parser

def handle_config_command(manager: JiraVersionManager, args: argparse.Namespace) -> None:
    """Handle the config command"""
    manager.logger.debug(f"Handling config command with args: {args}")
    if hasattr(args, 'config_key') and args.config_key:
        try:
            if args.config_key == 'jira_api_token': 
                manager.logger.info(f"{args.config_key}: '***'")
            else:
                manager.logger.info(f"{manager.config[args.config_key]}")
        except KeyError:
            manager.logger.error(f"Key '{args.config_key}' not found in configuration.")
    elif hasattr(args, 'edit') and args.edit:
        os.startfile(manager.config['config_location'])
    else:
        manager.logger.info("Current Configuration:")
        safe_config = manager.config.copy()
        if 'jira_api_token' in safe_config:
            safe_config['jira_api_token'] = '***'
        for key, value in safe_config.items():
            manager.logger.info(f"{key}: {json.dumps(value, indent=2)}")
        manager.logger.info("\nUse --edit to edit the configuration file.")

def handle_list_command(manager: JiraVersionManager, args: argparse.Namespace) -> None:
    """Handle the list command"""
    manager.logger.debug(f"Handling list command with args: {args}")

    if 'list' == args.command:
        args.command = None
        handle_key_input('l', manager, args)
        return
    
    projects = args.project_keys.split(',') if args.project_keys else manager.config['project_keys']

    for project_key in projects:
        versions = manager.list_versions(project_key)
        
        # Filter versions based on release status
        if not hasattr(args, 'show_all') or not args.show_all :
            if hasattr(args, 'show_released') and args.show_released:
                versions = [v for v in versions if v.get('released', False)]
            else:
                versions = [v for v in versions if not v.get('released', False)]
        
        if versions:
            manager.logger.info(f"\n{project_key}:")
            for version in versions:
                manager.logger.info(f"  - {version['name']} ({'Released' if version.get('released', False) else 'Unreleased'})")
                
                if hasattr(args, 'detailed') and args.detailed:
                    issues = manager.get_issues_for_version(project_key, version['name'])
                    if issues:
                        manager.logger.info("    Issues:")
                        for issue in issues:
                            manager.logger.info(f"      - {issue['key']}: {issue['fields']['summary']} ({issue['fields']['status']['name']})")
                    else:
                        manager.logger.info("    No issues assigned")
        else:
            manager.logger.info(f"\n{project_key}: No versions found")

def handle_create_command(manager: JiraVersionManager, args: argparse.Namespace) -> None:
    """Handle the create command"""
    manager.logger.debug(f"Handling create command with args: {args}")
    projects = args.project_keys.split(',') if args.project_keys else manager.config['project_keys']

    if args.dry_run:
        manager.logger.info("DRY RUN: The following versions would be created:")
    
    for project_key in projects:
        print(args)
        formats = hasattr(args, 'formats') and args.formats.split(',') or None

        for format_key in formats or manager.get_project_version_formats(project_key):
            current_format = manager.config['version_formats'][format_key]
            
            if any(x in current_format for x in ('MAJOR', 'MINOR', 'PATCH')):
                manager.logger.debug(f"Format contains semantic versioning: {current_format}")
                
                # Handle semantic versioning
                manager.logger.debug(f"Handling semantic versioning with args: {args}")
                semantic_action = None
                major = minor = patch = None
                pre_release = hasattr(args, 'pre_release') and args.pre_release or None
                build_number = hasattr(args, 'build') and args.build or None
                metadata = hasattr(args, 'metadata') and args.metadata or None
                
                # Determine format and version numbers
                if hasattr(args, 'new_major') and args.new_major:
                    semantic_action = 'new_major'
                elif hasattr(args, 'new_minor') and args.new_minor:
                    semantic_action = 'new_minor'
                elif hasattr(args, 'new_patch') and args.new_patch:
                    semantic_action = 'new_patch'
                else:
                    # Use explicit version numbers
                    major = hasattr(args, 'major') and args.major or 0
                    minor = hasattr(args, 'minor') and args.minor or 0
                    patch = hasattr(args, 'patch') and args.patch or 0
                    semantic_action = 'semantic'
                
                # Handle new pre-release versions
                if hasattr(args, 'new_pre_release') and args.new_pre_release:
                    latest_major, latest_minor, latest_patch, latest_pre, latest_build, latest_metadata = \
                        manager.get_latest_semantic_version(project_key, semantic_action)
                    
                    # If no explicit version numbers provided, use latest
                    if major == minor == patch == 0:
                        major = latest_major
                        minor = latest_minor
                        patch = latest_patch

                    manager.logger.debug(f"Latest pre-release: {latest_pre}")

                    # Parse latest pre-release version if it exists
                    if latest_pre and latest_pre.startswith(args.new_pre_release):
                        manager.logger.debug(f"Latest pre-release: {latest_pre}")
                        try:
                            pre_num = int(latest_pre.split('.')[-1])
                            pre_release = f"{args.new_pre_release}.{pre_num + 1}"
                        except (IndexError, ValueError):
                            pre_release = f"{args.new_pre_release}.1"
                    else:
                        pre_release = f"{args.new_pre_release}.1"

                formats = hasattr(args, 'formats') and args.formats.split(',') or None

                version_name = manager.create_version_name(
                    format_key, project_key,
                    semantic_action=semantic_action,
                    major=major, minor=minor, patch=patch,
                    pre_release=pre_release,
                    build_number=build_number, metadata=metadata
                )

                manager.logger.debug(f"Version name: {version_name}")

                if not manager.validate_version_name(version_name):
                    raise ValueError("Invalid version name format")
                
                if args.dry_run:
                    manager.logger.info(f"\n{project_key}:")
                    if manager.get_version_by_name(project_key, version_name):
                        manager.logger.info(f"  - {version_name} (already exists)")
                    else:
                        manager.logger.info(f"  - {version_name} (would create)")
                else:
                    manager.create_version(project_key, version_name, None, args.dry_run, args.debug)
                    manager.logger.info(f"Created version {version_name} for {project_key}")
                
            if any(x in current_format for x in ('{DAY}', '{MONTH}', '{YEAR}')):
                manager.logger.debug("Date-based version")

                # Handle date-based versions
                manager.logger.debug(f"Format contains date-based versions: {current_format}")
                
                try:
                    if hasattr(args, 'date') and args.date:
                        # Create versions for specific date
                        date = datetime.strptime(args.date, "%Y-%m-%d")
                        dates = [date]
                    else:
                        # Get dates for next month or current month
                        dates = manager.create_release_calendar(
                    project_key,
                            frequency=hasattr(args, 'frequency') and args.frequency or None,
                            start_date=hasattr(args, 'start_date') and args.start_date or None,
                            end_date=hasattr(args, 'end_date') and args.end_date or None,
                            weekdays=hasattr(args, 'weekdays') and args.weekdays or None,
                            monthdays=hasattr(args, 'monthdays') and args.monthdays or None,
                            yeardays=hasattr(args, 'yeardays') and args.yeardays or None,
                            days=hasattr(args, 'days') and args.days or None,
                            interval=hasattr(args, 'interval') and args.interval or None,
                            current_month=hasattr(args, 'current_month') and args.current_month or True,
                            next_month=hasattr(args, 'next_month') and args.next_month or True,
                            next_working_day=hasattr(args, 'next_working_day') and args.next_working_day or False
                        )
                    if args.dry_run:
                        conditional = "Would create"
                    else:
                        conditional = "Creating"

                    manager.logger.info(f"\n{conditional} versions for {project_key}:")
                    manager.create_versions_for_dates(project_key, dates, args.debug, args.dry_run, format_key)    
                except ConnectionError as e:
                    manager.logger.error(f"Connection error: {str(e)}")
                except Exception as e:
                    manager.logger.error(f"Error processing {project_key}: {str(e)}")
                    if args.debug:
                        import traceback
                        traceback.print_exc()

def handle_delete_command(manager: JiraVersionManager, args: argparse.Namespace) -> None:
    """Handle the delete command"""
    manager.logger.debug(f"Handling delete command with args: {args}")
    projects = args.project_keys.split(',') if args.project_keys else manager.config['project_keys']

    for project_key in projects:
        version = manager.get_version_by_name(project_key, args.version_name)
        if not version:
            manager.logger.info(f"Version not found: {args.version_name} in {project_key} project")
            continue

        move_to_version = None
        if hasattr(args, 'move_to') and args.move_to:
            move_to_version = manager.get_version_by_name(project_key, args.move_to)
            if not move_to_version:
                raise ValueError(f"Target version not found: {args.move_to}")
            
        if not args.dry_run:
            manager.delete_version(version['id'], move_to_version['id'] if move_to_version else None, args.dry_run, args.debug)
        else:
            manager.logger.info(f"DRY RUN: Would delete version: {args.version_name} in {project_key} project")

def handle_cleanup_command(manager: JiraVersionManager, args: argparse.Namespace) -> None:
    """Handle the cleanup command"""
    manager.logger.debug(f"Handling cleanup command with args: {args}")
    projects = args.project_keys.split(',') if args.project_keys else manager.config['project_keys']
    
    if args.dry_run:
        manager.logger.info("DRY RUN: The following versions would be removed:")
    
    # Get versions that would be removed
    removed = manager.cleanup_versions(args.project_keys, 
                                       hasattr(args, 'days') and args.days or 1, 
                                       hasattr(args, 'include_future') and args.include_future or False, 
                                       hasattr(args, 'include_released') and args.include_released or False, 
                                       args.dry_run,
                                       args.debug)
    
    if any(versions for versions in removed.values()):
        if not args.dry_run:
            manager.logger.info("Removed versions:")
        for project, versions in removed.items():
            if versions:
                manager.logger.info(f"\n{project}:")
                for version in versions:
                    manager.logger.info(f"  - {version}")
    else:
        manager.logger.warning("No versions would be removed." if args.dry_run else "No versions were removed.")

def handle_archive_command(manager: JiraVersionManager, args: argparse.Namespace) -> None:
    """Handle the archive command"""
    manager.logger.debug(f"Handling archive command with args: {args}")
    
    if args.dry_run:
        manager.logger.info("DRY RUN: The following versions would be archived:")
    
    # Get versions that would be archived
    archived = manager.archive_releases(
        args.project_keys, 
        hasattr(args, 'months') and args.months or 3, 
        args.dry_run, 
        args.debug)
    
    if any(versions for versions in archived.values()):
        if not args.dry_run:
            manager.logger.info("Archived versions:")
        for project, versions in archived.items():
            if versions:
                manager.logger.info(f"\n{project}:")
                for version in versions:
                    manager.logger.info(f"  - {version}")
    else:
        manager.logger.warning("No versions would be archived." if args.dry_run else "No versions were archived.")

def handle_maintenance_command(manager: JiraVersionManager, args: argparse.Namespace) -> None:
    """Handle the maintenance command"""
    manager.logger.debug(f"Handling maintenance command with args: {args}")

    projects = args.project_keys.split(',') if args.project_keys else manager.config['project_keys']
    for project_key in projects:
        manager.logger.info(f"Performing maintenance for project {project_key}")
        # Always perform:
        if args.dry_run:
            manager.logger.info("DRY RUN: The following versions would be reformatted:")
        manager.scanandfix_versions(project_key, args.dry_run, args.debug) # Scan and fix version formats
        if args.dry_run:
            manager.logger.info("DRY RUN: The following versions would be removed:")
        manager.cleanup_versions(
            project_key, 
            hasattr(args, 'days') and args.days or 1, 
            False, 
            hasattr(args, 'include_released') and args.include_released or False, 
            args.dry_run, 
            args.debug) # Remove old versions with no issues

        # Optional archive:
        if hasattr(args, 'archive_releases') and args.archive_releases:
            if args.dry_run:
                manager.logger.info("DRY RUN: The following versions would be archived:")
            manager.archive_releases(
                project_key, 
                hasattr(args, 'months') and args.months or 1, 
                args.dry_run, 
                args.debug)

        # Cleanup or create future versions:
        if hasattr(args, 'cleanup_future') and args.cleanup_future : # Remove future versions with no issues
            if args.dry_run:
                manager.logger.info("DRY RUN: The following versions would be removed:")
            manager.cleanup_versions(
                project_key, 
                hasattr(args, 'days') and args.days or 1, 
                True, 
                hasattr(args, 'include_released') and args.include_released or False, 
                args.dry_run, 
                args.debug)
            
        dates = manager.create_release_calendar(
            project_key,
            current_month=True, 
            next_month=True)
        
        for format_key in manager.get_project_version_formats(project_key):
            # Create versions for current and next month
            if args.dry_run:
                manager.logger.info("DRY RUN: The following versions would be created:")
            # Create versions for current month
            manager.create_versions_for_dates(
                project_key, 
                dates, 
                args.debug, 
                args.dry_run,
                format_key) 

def handle_scanandfix_command(manager: JiraVersionManager, args: argparse.Namespace) -> None:
    """Handle the scanandfix command to scan and fix version formats."""
    manager.logger.debug(f"Handling scanandfix command with args: {args}")

    if args.command:
        args.command = None
        handle_key_input('s', manager, args)
        return
    
    if args.dry_run:
        manager.logger.info("DRY RUN: The following versions would be reformatted:")
    
    projects = args.project_keys.split(',') if args.project_keys else manager.config['project_keys']

    for project_key in projects:
        results = manager.scanandfix_versions(project_key, args.dry_run, args.debug)
        if results:
            manager.logger.info(f"\n{project_key}:")
            for old_name, new_name in results:
                action = "Would rename" if args.dry_run else "Renamed"
                manager.logger.info(f"  - {action}: {old_name} -> {new_name}")
        else:
            manager.logger.warning(f"No version names need reformatting for {project_key}." if args.dry_run else f"No version names were reformatted for {project_key}.")

def format_output(data: Any, output_format: str = "text") -> str:
    """Format output data based on specified format.
    
    Args:
        data: Data to format.
        output_format: Output format (text, json, yaml).
        
    Returns:
        str: Formatted output string.
    """
    if output_format == "json":
        return json.dumps(data, indent=2)
    elif output_format == "yaml":
        return yaml.dump(data, default_flow_style=False)
    else:
        return str(data)
    
def clear_screen():
    """Clear the screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def main(args: Optional[List[str]] = None) -> int:
    """Main entry point for the CLI application"""
    parser = create_parser()
    args = parser.parse_args()

    try:
        # If --no-verify-ssl is used, it overrides config
        jira_verify_ssl = False if args.no_verify_ssl else None
        manager = JiraVersionManager(jira_verify_ssl=jira_verify_ssl)
        manager.logger.setLevel(logging.DEBUG if args.debug else logging.INFO)
        manager.parser = parser

        if hasattr(args, 'quiet') and args.quiet:  
            manager.logger.setLevel(logging.WARNING)

        command_handlers = {
            'config': handle_config_command,
            'list': handle_list_command,
            'create': handle_create_command,
            'delete': handle_delete_command,
            'cleanup': handle_cleanup_command,
            'archive': handle_archive_command,
            'maintenance': handle_maintenance_command,
            'scanandfix': handle_scanandfix_command
        }

        if args.command:
            result = command_handlers[args.command](manager, args)
            if result and args.format != "text":
                print(format_output(result, args.format))
        else:
            clear_screen()
            print_menu()
            
            while True:
                try:
                    # Use msvcrt on Windows for single key input
                    if os.name == 'nt':
                        import msvcrt
                        if msvcrt.kbhit():
                            try:
                                key = msvcrt.getch()
                                # Handle special keys (arrow keys, etc.)
                                if key in (b'\x00', b'\xe0'):  # Special key prefix
                                    msvcrt.getch()  # Consume the second byte
                                    continue
                                # Handle regular keys
                                key = key.decode('ascii', errors='ignore').lower()
                                if not handle_key_input(key, manager, args):
                                    break
                            except UnicodeDecodeError:
                                # Ignore any keys that can't be decoded
                                continue
                    # Use sys.stdin.read() for Unix-like systems            
                    else:
                        import sys, tty, termios
                        fd = sys.stdin.fileno()
                        old_settings = termios.tcgetattr(fd)
                        try:
                            tty.setraw(sys.stdin.fileno())
                            key = sys.stdin.read(1).lower()
                            if not handle_key_input(key, manager, args):
                                break
                        finally:
                            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                except Exception as e:
                    print(f"\nError reading input: {str(e)}")
                    break
                    
    except (ConfigurationError, JiraApiError, ConnectionError) as e:
        print(f"Error: {str(e)}")
        exit(1)
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        if args.debug:
            import traceback
            traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    main()
    os.system("pause")
