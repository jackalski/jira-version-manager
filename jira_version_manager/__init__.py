"""
Jira Version Manager - A tool to manage Jira versions with support for custom formats and SSL verification.
"""

from .version_manager import JiraVersionManager, JiraApiError, ConfigurationError

__version__ = "0.5.0"
__author__ = "Piotr Szmitkowski"
__email__ = "pszmitkowski@gmail.com"

__all__ = ["JiraVersionManager", "JiraApiError", "ConfigurationError"] 