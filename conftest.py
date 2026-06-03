# conftest.py
import os, pytest
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

pytest_plugins = ('pytest_asyncio',)


@pytest.fixture
def tmp_data(tmp_path):
    """Fixture that patches data directories to tmp_path."""
    return tmp_path
