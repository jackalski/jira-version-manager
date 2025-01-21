"""
Jira Version Manager - A tool to manage Jira versions
"""

from .version_manager import JiraVersionManager, JiraApiError, ConfigurationError

__version__ = "0.1.0"
__all__ = ["JiraVersionManager", "JiraApiError", "ConfigurationError"] 