import json
import os


class Task:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Task, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.urls = []
            self.file_paths = []
            self.get_all_url_list()
            self.url_logger = None
            self.requesturlNum = 0
            with open('./utils/running.json', 'r') as f:
                params = json.load(f)
                self.current_index = params['currentIndex']
            with open('exclude_keywords', 'r') as f:
                self.exclude_keywords = [s.replace('\n', '') for s in f.readlines()]
            self._initialized = True

    def get_all_url_list(self):
        directory = r'./url_lists'
        all_files = os.listdir(directory)
        # 获取所有文件的完整路径
        file_paths = [os.path.join(directory, f) for f in all_files]
        self.urls = all_files
        self.file_paths = file_paths

    @property
    def current_start_url(self):
        url_str = self.urls[self.current_index]
        if '{' in url_str:
            url_dict = json.loads(url_str)
            return url_dict['start_urls']
        else:
            return r'https://' + self.urls[self.current_index]

    @property
    def current_allowed_domain(self):
        url_str = self.urls[self.current_index]
        if '{' in url_str:
            url_dict = json.loads(url_str)
            return url_dict['allowed_domains']
        else:
            return self.urls[self.current_index]


task_instance = Task()
