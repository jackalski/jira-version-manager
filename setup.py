from setuptools import setup, find_packages
import os
import json

# Sample configuration that will be created
SAMPLE_CONFIG = {
    "jira_base_url": "https://your-jira-instance.com",
    "jira_api_token": "your-api-token",
    "project_keys": ["PROJECT1", "PROJECT2"],
    "version_formats": [
        "{}.W{:02d}.{}.{:02d}.{:02d}",
        "{}.INTAKE.W{:02d}.{}.{:02d}.{:02d}"
    ]
}

def create_sample_config():
    """Create sample configuration file if it doesn't exist"""
    config_file = os.path.expanduser("~/.jira_version_manager.json")
    if not os.path.exists(config_file):
        with open(config_file, 'w') as f:
            json.dump(SAMPLE_CONFIG, f, indent=4)
        print(f"Created sample configuration file at {config_file}")

setup(
    name="jira-version-manager",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        'requests>=2.25.0',
    ],
    extras_require={
        'dev': [
            'pytest>=7.0.0',
            'pytest-cov>=4.0.0',
            'mypy>=1.0.0',
            'flake8>=6.0.0',
            'black>=23.0.0',
            'build>=1.0.0',
            'twine>=4.0.0',
        ],
    },
    entry_points={
        'console_scripts': [
            'jira-version-manager=jira_version_manager.version_manager:main',
        ],
    },
    author="Piotr Szmitkowski",
    author_email="pszmitkowski@gmail.com",
    description="A tool to manage Jira versions",
    long_description=open('README.md').read() if os.path.exists('README.md') else '',
    long_description_content_type="text/markdown",
    url="https://github.com/pszmitkowski/jira-version-manager",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Office/Business",
    ],
    python_requires='>=3.8',
)

# Create sample configuration file during installation
if __name__ == "__main__":
    create_sample_config() 