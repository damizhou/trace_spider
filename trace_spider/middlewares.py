# Define here the models for your spider middleware
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/spider-middleware.html
import time
from scrapy import signals
from scrapy.http import HtmlResponse
from selenium.webdriver.common.by import By
from tools.math_tool import generate_normal_random
from utils.logger import logger
from utils.chrome import create_chrome_driver, scroll_to_bottom, add_cookies
import json
from utils.task import task_instance
import utils.archive as archive
from utils.save_page import save_page


class TraceSpiderSpiderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the spider middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_input(self, response, spider):
        # Called for each response that goes through the spider
        # middleware and into the spider.

        # Should return None or raise an exception.
        return None

    def process_spider_output(self, response, result, spider):
        # Called with the results returned from the Spider, after
        # it has processed the response.

        # Must return an iterable of Request, or item objects.
        for i in result:
            yield i

    def process_spider_exception(self, response, exception, spider):
        # Called when a spider or process_spider_input() method
        # (from other spider middleware) raises an exception.

        # Should return either None or an iterable of Request or item objects.
        pass

    def process_start_requests(self, start_requests, spider):
        # Called with the start requests of the spider, and works
        # similarly to the process_spider_output() method, except
        # that it doesn’t have a response associated.

        # Must return only requests (not items).
        for r in start_requests:
            yield r

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)


class TraceSpiderDownloaderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the downloader middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def __init__(self):
        logger.info(f"创建浏览器")
        self.browser = create_chrome_driver()
        if 'youtube' in task_instance.current_allowed_domain:
            self.browser.get('https://www.youtube.com/')
            # Retrieve all cookies
            add_cookies(self.browser)
            self.browser.get('https://www.youtube.com/')

    def __del__(self):
        logger.info(f"销毁浏览器")
        self.browser.close()

    def process_request(self, request, spider):
        # Called for each request that goes through the downloader
        # middleware.

        # Must either:
        # - return None: continue processing this request
        # - or return a Response object
        # - or return a Request object
        # - or raise IgnoreRequest: process_exception() methods of
        #   installed downloader middleware will be called
        # 打印页面内容
        logger.info(f"requestURL:{request.url}")
        task_instance.requesturlNum += 1
        self.browser.get(request.url)
        scroll_to_bottom(self.browser)
        if 'youtube' in task_instance.current_allowed_domain:
            if 'watch' in request.url:
                video_element = self.browser.find_element(By.TAG_NAME, "video")
                self.browser.execute_script("arguments[0].play();", video_element)
                video_duration = self.browser.execute_script("return arguments[0].duration;", video_element)
                print("视频总时长:", video_duration, "秒")
                current_time = 0
                i = 0
                while current_time < video_duration and current_time < 180 and i < 5:
                    i += 1
                    current_time = self.browser.execute_script("return arguments[0].currentTime;", video_element)
                    if current_time == 0:
                        self.browser.execute_script("arguments[0].play();", video_element)
                        time.sleep(20)
                    else:
                        time.sleep(40 + generate_normal_random())
                        scroll_to_bottom(self.browser)

                    print("当前播放时长:", current_time, "秒")

            with open('youtube_cookie.txt', 'w') as file:
                json.dump(self.browser.get_cookies(), file)
            return HtmlResponse(url=request.url, body=self.browser.page_source, encoding='utf-8', request=request)
        elif 'archive' in task_instance.current_allowed_domain:
            if 'details' not in request.url:
                url_set = archive.get_main_url(self.browser)
            else:
                url_set = archive.get_details_url(self.browser)
            combined_html = ' '.join(url_set)
            # 将字符串编码为字节类型
            combined_html_bytes = combined_html.encode('utf-8')
            return HtmlResponse(url=request.url, body=combined_html_bytes, encoding='utf-8', request=request)
        elif 'voanews' in task_instance.current_allowed_domain:
            save_page(driver=self.browser)
            return HtmlResponse(url=request.url, body=self.browser.page_source, encoding='utf-8', request=request)
        # elif 'douban' in task_instance.current_allowed_domain:
        #     save_page(driver=self.browser)
        #     return HtmlResponse(url=request.url, body=self.browser.page_source, encoding='utf-8', request=request)
        else:
            return HtmlResponse(url=request.url, body=self.browser.page_source, encoding='utf-8', request=request)

    def process_response(self, request, response, spider):
        # Called with the response returned from the downloader.

        # Must either;
        # - return a Response object
        # - return a Request object
        # - or raise IgnoreRequest
        return response

    def process_exception(self, request, exception, spider):
        # Called when a download handler or a process_request()
        # (from other downloader middleware) raises an exception.

        # Must either:
        # - return None: continue processing this exception
        # - return a Response object: stops process_exception() chain
        # - return a Request object: stops process_exception() chain
        pass

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)
