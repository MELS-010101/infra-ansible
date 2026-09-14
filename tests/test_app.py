import pytest
import requests

BASE_URL = "http://localhost:8080"

def test_root_endpoint():
    """Главная страница должна отдавать 200 и JSON с app name"""
    response = requests.get(f"{BASE_URL}/")
    assert response.status_code == 200
    data = response.json()
    assert "app" in data
    assert "requests" in data
    assert "uptime" in data

def test_boom_endpoint():
    """Эндпоинт /boom должен отдавать 500"""
    response = requests.get(f"{BASE_URL}/boom")
    assert response.status_code == 500

def test_health_endpoint():
    """Эндпоинт /health должен отдавать 200"""
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200
