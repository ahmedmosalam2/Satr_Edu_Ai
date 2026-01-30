from src.helpers.config import get_settings

class BaseDataModel:
    def __init__(self,client:object):
        self.settings=get_settings()
        self.client=client
        self.db=self.client[self.settings.MONGODB_DATABASE]
        
