# Build the executable for MacOS
nuitka --standalone --onefile \
  --include-data-file=jira_version_manager/config.json=jira_version_manager/config.json \
  --follow-imports \
  --output-filename=jira-version-manager \
  jira_version_manager/version_manager.py