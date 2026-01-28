from src.helpers.config import get_settings,Settings
import os
import random
import string

class BaseController:
    def __init__(self):
        self.settings=get_settings()
        self.base_path=os.path.join(os.getcwd(),"assets","files")
    
    def generate_random_string(self,length:int):
        return ''.join(random.choices(string.ascii_letters+string.digits,k=length))
