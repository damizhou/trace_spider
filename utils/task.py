import os

import pandas as pd

class Task:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Task, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.urls = self.read_file()
            self.url_logger = None
            self._pcap_path = ''
            self.ssl_key_path = ''
            self.requesturlNum = 0
            self._initialized = True

    @property
    def pcap_path(self) -> str:
        return self._pcap_path

    @pcap_path.setter
    def pcap_path(self, pcap_path):
        if pcap_path in (None, ""):
            self._pcap_path = ""
            self.ssl_key_path = ""
            return
        self._pcap_path = pcap_path
        self.ssl_key_path = rf"{pcap_path.replace('data', 'ssl_keys').replace('.pcap', '_ssl_key.log')}"
        if len(os.path.dirname(self.ssl_key_path)) > 0:
            os.makedirs(os.path.dirname(self.ssl_key_path), exist_ok=True)

    def read_file(self):
        df = pd.read_csv(r'current_docker_url_list.csv', encoding="utf-8", sep=",")

        # 将 NaN 统一成 None，便于 json 序列化
        df = df.where(pd.notna(df), None)

        # 导出为 JSON 数组（list[dict]）
        records = df.to_dict(orient="records")
        return records

    @property
    def current_allowed_domain(self):
        return 'theguardian.com'




task_instance = Task()
