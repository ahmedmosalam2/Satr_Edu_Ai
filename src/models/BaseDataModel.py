from src.helpers.config import get_settings

class BaseDataModel:
    def __init__(self, client: object = None):
        self.settings = get_settings()
        self.client = client
        # Only set db if client is provided (MongoDB connected)
        self.db = self.client[self.settings.MONGODB_DATABASE] if self.client is not None else None
        
