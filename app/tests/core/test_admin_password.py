"""Tests for admin password verification."""
import os
import pytest

from app.core.security import verify_admin_password
from app.core.settings import get_settings


def test_verify_admin_password_correct(monkeypatch):
    """Test admin password verification with correct password."""
    test_password = "test_admin_password_123"
    monkeypatch.setenv("ADMIN_PASSWORD", test_password)

    # Clear settings cache to pick up new env var
    get_settings.cache_clear()

    try:
        assert verify_admin_password(test_password) is True
    finally:
        get_settings.cache_clear()


def test_verify_admin_password_incorrect(monkeypatch):
    """Test admin password verification with wrong password."""
    monkeypatch.setenv("ADMIN_PASSWORD", "correct_password")

    get_settings.cache_clear()

    try:
        assert verify_admin_password("wrong_password") is False
    finally:
        get_settings.cache_clear()


def test_verify_admin_password_empty_string(monkeypatch):
    """Test admin password verification with empty string."""
    monkeypatch.setenv("ADMIN_PASSWORD", "actual_password")

    get_settings.cache_clear()

    try:
        assert verify_admin_password("") is False
    finally:
        get_settings.cache_clear()


def test_verify_admin_password_case_sensitive(monkeypatch):
    """Test that admin password is case-sensitive."""
    monkeypatch.setenv("ADMIN_PASSWORD", "SecretPassword")

    get_settings.cache_clear()

    try:
        assert verify_admin_password("SecretPassword") is True
        assert verify_admin_password("secretpassword") is False
        assert verify_admin_password("SECRETPASSWORD") is False
    finally:
        get_settings.cache_clear()
