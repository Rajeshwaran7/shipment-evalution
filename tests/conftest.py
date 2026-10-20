"""Pytest configuration and fixtures. Enforces offline MockLLM during test suites."""

import os
import pytest

# Ensure all tests run offline with MockLLM
os.environ["LLM_PROVIDER"] = "mock"

