import os
import shutil
from typing import List

class FileStore:
    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self._create_storage_dir()

    def _create_storage_dir(self):
        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path)

    # Save content to a file
    def save(self, file_name: str, content: str):
        with open(os.path.join(self.storage_path, file_name), 'w') as f:
            f.write(content)

    # Load the content of a file
    def load(self, file_name: str) -> str:
        with open(os.path.join(self.storage_path, file_name), 'r') as f:
            return f.read()
        
    # Move a file from src_path to the storage directory
    def move(self, src_path: str):
        shutil.move(src_path, os.path.join(self.storage_path, os.path.split(src_path)[1]))

    # Delete a file
    def delete(self, file_name: str):
        os.remove(os.path.join(self.storage_path, file_name))

    # List all files in the storage directory
    def list_files(self) -> List[str]:
        return os.listdir(self.storage_path)