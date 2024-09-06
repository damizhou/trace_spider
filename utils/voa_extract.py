import json
import os
import scrapy
from trace_spider.items import ArticleItem, HeadItem, ImageItem, BodyItem  # 假设你将 Item 定义在 my_items 模块中
from datetime import datetime


# 递归转换scrapy.Item为字典
def item_to_dict(item):
    if isinstance(item, scrapy.Item):
        return {key: item_to_dict(value) for key, value in item.items()}
    elif isinstance(item, list):
        return [item_to_dict(element) for element in item]
    else:
        return item


def extract_from_voa(response):
    url = response.url
    # 创建存储数据的文件夹
    voa_data_folder = os.path.join(os.getcwd(), 'voa_data')
    if not os.path.exists(voa_data_folder):
        os.makedirs(voa_data_folder)

    processed_urls_file = os.path.join(voa_data_folder, 'processed_urls.txt')

    # 加载已处理的 URL
    if os.path.exists(processed_urls_file):
        with open(processed_urls_file, 'r', encoding='utf-8') as f:
            processed_urls = set(f.read().splitlines())
    else:
        processed_urls = set()

    if url in processed_urls:
        print(f"URL already processed, skipping: {url}")
        return False

    # 使用 XPath 提取 class 为 'hdr-container' 的 div 元素
    header = response.xpath('//div[@class="hdr-container"]')
    if header:  # 检查是否找到了匹配的元素
        title = header.xpath('.//h1[@class="title pg-title"]/text()').get().strip()
        time = header.xpath('.//span/time/text()').get().strip()
        # 提取头图信息
        headimg = header.xpath('//div[@class="img-wrap"]/div/img[@class=" enhanced"]')
        if headimg:
            headimgsrc = headimg.xpath('@src').get()
            headimgalt = headimg.xpath('@alt').get()
            # 创建 HeadItem 和 Head ImageItem
            head_image_item = ImageItem(img_src=headimgsrc, img_alt=headimgalt)
            head_item = HeadItem(title=title, head_img=head_image_item)

            category = response.xpath('//a[contains(@class, "category")]/text()').get().strip()

            # 提取文章主体
            body = response.xpath('//div[@class="body-container"]')
            if body:  # 检查是否找到了匹配的元素
                article_content = body.xpath('.//div[@id="article-content"]')

                # 提取文章内容文本
                p_elements = article_content.xpath('.//div[@class="wsw"]//p/text()').getall()
                article_content_texts = [p.strip() for p in p_elements if p.strip()]

                # 提取文章内容图片
                content_imgs = article_content.xpath('.//div[@class="wsw__embed"]//div[@class="thumb"]/img')
                article_content_imgs = []
                for content_img in content_imgs:
                    content_img_src = content_img.xpath('@src').get()
                    content_img_alt = content_img.xpath('@alt').get()
                    img_item = ImageItem(img_src=content_img_src, img_alt=content_img_alt)
                    article_content_imgs.append(img_item)

                # 创建 BodyItem
                body_item = BodyItem(article_content_texts=article_content_texts,
                                     article_content_imgs=article_content_imgs)
                # 创建 ArticleItem
                article_item = ArticleItem(head=head_item, body=body_item, time=time, url=url)

                # 将 ArticleItem 转换为字典
                article_item_dict = item_to_dict(article_item)
                article_item_dict["category"] = category

                # 根据当前日期生成文件名
                current_date = datetime.now().strftime('%Y%m%d')
                file_path = os.path.join(voa_data_folder, f'{current_date}_ova_articles.json')

                # 如果文件不存在，创建一个空数组文件
                if not os.path.exists(file_path):
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump([], f)

                # 读取已有的 JSON 文件并追加新的文章数据
                with open(file_path, 'r+', encoding='utf-8') as f:
                    articles = json.load(f)  # 读取现有数据
                    articles.append(article_item_dict)  # 添加新数据
                    f.seek(0)  # 将文件指针移动到文件开头
                    json.dump(articles, f, ensure_ascii=False, indent=4)  # 写回文件

                    # 将已处理的 URL 添加到文件中
                with open(processed_urls_file, 'a', encoding='utf-8') as f:
                    f.write(url + '\n')

                    # 将 URL 加入到已处理的 URL 集合中
                processed_urls.add(url)

    return True
