import scrapy
# 导入 logger 模块
from utils.logger import logger
from utils.config import config
from utils.task import task_instance


class TraceSpider(scrapy.Spider):
    name = "trace"
    allowed_domains = [task_instance.current_allowed_domain]
    start_urls = [task_instance.current_start_url]

    def parse(self, response):
        # 打印页面内容
        logger.info(f"responseURL:{response.url}")
        # logger.info(response.text)

        # 提取页面中的链接
        links = response.css('a::attr(href)').getall()
        for link in links:
            # 拼接相对 URL 为绝对 URL
            full_url = response.urljoin(link)

            if "http" in full_url:
                # 跟随提取的链接
                yield response.follow(full_url, self.parse)
