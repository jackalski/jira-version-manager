import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from jira_version_manager.version_manager import JiraVersionManager, JiraApiError, ConfigurationError

@pytest.fixture
def manager():
    with patch.dict('os.environ', {
        'JIRA_BASE_URL': 'https://jira.example.com',
        'JIRA_API_TOKEN': 'test-token',
        'JIRA_PROJECT_KEYS': 'TEST1,TEST2',
        'JIRA_VERSION_FORMATS': '{}.W{:02d}.{}.{:02d}.{:02d}'
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