import scrapy
# 导入 logger 模块
from utils.task import task_instance
from urllib.parse import unquote


class TraceSpider(scrapy.Spider):
    name = "trace"
    allowed_domains = [task_instance.current_allowed_domain]
    start_urls = [task_instance.current_start_url]

    # custom_settings = {
    #     'DEPTH_LIMIT': 1  # 设置爬取深度为 1
    # }

    def parse(self, response):
        a_links = response.css('a::attr(href)').getall()
        if len(a_links) == 0:
            print(f'{response.url} 没有提取到 URL')
        for link in a_links:
            # 拼接相对 URL 为绝对 URL
            full_url = response.urljoin(link)

            # 检查 URL 是否以 http 或 https 开头
            if full_url.startswith('http'):
                if 'analytics' in full_url and 'x.com' in full_url:
                    continue
                # 剔除类似登录注册页面
                if any(keyword in full_url for keyword in task_instance.exclude_keywords):
                    continue
                yield response.follow(full_url, self.parse)
