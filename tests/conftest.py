import pytest
import sys
import os
from unittest.mock import MagicMock, AsyncMock, patch

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@pytest.fixture(autouse=True, scope="session")
def mock_startup_dependencies():
    # Mock AsyncIOMotorClient
    mock_client = MagicMock()
    mock_client.admin.command = AsyncMock(return_value={"ok": 1})
    
    # Setup mock collections for any DB queries in routes/startup
    mock_db = MagicMock()
    mock_collection = AsyncMock()
    mock_cursor = MagicMock()
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.to_list = AsyncMock(return_value=[])
    mock_collection.find.return_value = mock_cursor
    mock_collection.find_one = AsyncMock(return_value=None)
    mock_collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id="mock_id"))
    mock_collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_collection.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))
    
    mock_db.__getitem__.return_value = mock_collection
    mock_db.get_collection.return_value = mock_collection
    mock_client.__getitem__.return_value = mock_db
    mock_client.get_database.return_value = mock_db

    # Mock requests.get for Ollama tag check
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"models": []}

    with patch("main.AsyncIOMotorClient", return_value=mock_client), \
         patch("main.requests.get", return_value=mock_response):
        yield
