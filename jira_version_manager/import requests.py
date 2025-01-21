import requests
from datetime import datetime, timedelta
import calendar
import argparse
import os
import json
import sys

class JiraVersionManager:
    def __init__(self):
        # Default configuration
        self.config = {
            "jira_base_url": "https://your-jira-instance.com",
            "jira_api_token": "your-api-token",
            "project_keys": ["PROJECT1", "PROJECT2"],
            "version_formats": [
                "{}.W{:02d}.{}.{:02d}.{:02d}",
                "{}.INTAKE.W{:02d}.{}.{:02d}.{:02d}"
            ]
        }
        self.load_config()
        
        self.headers = {
            "Authorization": f"Bearer {self.config['jira_api_token']}",
            "Content-Type": "application/json"
        }
        
    def load_config(self):
        """Load configuration in order: file, environment, defaults"""
        # Try loading from config file
        config_file = os.path.expanduser("~/.jira_version_manager.json")
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    self.config.update(json.load(f))
            except Exception as e:
                print(f"Error loading config file: {e}")

        # Override with environment variables
        env_mapping = {
            "JIRA_BASE_URL": "jira_base_url",
            "JIRA_API_TOKEN": "jira_api_token",
            "JIRA_PROJECT_KEYS": "project_keys",
            "JIRA_VERSION_FORMATS": "version_formats"
        }
        
        for env_var, config_key in env_mapping.items():
            if os.getenv(env_var):
                if env_var in ["JIRA_PROJECT_KEYS", "JIRA_VERSION_FORMATS"]:
                    self.config[config_key] = os.getenv(env_var).split(',')
                else:
                    self.config[config_key] = os.getenv(env_var)

    def get_weekdays_for_next_month(self, start_date=None):
        """Get all Monday-Thursday dates starting from given date or next month"""
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

    def create_version(self, project_key, version_name, dry_run=False, debug=False):
        """Create a version in Jira project"""
        url = f"{self.config['jira_base_url']}/rest/api/2/version"
        payload = {
            "name": version_name,
            "project": project_key,
            "released": False
        }
        
        if debug:
            print(f"DEBUG: Creating version with payload: {payload}")
        
        if dry_run:
            print(f"DRY RUN: Would create version: {version_name}")
            return
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            print(f"Created version: {version_name}")
        except requests.exceptions.RequestException as e:
            print(f"Error creating version {version_name}: {str(e)}")

    def create_custom_version(self, project_key, date_str, debug=False, dry_run=False):
        """Create a version for a specific date"""
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
            week_num = date.isocalendar()[1]
            formatted_date = date.strftime("%Y.%m.%d")
            
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
            print(f"Error: Invalid date format. Please use YYYY-MM-DD. {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="Jira Version Manager")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--dry-run", action="store_true", help="Simulate version creation without actually creating them")
    parser.add_argument("--info", action="store_true", help="Display current configuration")
    parser.add_argument("--custom-version", nargs=2, metavar=('PROJECT_KEY', 'DATE'),
                       help="Create custom version for specific project and date (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    manager = JiraVersionManager()
    
    if args.info:
        print("Current Configuration:")
        for key, value in manager.config.items():
            print(f"{key}: {value}")
        return
    
    if args.custom_version:
        project_key, date_str = args.custom_version
        manager.create_custom_version(project_key, date_str, args.debug, args.dry_run)
        return
    
    # Default behavior: create versions for next month
    weekdays = manager.get_weekdays_for_next_month()
    
    for project_key in manager.config['project_keys']:
        for date in weekdays:
            week_num = date.isocalendar()[1]
            formatted_date = date.strftime("%Y.%m.%d")
            
            for version_format in manager.config['version_formats']:
                version_name = version_format.format(
                    project_key,
                    week_num,
                    date.year,
                    date.month,
                    date.day
                )
                manager.create_version(project_key, version_name, args.dry_run, args.debug)

if __name__ == "__main__":
    main()

