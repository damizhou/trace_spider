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
            self.file_path = 'current_docker_url_list.txt'
            self.urls = self.read_file()
            self._pcap_path = ''
            self.ssl_key_path = ''
            self.content_path = ''
            self.html_path = ''
            self.screenshot_path = ''
            self.requesturlNum = 0
            with open('./utils/running.json', 'r') as f:
                params = json.load(f)
                self.current_index = params['currentIndex']
            with open('exclude_keywords', 'r') as f:
                self.exclude_keywords = [s.replace('\n', ' ') for s in f.readlines()]
            self._initialized = True

    @property
    def pcap_path(self) -> str:
        return self._pcap_path

    @pcap_path.setter
    def pcap_path(self, pcap_path):
        if pcap_path in (None, ""):
            self._pcap_path = ""
            self.ssl_key_path = ""
            self.html_path = ""
            self.screenshot_path = ""
            return
        self._pcap_path = pcap_path
        self.ssl_key_path = rf"{pcap_path.replace('data', 'ssl_key').replace('.pcap', '_ssl_key.log')}"
        self.content_path = rf"{pcap_path.replace('data', 'content').replace('.pcap', '.txt')}"
        self.html_path = rf"{pcap_path.replace('data', 'html').replace('.pcap', '.html')}"
        self.screenshot_path = rf"{pcap_path.replace('data', 'screenshot').replace('.pcap', '.png')}"
        if len(os.path.dirname(self.ssl_key_path)) > 0:
            os.makedirs(os.path.dirname(self.ssl_key_path), exist_ok=True)

    def read_file(self):
        with open(self.file_path, 'r') as file:
            lines = file.readlines()
        urls = [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]
        return urls

    @property
    def current_start_url(self):
        current_start_url = 'https://' + self.urls[self.current_index]
        print('current_start_url', current_start_url)
        return current_start_url

    @property
    def current_allowed_domain(self):
        return self.urls[self.current_index]

task_instance = Task()