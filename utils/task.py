import json


class Task:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Task, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.file_path = 'current_docker_url_list.txt'
            self.urls = self.read_file()
            self.url_logger = None
            self.requesturlNum = 0
            with open('./utils/running.json', 'r') as f:
                params = json.load(f)
                self.current_index = params['currentIndex']
            with open('exclude_keywords', 'r') as f:
                self.exclude_keywords = [s.replace('\n', '') for s in f.readlines()]
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
        return "voachinese.com"


task_instance = Task()
