# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class TraceSpiderItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    pass


class ImageItem(scrapy.Item):
    img_src = scrapy.Field()
    img_alt = scrapy.Field()


class HeadItem(scrapy.Item):
    title = scrapy.Field()  # 文本字段
    head_img = scrapy.Field()  # ImageItem对象


class BodyItem(scrapy.Item):
    article_content_texts = scrapy.Field()  # 字符串数组
    article_content_imgs = scrapy.Field()  # ImageItem数组


class ArticleItem(scrapy.Item):
    time = scrapy.Field()
    url = scrapy.Field()
    head = scrapy.Field()  # HeadItem对象
    body = scrapy.Field()  # BodyItem对象
