import scrapy
# 导入 logger 模块
from utils.task import task_instance
from utils.voa_extract import extract_from_voa


class TraceSpider(scrapy.Spider):
    name = "trace"
    allowed_domains = [task_instance.current_allowed_domain]
    start_urls = ["https://www.voachinese.com/a/why-is-beijing-interested-in-a-mid-level-government-aide-in-new-york-state-20240905/7773593.html"]

    def parse(self, response):
        if 'archive' in response.url:
            url_set_Str = response.body.decode('utf-8').split(' ')

            for link in url_set_Str:
                # 检查 URL 是否以 http 或 https 开头
                if link.startswith('http'):
                    # 跟随提取的链接
                    yield response.follow(link, self.parse)
        else:
            if r'www.voachinese.com/a' in response.url or r'voacantonese.com/a' in response.url:
                extract_from_voa(response)
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
