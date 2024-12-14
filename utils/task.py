import json
import os

index = 0


class Task:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Task, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.file_path = 'url_list.txt'
            self.urls = self.read_file()
            self.requesturlNum = 0
            self.current_index = 0
            with open('exclude_keywords', 'r') as f:
                self.exclude_keywords = [s.replace('\n', ' ') for s in f.readlines()]
            self._initialized = True

    def read_file(self):
        with open(self.file_path, 'r') as file:
            lines = file.readlines()
        urls = [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]
        return urls

    @property
    def current_start_url(self):
        return self.urls[self.current_index]

    @property
    def current_allowed_domain(self):
        return 'huggingface.co'


task_instance = Task()
