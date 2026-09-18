"""Pytest configuration and fixtures for binary_master."""

import pytest


@pytest.fixture(autouse=True)
def set_default_test_locale(monkeypatch):
    """Set default test environment locale to en_US.UTF-8.

    This ensures tests asserting default English output run consistently across all developer
    machines and CI environments regardless of the host system's locale.
    Tests specifically targeting Japanese output can set lang='ja' or override LANG to ja_JP.UTF-8.
    """
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    monkeypatch.setenv("LC_ALL", "en_US.UTF-8")
    monkeypatch.setenv("LC_MESSAGES", "en_US.UTF-8")
