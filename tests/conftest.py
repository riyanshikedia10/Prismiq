"""
Shared fixtures for the Prismiq test suite.
Tests that need Neo4j are marked with @pytest.mark.neo4j.
"""

import os
import sys
import pytest

# Ensure project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def pytest_addoption(parser):
    parser.addoption("--neo4j", action="store_true", default=False, help="Run tests that require Neo4j")


def pytest_configure(config):
    config.addinivalue_line("markers", "neo4j: test requires a running Neo4j instance")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--neo4j"):
        skip = pytest.mark.skip(reason="Need --neo4j flag to run")
        for item in items:
            if "neo4j" in item.keywords:
                item.add_marker(skip)


@pytest.fixture(scope="session")
def neo4j_driver():
    """Session-scoped Neo4j driver — only created when --neo4j is passed."""
    from kg.schema import get_driver, verify_connectivity
    driver = get_driver()
    verify_connectivity(driver)
    yield driver
    driver.close()
