import scrapy
# 导入 logger 模块
from utils.logger import logger


class TraceSpider(scrapy.Spider):
    name = "trace"
    allowed_domains = ["douban.com"]
    start_urls = ["https://movie.douban.com/chart"]

    def parse(self, response):
        # 打印页面内容
        logger.info(f"Srart link:{response.url}")
        # logger.info(response.text)

        # 提取页面中的链接
        links = response.css('a::attr(href)').getall()
        for link in links:
            # 拼接相对 URL 为绝对 URL
            full_url = response.urljoin(link)

            if "http" in full_url:
                # 跟随提取的链接
                logger.info(f"Full URL:{full_url}")
                # yield response.follow(full_url, self.parse_link)

    def parse_link(self, response):
        # 打印跟随链接后的页面内容
        logger.info(f"Followed link:{response.url}")
        # logger.info(fresponse.text)
