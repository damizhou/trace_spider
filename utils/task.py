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
            urls = []
            for i in range(100):
                # urls.append(
                #     f'https://huggingface.co/datasets?modality=modality:text&language=language:zh&p={i}&sort=trending')
                urls.append(
                    f'https://huggingface.co/datasets?p={i}&sort=downloads')
            self.urls = urls
            self.requesturlNum = 0
            self.current_index = 0
            with open('exclude_keywords', 'r') as f:
                self.exclude_keywords = [s.replace('\n', ' ') for s in f.readlines()]
            self._initialized = True

    def read_file(self):
        urls = []
        for i in range(99):
            urls.append(
                f'https://huggingface.co/datasets?sort=downloads')
        return urls

    @property
    def current_start_url(self):
        return self.urls[self.current_index]

    @property
    def current_allowed_domain(self):
        return 'huggingface.co'


task_instance = Task()
