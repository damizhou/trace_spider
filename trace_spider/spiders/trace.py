import os

import scrapy
# 导入 logger 模块
from utils.task import task_instance
from utils.zh_wikipedia import extract_info_for_wikipedia, extract_wiki_url


class TraceSpider(scrapy.Spider):
    name = "trace"
    allowed_domains = [task_instance.current_allowed_domain]
    start_urls = task_instance.urls

    def parse(self, response, **kwargs):
        a_links = response.css('a::attr(href)').getall()
        for link in a_links:
            # 拼接相对 URL 为绝对 URL
            if '/datasets/' in link:
                full_url = response.urljoin(link)
                huggingface_data_folder = os.path.join(os.getcwd(), 'huggingface_data')
                if not os.path.exists(huggingface_data_folder):
                    os.makedirs(huggingface_data_folder)
                with open(os.path.join(huggingface_data_folder, f"huggingface_dataset_all_url_list_mostdownloads.txt"), "a", encoding="utf-8") as f:
                    f.write(full_url + "\n")
