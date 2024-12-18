import scrapy
# 导入 logger 模块
from utils.task import task_instance
from urllib.parse import unquote


class TraceSpider(scrapy.Spider):
    name = "trace"
    allowed_domains = ["voachinese.com"]
    start_urls = [task_instance.current_start_url]

    # custom_settings = {
    #     'DEPTH_LIMIT': 1  # 设置爬取深度为 1
    # }

    def parse(self, response):
        return
