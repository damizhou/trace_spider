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
            self.file_path = 'url_list.txt'
            self.urls = self.read_file()
            self.requesturlNum = 0
            with open('./utils/running.json', 'r') as f:
                params = json.load(f)
                self.current_index = params['currentIndex']
            with open('exclude_keywords', 'r') as f:
                self.exclude_keywords = [s.replace('\n', ' ') for s in f.readlines()]
            self._initialized = True

    def read_file(self):
        # with open(self.file_path, 'r') as file:
        #     lines = file.readlines()
        # urls = [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]
        # return urls
        base_filename = 'wiki_url_list'
        index = 0
        all_need_spider_urls = []
        for i in range(15):
            wikipedia_data_folder = os.path.join(os.getcwd(), 'wikipedia_data')
            url_file_path = os.path.join(wikipedia_data_folder, f"{base_filename}_{index+i}.txt")
            with open(url_file_path, 'r') as file:
                urls = file.readlines()
                print('url_file_path', url_file_path)
                print("urls[-1]", urls[-1])
                print("urls[0]", urls[0])
                all_need_spider_urls.extend(urls)
        print("len(all_need_spider_urls)", len(all_need_spider_urls))
        print("all_need_spider_urls[-1]", all_need_spider_urls[-1])
        print("all_need_spider_urls[0]", all_need_spider_urls[0])
        return all_need_spider_urls

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
