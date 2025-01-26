import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from jira_version_manager.version_manager import JiraVersionManager, JiraApiError, ConfigurationError
import requests

@pytest.fixture
def manager():
    with patch.dict('os.environ', {
        'JIRA_BASE_URL': 'https://jira.example.com',
        'JIRA_API_TOKEN': 'test-token'
    }):
        return JiraVersionManager()

def test_init_configuration(manager):
    assert manager.config['jira_base_url'] == 'https://jira.example.com'
    assert manager.config['jira_api_token'] == 'test-token'
    assert manager.config['project_keys'] == ['TEST1', 'TEST2']
    assert len(manager.config['version_formats']) == 1

def test_init_missing_token():
    with pytest.raises(ConfigurationError, match="API token not configured"):
        JiraVersionManager()

def test_get_weekdays_for_next_month(manager):
    # Test with specific date
    date = "2024-02-01"
    weekdays = manager.get_weekdays_for_next_month(date)
    assert all(d.weekday() < 4 for d in weekdays)  # All days are Mon-Thu
    assert all(d.month == 2 for d in weekdays)  # All days are in February

def test_get_weekdays_invalid_date(manager):
    with pytest.raises(ValueError, match="Invalid date format"):
        manager.get_weekdays_for_next_month("invalid-date")

@patch('requests.post')
def test_create_version(mock_post, manager):
    mock_response = Mock()
    mock_response.status_code = 201
    mock_post.return_value = mock_response
    
    manager.create_version("TEST1", "1.0.0")
    
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert kwargs['json']['name'] == "1.0.0"
    assert kwargs['json']['project'] == "TEST1"

@patch('requests.get')
def test_list_versions(mock_get, manager):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"id": "1", "name": "1.0.0", "released": True},
        {"id": "2", "name": "1.0.1", "released": False}
    ]
    mock_get.return_value = mock_response
    
    versions = manager.list_versions("TEST1")
    
    assert len(versions) == 2
    assert versions[0]['name'] == "1.0.0"
    assert versions[1]['name'] == "1.0.1"

@patch('requests.delete')
def test_delete_version(mock_delete, manager):
    mock_response = Mock()
    mock_response.status_code = 204
    mock_delete.return_value = mock_response
    
    manager.delete_version("1")
    
    mock_delete.assert_called_once()
    
@patch('requests.get')
def test_get_version_by_name(mock_get, manager):
    mock_response = Mock()
    mock_response.json.return_value = [
        {"id": "1", "name": "1.0.0"},
        {"id": "2", "name": "1.0.1"}
    ]
    mock_get.return_value = mock_response
    
    version = manager.get_version_by_name("TEST1", "1.0.0")
    assert version['id'] == "1"
    assert version['name'] == "1.0.0"
    
    version = manager.get_version_by_name("TEST1", "nonexistent")
    assert version is None

@patch('requests.get')
def test_get_issues_for_version(mock_get, manager):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'issues': [
            {
                'key': 'TEST-1',
                'fields': {
                    'summary': 'Test issue 1',
                    'status': {'name': 'Open'}
                }
            },
            {
                'key': 'TEST-2',
                'fields': {
                    'summary': 'Test issue 2',
                    'status': {'name': 'In Progress'}
                }
            }
        ]
    }
    mock_get.return_value = mock_response
    
    issues = manager.get_issues_for_version("TEST1", "1.0.0")
    assert len(issues) == 2
    assert issues[0]['key'] == 'TEST-1'
    assert issues[1]['key'] == 'TEST-2'
    
    # Verify JQL query
    args, kwargs = mock_get.call_args
    assert 'jql' in kwargs['params']
    assert 'project = TEST1' in kwargs['params']['jql']
    assert 'fixVersion = "1.0.0"' in kwargs['params']['jql']

@patch('requests.get')
def test_get_issues_for_version_invalid_response(mock_get, manager):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'not_issues': []}  # Invalid response format
    mock_get.return_value = mock_response
    
    with pytest.raises(JiraApiError, match="Invalid response format"):
        manager.get_issues_for_version("TEST1", "1.0.0")

@patch('requests.get')
def test_check_version_exists_with_issues(mock_get, manager):
    # Mock version list response
    version_response = Mock()
    version_response.json.return_value = [
        {"id": "1", "name": "1.0.0"}
    ]
    
    # Mock issues response
    issues_response = Mock()
    issues_response.json.return_value = {
        'issues': [
            {
                'key': 'TEST-1',
                'fields': {
                    'summary': 'Test issue',
                    'status': {'name': 'Open'}
                }
            }
        ]
    }
    
    # Set up mock to return different responses
    mock_get.side_effect = [version_response, issues_response]
    
    exists, issues = manager.check_version_exists("TEST1", "1.0.0")
    assert exists is True
    assert len(issues) == 1
    assert issues[0]['key'] == 'TEST-1'

@patch('requests.get')
def test_check_version_exists_no_version(mock_get, manager):
    # Mock empty version list response
    version_response = Mock()
    version_response.json.return_value = []
    mock_get.return_value = version_response
    
    exists, issues = manager.check_version_exists("TEST1", "1.0.0")
    assert exists is False
    assert len(issues) == 0

@patch('requests.post')
@patch('requests.get')
def test_create_version_already_exists(mock_get, mock_post, manager):
    # Mock version exists response
    version_response = Mock()
    version_response.json.return_value = [
        {"id": "1", "name": "1.0.0"}
    ]
    
    # Mock issues response
    issues_response = Mock()
    issues_response.json.return_value = {
        'issues': [
            {
                'key': 'TEST-1',
                'fields': {
                    'summary': 'Test issue',
                    'status': {'name': 'Open'}
                }
            }
        ]
    }
    
    mock_get.side_effect = [version_response, issues_response]
    
    manager.create_version("TEST1", "1.0.0")
    
    # Verify that post was not called (version not created)
    mock_post.assert_not_called()

def test_init_ssl_verification_from_config():
    with patch.dict('os.environ', {
        'JIRA_BASE_URL': 'https://jira.example.com',
        'JIRA_API_TOKEN': 'test-token',
        'JIRA_PROJECT_KEYS': 'TEST1,TEST2',
        'JIRA_VERSION_FORMATS': '{}.W{:02d}.{}.{:02d}.{:02d}',
        'JIRA_VERIFY_SSL': 'false'
    }):
        manager = JiraVersionManager()
        assert manager.verify_ssl is False

def test_init_ssl_verification_from_parameter():
    with patch.dict('os.environ', {
        'JIRA_BASE_URL': 'https://jira.example.com',
        'JIRA_API_TOKEN': 'test-token',
        'JIRA_PROJECT_KEYS': 'TEST1,TEST2',
        'JIRA_VERSION_FORMATS': '{}.W{:02d}.{}.{:02d}.{:02d}',
        'JIRA_VERIFY_SSL': 'true'
    }):
        manager = JiraVersionManager(verify_ssl=False)
        assert manager.verify_ssl is False

@patch('requests.request')
def test_make_request_with_ssl_verification(mock_request):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_request.return_value = mock_response
    
    manager = JiraVersionManager(verify_ssl=False)
    manager._make_request('GET', 'https://example.com')
    
    args, kwargs = mock_request.call_args
    assert kwargs['verify'] is False

@patch('requests.request')
def test_make_request_with_ssl_verification_enabled(mock_request):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_request.return_value = mock_response
    
    manager = JiraVersionManager(verify_ssl=True)
    manager._make_request('GET', 'https://example.com')
    
    args, kwargs = mock_request.call_args
    assert kwargs['verify'] is True

@patch('requests.get')
@patch('requests.delete')
def test_cleanup_versions(mock_delete, mock_get, manager):
    # Mock version list response
    version_response = Mock()
    version_response.status_code = 200
    version_response.json.return_value = [
        {
            "id": "1",
            "name": "TEST1.W01.2024.01.01",  # Old version
            "released": False
        },
        {
            "id": "2",
            "name": "TEST1.W12.2024.03.21",  # Recent version
            "released": False
        },
        {
            "id": "3",
            "name": "TEST1.W01.2024.01.01",  # Old version with issues
            "released": False
        },
        {
            "id": "4",
            "name": "TEST1.W01.2024.01.01",  # Old released version
            "released": True
        }
    ]
    
    # Mock issues response for versions
    def mock_issues_response(*args, **kwargs):
        issues_response = Mock()
        issues_response.status_code = 200
        
        # Return issues only for version 3
        if 'fixVersion = "TEST1.W01.2024.01.01"' in kwargs['params']['jql']:
            version_id = next((v['id'] for v in version_response.json.return_value 
                             if v['name'] == "TEST1.W01.2024.01.01" and v['id'] == "3"), None)
            if version_id:
                issues_response.json.return_value = {
                    'issues': [{'key': 'TEST-1'}]
                }
            else:
                issues_response.json.return_value = {'issues': []}
        else:
            issues_response.json.return_value = {'issues': []}
        return issues_response
    
    mock_get.side_effect = [version_response] + [mock_issues_response() for _ in range(4)]
    
    # Mock successful deletion
    mock_delete.return_value = Mock(status_code=204)
    
    # Test cleanup without including released versions
    removed = manager.cleanup_versions("TEST1", include_released=False)
    assert len(removed) == 1
    assert "TEST1.W01.2024.01.01" in removed  # Only the old version without issues
    assert mock_delete.call_count == 1
    
    # Reset mocks
    mock_delete.reset_mock()
    mock_get.reset_mock()
    mock_get.side_effect = [version_response] + [mock_issues_response() for _ in range(4)]
    
    # Test cleanup including released versions
    removed = manager.cleanup_versions("TEST1", include_released=True)
    assert len(removed) == 2  # Both old versions without issues (including released)
    assert mock_delete.call_count == 2

@patch('requests.get')
def test_cleanup_versions_invalid_format(mock_get, manager):
    # Mock version list response with invalid format
    version_response = Mock()
    version_response.status_code = 200
    version_response.json.return_value = [
        {
            "id": "1",
            "name": "INVALID_FORMAT",
            "released": False
        }
    ]
    
    mock_get.return_value = version_response
    
    # Test cleanup with invalid format
    removed = manager.cleanup_versions("TEST1")
    assert len(removed) == 0  # Should skip invalid format versions 

@patch('requests.get')
@patch('requests.delete')
def test_cleanup_versions_all_projects(mock_delete, mock_get, manager):
    # Mock version list response for multiple projects
    def mock_version_list(project):
        response = Mock()
        response.status_code = 200
        response.json.return_value = [
            {
                "id": f"{project}_1",
                "name": f"{project}.W01.2024.01.01",  # Old version
                "released": False
            },
            {
                "id": f"{project}_2",
                "name": f"{project}.W12.2024.03.21",  # Recent version
                "released": False
            }
        ]
        return response
    
    # Mock issues response (no issues)
    issues_response = Mock()
    issues_response.status_code = 200
    issues_response.json.return_value = {'issues': []}
    
    # Set up mock responses for both projects
    mock_get.side_effect = [
        mock_version_list("TEST1"),  # First project versions
        issues_response,  # First project old version issues
        issues_response,  # First project recent version issues
        mock_version_list("TEST2"),  # Second project versions
        issues_response,  # Second project old version issues
        issues_response,  # Second project recent version issues
    ]
    
    # Mock successful deletion
    mock_delete.return_value = Mock(status_code=204)
    
    # Test cleanup without project key (should clean all projects)
    removed = manager.cleanup_versions(include_released=False)
    
    # Verify results
    assert "TEST1" in removed
    assert "TEST2" in removed
    assert len(removed["TEST1"]) == 1  # Only old version removed
    assert len(removed["TEST2"]) == 1  # Only old version removed
    assert "TEST1.W01.2024.01.01" in removed["TEST1"]
    assert "TEST2.W01.2024.01.01" in removed["TEST2"]
    assert mock_delete.call_count == 2  # One version removed from each project

@patch('requests.get')
@patch('requests.delete')
def test_cleanup_versions_single_project(mock_delete, mock_get, manager):
    # Mock version list response
    version_response = Mock()
    version_response.status_code = 200
    version_response.json.return_value = [
        {
            "id": "1",
            "name": "TEST1.W01.2024.01.01",  # Old version
            "released": False
        },
        {
            "id": "2",
            "name": "TEST1.W12.2024.03.21",  # Recent version
            "released": False
        },
        {
            "id": "3",
            "name": "TEST1.W01.2024.01.01",  # Old version with issues
            "released": False
        },
        {
            "id": "4",
            "name": "TEST1.W01.2024.01.01",  # Old released version
            "released": True
        }
    ]
    
    # Mock issues response for versions
    def mock_issues_response(*args, **kwargs):
        issues_response = Mock()
        issues_response.status_code = 200
        
        # Return issues only for version 3
        if 'fixVersion = "TEST1.W01.2024.01.01"' in kwargs['params']['jql']:
            version_id = next((v['id'] for v in version_response.json.return_value 
                             if v['name'] == "TEST1.W01.2024.01.01" and v['id'] == "3"), None)
            if version_id:
                issues_response.json.return_value = {
                    'issues': [{'key': 'TEST-1'}]
                }
            else:
                issues_response.json.return_value = {'issues': []}
        else:
            issues_response.json.return_value = {'issues': []}
        return issues_response
    
    mock_get.side_effect = [version_response] + [mock_issues_response() for _ in range(4)]
    
    # Mock successful deletion
    mock_delete.return_value = Mock(status_code=204)
    
    # Test cleanup for single project
    removed = manager.cleanup_versions("TEST1", include_released=False)
    
    # Verify results
    assert "TEST1" in removed
    assert len(removed["TEST1"]) == 1
    assert "TEST1.W01.2024.01.01" in removed["TEST1"]
    assert mock_delete.call_count == 1 

@patch('requests.get')
@patch('requests.put')
def test_archive_releases(mock_put, mock_get, manager):
    # Mock version list response for multiple projects
    def mock_version_list(project):
        response = Mock()
        response.status_code = 200
        response.json.return_value = [
            {
                "id": f"{project}_1",
                "name": f"{project}.W01.2024.01.01",  # Old version
                "released": True,
                "description": f"{project} description"
            },
            {
                "id": f"{project}_2",
                "name": f"{project}.W12.2024.03.21",  # Recent version
                "released": True
            }
        ]
        return response
    
    # Set up mock responses for both projects
    mock_get.side_effect = [mock_version_list("TEST1"), mock_version_list("TEST2")]
    mock_put.return_value = Mock(status_code=200)
    
    # Override archive settings for testing
    manager.config['archive_settings'] = {
        'default': {'months': 3, 'enabled': True},
        'TEST1': {'months': 6, 'enabled': True},
        'TEST2': {'months': 1, 'enabled': False}
    }
    
    # Test archive without project key (all projects)
    archived = manager.archive_releases()
    
    # Verify results
    assert "TEST1" in archived and "TEST2" in archived
    assert len(archived["TEST1"]) == 1  # TEST1 has 6-month setting, so old version is not archived
    assert len(archived["TEST2"]) == 0  # TEST2 has archiving disabled
    assert mock_put.call_count == 1  # Only one version archived (TEST1)
    
    # Reset mocks
    mock_put.reset_mock()
    mock_get.reset_mock()
    mock_get.side_effect = [mock_version_list("TEST1")]
    
    # Test with explicit months parameter (should override project settings)
    archived = manager.archive_releases("TEST1", months=1)
    assert len(archived["TEST1"]) == 1  # Now the old version should be archived
    assert mock_put.call_count == 1  # One version archived

@patch('requests.get')
def test_archive_releases_invalid_format(mock_get, manager):
    # Mock version list response with invalid format
    version_response = Mock()
    version_response.status_code = 200
    version_response.json.return_value = [
        {
            "id": "1",
            "name": "INVALID_FORMAT",
            "released": True
        }
    ]
    
    mock_get.return_value = version_response
    
    # Test archive with invalid format
    archived = manager.archive_releases("TEST1")
    assert len(archived["TEST1"]) == 0  # Should skip invalid format versions

def test_parse_semantic_version():
    """Test parsing semantic version names"""
    manager = JiraVersionManager()
    
    # Test full version with pre-release and build
    parsed = manager.parse_semantic_version("1.2.3-alpha.1+b42")
    assert parsed['MAJOR'] == 1
    assert parsed['MINOR'] == 2
    assert parsed['PATCH'] == 3
    assert parsed['PRE_RELEASE'] == '-alpha.1'
    assert parsed['BUILD'] == '+b42'
    
    # Test version with pre-release only
    parsed = manager.parse_semantic_version("2.0.0-beta.2")
    assert parsed['MAJOR'] == 2
    assert parsed['MINOR'] == 0
    assert parsed['PATCH'] == 0
    assert parsed['PRE_RELEASE'] == '-beta.2'
    assert parsed['BUILD'] is None
    
    # Test version with build only
    parsed = manager.parse_semantic_version("1.2.3+b42")
    assert parsed['MAJOR'] == 1
    assert parsed['MINOR'] == 2
    assert parsed['PATCH'] == 3
    assert parsed['PRE_RELEASE'] is None
    assert parsed['BUILD'] == '+b42'
    
    # Test version with metadata
    parsed = manager.parse_semantic_version("1.2.3+sha.5114f85")
    assert parsed['MAJOR'] == 1
    assert parsed['MINOR'] == 2
    assert parsed['PATCH'] == 3
    assert parsed['METADATA'] == '+sha.5114f85'

def test_create_semantic_version():
    """Test creating semantic version names"""
    manager = JiraVersionManager()
    
    # Test full version with pre-release and build
    version = manager.create_semantic_version_name(
        "PROJECT1", "semantic",
        major=1, minor=2, patch=3,
        pre_release="alpha.1",
        build=42
    )
    assert version == "1.2.3-alpha.1+b42"
    
    # Test version with pre-release only
    version = manager.create_semantic_version_name(
        "PROJECT1", "semantic",
        major=2, minor=0, patch=0,
        pre_release="beta.2"
    )
    assert version == "2.0.0-beta.2"
    
    # Test version with build only
    version = manager.create_semantic_version_name(
        "PROJECT1", "semantic",
        major=1, minor=2, patch=3,
        build=42
    )
    assert version == "1.2.3+b42"
    
    # Test version with metadata
    version = manager.create_semantic_version_name(
        "PROJECT1", "semantic",
        major=1, minor=2, patch=3,
        metadata="+sha.5114f85"
    )
    assert version == "1.2.3+sha.5114f85"
    
    # Test project-specific semantic version
    version = manager.create_semantic_version_name(
        "PROJECT1", "semantic_project",
        major=1, minor=2, patch=3,
        pre_release="beta.1",
        build=42
    )
    assert version == "PROJECT1.1.2.3-beta.1+b42"

@patch('requests.request')
def test_get_latest_semantic_version(mock_request):
    """Test getting latest semantic version numbers"""
    manager = JiraVersionManager()
    
    # Mock version list response
    mock_request.return_value.json.return_value = [
        {'name': '1.0.0'},
        {'name': '1.1.0-alpha.1'},
        {'name': '1.1.0-alpha.2'},
        {'name': '1.1.0-beta.1+b42'},
        {'name': '1.1.0-rc.1'},
        {'name': '1.1.0'},
        {'name': '1.1.1+b43'}
    ]
    
    major, minor, patch, pre_release, build = manager.get_latest_semantic_version("PROJECT1", "semantic")
    assert major == 1
    assert minor == 1
    assert patch == 1
    assert pre_release is None
    assert build == 43

@patch('requests.request')
def test_create_next_pre_release(mock_request):
    """Test creating next pre-release version"""
    manager = JiraVersionManager()
    
    # Mock version list response
    mock_request.return_value.json.return_value = [
        {'name': '1.0.0-alpha.1'},
        {'name': '1.0.0-alpha.2'},
        {'name': '1.0.0-beta.1'}
    ]
    
    # Test creating next alpha version
    version = manager.create_version_name(
        "semantic", "PROJECT1",
        major=1, minor=0, patch=0,
        pre_release="alpha.3"
    )
    assert version == "1.0.0-alpha.3"
    
    # Test creating first beta version
    version = manager.create_version_name(
        "semantic", "PROJECT1",
        major=1, minor=0, patch=0,
        pre_release="beta.1"
    )
    assert version == "1.0.0-beta.1"

def test_create_release_calendar():
    """Test creating release calendar with various parameters"""
    manager = JiraVersionManager()
    
    # Test weekly frequency
    dates = manager.create_release_calendar(
        "TEST1",
        frequency="weekly",
        weekdays="0,2,4",  # Monday, Wednesday, Friday
        next_month=True,
        current_month=False
    )
    assert all(d.weekday() in [0, 2, 4] for d in dates)  # All dates are Mon/Wed/Fri
    
    # Test monthly frequency
    dates = manager.create_release_calendar(
        "TEST1",
        frequency="monthly",
        monthdays="1,15",  # 1st and 15th of month
        next_month=True
    )
    assert all(d.day in [1, 15] for d in dates)
    
    # Test interval
    dates = manager.create_release_calendar(
        "TEST1",
        interval=7,  # Every 7 days
        next_month=True
    )
    for i in range(len(dates) - 1):
        assert (dates[i+1] - dates[i]).days == 7
    
    # Test next working day adjustment
    dates = manager.create_release_calendar(
        "TEST1",
        weekdays="5,6",  # Saturday and Sunday
        next_working_day=True,
        next_month=True
    )
    assert all(d.weekday() < 5 for d in dates)  # All dates are weekdays

def test_create_release_calendar_invalid_weekdays():
    """Test creating release calendar with invalid weekdays"""
    manager = JiraVersionManager()
    
    with pytest.raises(ValueError, match="Weekdays must be between 0 and 6"):
        manager.create_release_calendar("TEST1", weekdays="7,8")

def test_create_release_calendar_current_and_next_month():
    """Test creating release calendar for current and next month"""
    manager = JiraVersionManager()
    
    dates = manager.create_release_calendar(
        "TEST1",
        current_month=True,
        next_month=True
    )
    
    today = datetime.now()
    next_month = today.replace(day=1) + timedelta(days=32)  # Simple way to get next month
    
    assert any(d.month == today.month for d in dates)  # Has dates in current month
    assert any(d.month == next_month.month for d in dates)  # Has dates in next month

def test_create_release_calendar_start_date():
    """Test that create_release_calendar uses today's date as start_date when none is provided"""
    manager = JiraVersionManager()
    today = datetime.now()
    
    # Test with no current_month flag (should start from today)
    dates = manager.create_release_calendar(
        "TEST1",
        frequency="weekly",
        weekdays="0,1,2,3",  # Monday-Thursday
        next_month=True
    )
    
    # First date should not be before today
    assert min(dates) >= today.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Test with current_month flag (should start from first day of month)
    dates = manager.create_release_calendar(
        "TEST1",
        frequency="weekly",
        weekdays="0,1,2,3",  # Monday-Thursday
        current_month=True
    )
    
    # First date should be in current month
    first_date = min(dates)
    assert first_date.year == today.year
    assert first_date.month == today.month
    assert first_date.day >= 1  # Should start from beginning of month

@patch('requests.request')
def test_make_request_connection_error(mock_request, manager):
    """Test handling of connection errors in _make_request"""
    mock_request.side_effect = requests.exceptions.ConnectionError("No network")
    
    with pytest.raises(JiraApiError, match="Permanent connection failure"):
        manager._make_request('GET', 'https://jira.example.com/rest/api/2/serverInfo')

@patch('requests.request')
def test_make_request_retry_success(mock_request, manager):
    """Test retry logic with eventual success"""
    mock_request.side_effect = [
        requests.exceptions.ConnectionError("Temporary failure"),
        requests.exceptions.ConnectionError("Temporary failure"), 
        Mock(status_code=200)
    ]
    
    response = manager._make_request('GET', 'https://jira.example.com')
    assert response.status_code == 200
    assert mock_request.call_count == 3

@patch('requests.request')
def test_make_request_ssl_error(mock_request, manager):
    """Test SSL error handling with guidance"""
    mock_request.side_effect = requests.exceptions.SSLError("Certificate error")
    
    with pytest.raises(JiraApiError, match="SSL verification failed"):
        manager._make_request('GET', 'https://jira.example.com')

@patch('requests.head')
def test_pre_flight_connectivity_check(mock_head, manager):
    """Test pre-flight connectivity check failure"""
    mock_head.side_effect = requests.exceptions.ConnectionError("DNS failure")
    
    with pytest.raises(JiraApiError, match="No network connection to Jira"):
        manager._make_request('GET', 'https://jira.example.com')

@patch('requests.request')
def test_make_request_timeout_handling(mock_request, manager):
    """Test separate handling of connection vs response timeouts"""
    mock_request.side_effect = requests.exceptions.Timeout("Connection timed out")
    
    with pytest.raises(JiraApiError, match="timed out after"):
        manager._make_request('GET', 'https://jira.example.com')