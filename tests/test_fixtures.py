"""Tests on correct fixtures"""

import pytest
import requests


def test_app_fixture(app):
    """app fixture is loaded"""
    assert app is not None
    assert app.config['TESTING']


def test_db_fixture(db):
    """db fixture is loaded"""
    assert db is not None


def test_session_fixture(db_session):
    """db_session fixture is loaded"""
    assert db_session is not None


@pytest.mark.filterwarnings('ignore::urllib3.exceptions.InsecureRequestWarning')
def test_api_spec_request(url):
    """Verify that the openapi.json API endpoint works"""
    response = requests.get(url + '/openapi.json', verify=False)
    assert response.status_code == 200
