"""Shared test setup.

Tests must never call a real LLM. Setting LLM_PROVIDER=off here, before any test module
imports `app`, wins over a developer's .env (load_settings uses override=False). Tests that
need an LLM inject an LLMClient backed by httpx.MockTransport instead.
"""

import os

os.environ["LLM_PROVIDER"] = "off"
