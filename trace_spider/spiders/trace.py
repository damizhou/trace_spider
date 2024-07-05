import scrapy
# 导入 logger 模块
from utils.task import task_instance


class TraceSpider(scrapy.Spider):
    name = "trace"
    allowed_domains = [task_instance.current_allowed_domain]
    start_urls = [task_instance.current_start_url]

    def parse(self, response):
        # logger.info(response.text)
        # 提取页面中的链接
        a_links = response.css('a::attr(href)').getall()
        link_tags = response.css('link::attr(href)').getall()
        links = a_links + link_tags
        for link in links:
            # 拼接相对 URL 为绝对 URL
            full_url = response.urljoin(link)

            # 检查 URL 是否以 http 或 https 开头
            if full_url.startswith('http'):
                # 跟随提取的链接
                yield response.follow(full_url, self.parse)
