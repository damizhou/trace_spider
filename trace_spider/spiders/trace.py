import scrapy
# 导入 logger 模块
from utils.task import task_instance

class TraceSpider(scrapy.Spider):
    name = "trace"
    allowed_domains = [task_instance.current_allowed_domain]
    start_urls = task_instance.urls
    # start_urls = ["https://zh.wikipedia.org/wiki/Linux",
    #               "https://zh.wikipedia.org/wiki/Google_Chrome",
    #               "https://zh.wikipedia.org/wiki/Android"]
    # start_urls = ["https://zh.wikipedia.org/wiki/(1,1%27-%E5%8F%8C("
    #               "%E4%BA%8C%E8%8B%AF%E5%9F%BA%E8%86%A6)%E4%BA%8C%E8%8C%82%E9%93%81)%E4%BA%8C%E6%B0%AF%E5%8C%96%E9%92"
    #               "%AF"]

    def parse(self, response, **kwargs):
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
                # 跟随提取的链接
                yield response.follow(full_url, self.parse)
