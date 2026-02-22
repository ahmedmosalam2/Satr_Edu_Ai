from src.helpers.config import get_settings,Settings
import os
import random
import string

class BaseController:
    def __init__(self):
        self.settings=get_settings()
      
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        self.base_path = os.path.join(project_root, "src", "assets", "files")
        print(f"Files will be saved in: {self.base_path}")

  
    
    def generate_random_string(self,length:int):
        return ''.join(random.choices(string.ascii_letters+string.digits,k=length))
    

    def get_database_path(self,dn_name:str):
        database_path=os.path.join(self.base_path,dn_name)

        if not os.path.exists(database_path):
            os.makedirs(database_path)
        return database_path