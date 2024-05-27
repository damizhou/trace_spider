import multiprocessing
import json
import os
import fcntl


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
            with open('./utils/running.json', 'r') as f:
                params = json.load(f)
                self.current_index = params['currentIndex']
            self._initialized = True

    def read_file(self):
        with open(self.file_path, 'r') as file:
            lines = file.readlines()
        urls = [line.strip() for line in lines]
        return urls

    @property
    def current_start_url(self):
        return self.urls[self.current_index]

    @property
    def current_allowed_domain(self):
        return self.urls[self.current_index].split("//")[-1]


# 单例实例
task_instance = Task()
