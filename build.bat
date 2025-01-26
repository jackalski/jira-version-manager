@echo off
chcp 65001 > nul
REM Build Windows executable using Nuitka
nuitka --standalone --onefile ^
  --follow-imports ^
  --output-filename=jira-version-manager.exe ^
  --windows-disable-console ^
  --lto=yes ^
  jira_version_manager\version_manager.py

pause