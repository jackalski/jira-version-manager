from setuptools import setup, find_packages
import os
import json
from appdirs import user_data_dir
from jira_version_manager import __version__, __author__, __email__

def get_long_description():
    filename = os.path.join(os.path.dirname(__file__), "README.md")
    try:
        with open(filename, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return "No README.md file found"

setup(
    name="jira-version-manager",
    version=__version__,
    packages=find_packages(),
    install_requires=[
        "requests>=2.32.0",
        "urllib3>=2.0.0",
        "appdirs>=1.4.4"
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=24.0.0",
            "flake8>=6.0.0"
        ]
    },
    entry_points={
        "console_scripts": [
            "jira-version-manager=jira_version_manager.version_manager:main"
        ]
    },
    author=__author__,
    author_email=__email__,
    description="A tool to manage Jira versions with support for custom formats and SSL verification",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    keywords="jira, version management, agile",
    url="https://github.com/jackalski/jira-version-manager",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Software Development :: Version Control",
    ],
    python_requires=">=3.8"
)

if __name__ == "__main__":
    print("Hello")