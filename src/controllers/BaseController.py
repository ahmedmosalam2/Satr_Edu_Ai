from src.helpers.config import get_settings,Settings
import os
import random
import string

class BaseController:
    def __init__(self):
        self.settings=get_settings()
        # Fix: Ensure path points to src/assets/files relative to this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir)) # Go up from controllers -> src -> root
        self.base_path = os.path.join(project_root, "src", "assets", "files")
        print(f"📂 Files will be saved in: {self.base_path}")
    
    def generate_random_string(self,length:int):
        return ''.join(random.choices(string.ascii_letters+string.digits,k=length))
