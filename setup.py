from setuptools import setup, find_packages, Command
import subprocess
import sys
from pathlib import Path
from jira_version_manager import __version__, __author__, __email__

class PyInstallerCommand(Command):
    """Custom command to build with PyInstaller"""
    description = "Build executable using PyInstaller"
    user_options = [
        ('onefile', None, 'Create single file executable'),
        ('console', None, 'Create console application'),
    ]

    def initialize_options(self):
        self.onefile = True
        self.console = True

    def finalize_options(self):
        pass

    def run(self):
        cmd = ['pyinstaller']
        if self.onefile:
            cmd.append('--onefile')
        if self.console:
            cmd.append('--console')
        cmd.extend([
            '--name=jira-version-manager',
            'jira_version_manager/version_manager.py'
        ])
        subprocess.check_call(cmd)

class NuitkaCommand(Command):
    """Custom command to build with Nuitka"""
    description = "Build executable using Nuitka"
    user_options = [
        ('onefile', None, 'Create single file executable'),
        ('standalone', None, 'Create standalone executable'),
    ]

    def initialize_options(self):
        self.onefile = True
        self.standalone = True

    def finalize_options(self):
        pass

    def run(self):
        cmd = ['nuitka']
        if self.onefile:
            cmd.append('--onefile')
        if self.standalone:
            cmd.append('--standalone')
        cmd.extend([
            '--enable-plugin=anti-bloat,data-files,pkg-resources,appdirs',
            '--output-filename=jira-version-manager',
            'jira_version_manager/version_manager.py'
        ])
        subprocess.check_call(cmd)

def get_long_description():
    path = Path(__file__).parent / "README.md"
    return path.read_text(encoding="utf-8") if path.exists() else "No README.md found"

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
        'build': [
            'pyinstaller>=6.0.0',
            'nuitka>=2.0.0'
        ]
    },
    entry_points={
        'console_scripts': [
            'jira-version-manager=jira_version_manager.version_manager:main',
        ],
    },
    cmdclass={
        'pyinstaller': PyInstallerCommand,
        'nuitka': NuitkaCommand
    },
    author=__author__,
    author_email=__email__,
    description="A tool to manage Jira versions with support for custom formats and SSL verification",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    keywords="jira, version management, agile",
    url="https://github.com/jackalski/jira-version-manager",
    project_urls={
        "Source": "https://github.com/jackalski/jira-version-manager",
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Software Development :: Version Control",
    ],
    python_requires=">=3.8"
)