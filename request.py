import time
import requests
from bs4 import BeautifulSoup
import json
import datetime
import base64
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

with open('organizations_detail_data.json', 'w', encoding='utf-8') as f:
    f.write("")  # 每个数据项单独一行

# 遍历每个URL
for i in range(100):
    gitstar_ranking_url = 'https://gitstar-ranking.com/organizations?page=' + str(i + 1)
    gitstar_ranking_response = requests.get(gitstar_ranking_url)

    # 如果请求成功（HTTP 200 OK），继续处理
    if gitstar_ranking_response.status_code == 200:
        soup = BeautifulSoup(gitstar_ranking_response.text, 'html.parser')

        # 提取用户资料的元素
        try:
            items = soup.find_all('a',class_="list-group-item paginated_item")
            for item in items:
                organization_name =  item.find('span', class_='hidden-xs hidden-sm').text.strip()
                fa_star = item.find('span', class_='stargazers_count pull-right').text.strip()
                rank = item.find('span', class_='name').text.strip().split('.')[0]
                # 定义用户名和密码
                username = 'Ov23liAiCROuDOTgDC57'
                password = '6cdfd527a5f55405a0eb197b1666e98bcd028dc1'

                # 将用户名和密码组合成字符串，并用Base64编码
                credentials = f'{username}:{password}'
                b64_credentials = base64.b64encode(credentials.encode()).decode()

                # 设置请求头
                headers = {'Authorization': f'Basic {b64_credentials}'}


                # GitHub 组织 API URL
                github_url = "https://api.github.com/orgs/" + organization_name
                # 创建一个会话对象
                session = requests.Session()

                # 设置重试策略
                retry_strategy = Retry(total=10,  # 总共重试 3 次
                    backoff_factor=2,  # 重试之间的等待时间倍数
                    status_forcelist=[500, 502, 503, 443],  # 针对哪些状态码重试
                )
                adapter = HTTPAdapter(max_retries=retry_strategy)
                session.mount("https://", adapter)

                try:
                    github_response = session.get(github_url, timeout=10, headers=headers)
                    github_response.raise_for_status()  # 检查请求是否成功


                    # 检查请求是否成功
                    if github_response.status_code == 200:
                        # 请求成功，打印返回的数据
                        data = github_response.json()  # 将返回的 JSON 数据转换为字典
                        is_verified = str(data.get('is_verified'))
                        html_url = data.get('html_url')
                        blog = data.get('blog')
                        organization_data = {'organization_name': organization_name, 'fa_star': fa_star, 'rank': rank,
                                             'is_verified': is_verified, 'html_url': html_url, 'blog': blog}
                        # 获取当前时间
                        current_time = datetime.datetime.now()

                        # 格式化并打印当前时间（年-月-日 时:分:秒）
                        formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
                        print(f'{formatted_time}:{organization_data}')

                        with open('organizations_detail_data.json', 'a', encoding='utf-8') as f:
                            json.dump(organization_data, f, ensure_ascii=False)
                            f.write("\n")  # 每个数据项单独一行

                        time.sleep(random.uniform(1.0, 5.0))
                    else:
                        # 请求失败，打印错误信息
                        print(f"Failed to retrieve data. Status code: {github_response.status_code}")
                        print("Response content:", github_response.text)
                except requests.exceptions.Timeout:
                    print("请求超时，请检查网络连接或增加超时时间。")
                except requests.exceptions.RequestException as e:
                    print(f"请求失败: {e}")
        except AttributeError as e:
            print(f"Error processing github requests error: {e}")
    else:
        print(f"Failed to retrieve {gitstar_ranking_url}, Status code: {gitstar_ranking_response.status_code}")

print("爬取数据结束, 数据已逐条保存到 'organizations_detail_output_data.json'.")
