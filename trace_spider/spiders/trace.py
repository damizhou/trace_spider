import scrapy
# 导入 logger 模块
from utils.task import task_instance


class TraceSpider(scrapy.Spider):
    name = "trace"
    allowed_domains = [task_instance.current_allowed_domain]
    start_urls = [task_instance.current_start_url]

    def parse(self, response):
        url_set_Str = response.body.decode('utf-8').split(' ')

        for link in url_set_Str:
            # 检查 URL 是否以 http 或 https 开头
            if link.startswith('http'):
                # 跟随提取的链接
                yield response.follow(link, self.parse)
                pass
