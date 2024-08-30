import json
import os
from datetime import datetime
from urllib.parse import urljoin
import scrapy
from trace_spider.items import WikiPageItem
import hashlib

from utils.task import task_instance


def hash_url(input_string):
    # 计算输入字符串的哈希值（使用SHA-256 算法）
    hash_object = hashlib.sha256(input_string.encode('utf-8'))
    hash_value = hash_object.hexdigest()

    # 返回哈希值
    return hash_value


def extract_info_for_wikipedia(response):
    # 标题
    title = response.xpath('//h1[@id="firstHeading"]/text()').get()

    # url
    url = response.url

    # 分类
    categories_div = response.xpath('//div[@id="mw-normal-catlinks"]//ul/li/a')
    categories = []
    for category in categories_div:
        text = category.xpath('.//text()').getall()
        text_combined_text = ' '.join(text).strip()
        categories.append(text_combined_text)

    # 简介
    info_box = response.xpath('//table[contains(@class, "infobox")]')
    info_box_list = []
    if info_box is not None:
        info_box_trs = info_box.xpath('.//tr')
        info_box_trs.xpath('.//style').remove()
        for tr in info_box_trs:
            img = tr.xpath('.//img')
            if tr.xpath('.//td[@colspan="2" and @class="infobox-image"]'):
                img = tr.xpath('.//img')
                img_src = img.xpath('@src').get()
                img_url = urljoin(response.url, img_src)
                img_alt = img.xpath('@alt').get()
                infobox_image = {'img': {"src": img_url, "alt": img_alt}}
                info_box_list.append(infobox_image)
            elif tr.xpath('.//th[@scope="row"]'):
                th = tr.xpath('.//th[@scope="row"]')[0]
                td = tr.xpath('.//td[@class="infobox-data"]')[0]
                # 提取标题
                label = th.xpath('.//text()').get().strip()
                # 提取数据
                data = td.xpath('.//text()').getall()
                data = ' '.join(data).strip()
                # 添加到内容列表
                info_box_list.append({'label': label, 'data': data})

    # 主体内容
    content = response.xpath('//*[@class="mw-content-ltr mw-parser-output"]')
    # 提取所有子节点
    child_nodes = content.xpath('* | ./*')
    content = []
    for child_node in child_nodes:

        # 清理<style>元素
        child_node.xpath('.//style').remove()
        # 获取节点的类型
        node_type = child_node.root.tag
        node_class = child_node.xpath('@class').get()
        if node_type == "style" or node_type == "meta":
            continue
        if node_type == "div":
            if not node_class:
                continue
            if child_node.xpath('@role').get() == "note":
                # 提取所有文本内容
                div_text_content = child_node.xpath('.//text()').getall()
                # 组合文本内容
                div_combined_text = ' '.join(div_text_content).strip()
                # print("div_combined_text", div_combined_text)
                content.append({'text': div_combined_text})
            if 'mw-heading' in node_class:
                # 提取所有文本内容
                heading_div_text_content = child_node.xpath('.//text()').getall()
                # 组合文本内容
                heading_div_combined_text = ' '.join(heading_div_text_content).strip().replace("[ 编辑 ]", "")
                # print('heading_div_combined_text', heading_div_combined_text)
                content.append({'text': heading_div_combined_text})

            if "reflist" in node_class or "refbegin" in node_class:
                references = child_node.xpath('.//ol/li')
                if not references:
                    references = child_node.xpath('.//ul/li')
                index = 1
                for reference in references:
                    ref = reference.xpath('.//text()').getall()
                    ref_combined_text = ' '.join(ref).strip()
                    index_text = fr"[{index}]"
                    content.append({'text': index_text + ref_combined_text})
                    index += 1
            if "thumb" in node_class:
                tsingles = child_node.xpath('.//div[@class="tsingle"]')
                # 遍历每个 .tsingle 元素并提取数据
                for tsingle in tsingles:
                    img_src = tsingle.xpath('.//img/@src').get()
                    caption = tsingle.xpath('.//div[@class="thumbcaption"]/text()').getall()
                    caption_combined_text = ' '.join(caption).strip()
                    content.append({'img': {
                        "src": response.urljoin(img_src),
                        "alt": caption_combined_text
                    }})
        elif node_type == "p":
            # 提取所有文本内容
            p_text_content = child_node.xpath('.//text()').getall()
            p_combined_text = ' '.join(p_text_content).strip()
            # print('p_combined_text', p_combined_text)
            content.append({'text': p_combined_text})
        elif node_type == "figure":
            if not node_class:
                continue
            if "mw-default-size" in node_class:
                image_element = child_node.xpath('.//img')
                figcaption = child_node.xpath('.//figcaption')
                img = {}
                if image_element:
                    image_src = image_element.xpath('@src').get()
                    img["src"] = response.urljoin(image_src)
                if figcaption:
                    image_alt = figcaption.xpath('.//text()').getall()
                    image_alt_combined_text = ' '.join(image_alt).strip()
                    img["alt"] = image_alt_combined_text
                content.append({'img': img})
        elif node_type == "ul":
            if node_class:
                if "gallery" in node_class:
                    li_nodes = child_node.xpath('.//li')
                    for li_node in li_nodes:
                        li_node_class = li_node.xpath('@class').get()
                        if li_node_class == "gallerycaption":
                            gallery_name = li_node.xpath('.//text()').getall()
                            gallery_name_combined_text = ' '.join(gallery_name).strip()
                            content.append({'text': gallery_name_combined_text})
                        elif li_node_class == "gallerybox":
                            image_element = li_node.xpath('.//img')
                            image_src = image_element.xpath('@src').get()
                            image_alt = image_element.xpath('@alt').get()
                            content.append({'img': {
                                "src": response.urljoin(image_src),
                                "alt": image_alt
                            }})
            else:
                li_nodes = child_node.xpath('.//li')
                for li in li_nodes:
                    li_text = li.xpath('.//text()').getall()
                    # 将列表中的所有文本片段连接起来，并去除多余的空白
                    li_combined_text = ''.join(li_text).strip()
                    # print('li_text_joined', li_combined_text)
                    content.append({'text': li_combined_text})
        elif node_type == "dl":
            dt_text = child_node.xpath('.//dt/text()').get()
            if dt_text:
                content.append({'text': dt_text})
            dd_text = child_node.xpath('.//dd//text()').getall()
            dd_text = ' '.join(dd_text).strip()
            if dd_text and len(dd_text) != 0:
                content.append({'text': dd_text})
        elif node_type == "blockquote":
            blockquote_text = child_node.xpath('.//text()').getall()
            blockquote_combined_text = ' '.join(blockquote_text).strip()
            if blockquote_combined_text:
                content.append({'text': blockquote_combined_text})

    url = response.url
    url_hash = hash_url(url)
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    item = {
        'title': title,
        'time': current_time,
        'url': url,
        'info_box': info_box_list,
        'content': content,
        'categories': categories
    }

    wikipedia_data_folder = os.path.join(os.getcwd(), 'wikipedia_data')
    if not os.path.exists(wikipedia_data_folder):
        os.makedirs(wikipedia_data_folder)
    file_path = os.path.join(wikipedia_data_folder, f'{url_hash}.json')

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(item, f, ensure_ascii=False)

    hash_results_file = os.path.join(wikipedia_data_folder, task_instance.current_allowed_domain + '_hash_file')

    with open(hash_results_file, 'a') as file:  # 使用 'a' 模式附加内容到文件中
        file.write(f"{url}SHA-256TO{url_hash}\n")


def extract_wiki_url(response):
    next_page_url = response.xpath('//div[@class="mw-allpages-nav"]/a/@href').getall()[-1]
    wiki_links = response.xpath('//div[@class="mw-allpages-body"]//ul[@class="mw-allpages-chunk"]/li/a/@href').getall()
    return wiki_links, next_page_url
