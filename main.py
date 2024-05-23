from utils.logger import logger
from utils.config import config

import os
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from trace_spider.spiders.trace import TraceSpider


def print_directory_structure(startpath, prefix=""):
    for item in os.listdir(startpath):
        itempath = os.path.join(startpath, item)
        if os.path.isdir(itempath):
            print(f"{prefix}{item}/")
            print_directory_structure(itempath, prefix + "    ")
        else:
            print(f"{prefix}{item}")


# 启动爬虫
def start_spider():
    process = CrawlerProcess(get_project_settings())

    # 添加你要运行的爬虫
    process.crawl(TraceSpider)

    # 启动爬虫
    process.start()


def main():
    mode = config["spider"]["mode"]
    logger.info(f"开始捕获流量，模式{mode}")
    start_spider()


if __name__ == "__main__":
    main()
