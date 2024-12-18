import json
import subprocess
import os
from ssl import create_default_context

with open('category_urls.json', 'r', encoding='utf-8') as file:
    categorys = json.load(file)

git_command = ["git", "clone", "--branch", "clash", "https://gitee.com/damizhou/trace_spider.git", "spiderCode"]
result = subprocess.run(git_command, check=True, text=True, capture_output=True)

# 输出命令的标准输出
print(result.stdout)

for index, category in enumerate(categorys):
    print(category["category"])
    print(category["url_list"][0])
    print(index)
    create_default_context(index, category)

def create_docker_container(index, category):
    # 定义需要的参数
    docker_image = "chuanzhoupan/trace_spider:0712"
    container_name = f"voa_spider{index}"
    volume_mount = "E:\\Study\\Code\\trace_spider:/app"

    # 构建Docker命令
    command = ["docker", "run", "--volume", volume_mount, "--privileged", "-itd", "--name",
        container_name, docker_image, "/bin/bash"]

    try:
        # 执行命令
        print(f"执行命令: {' '.join(command)}")
        subprocess.run(command, check=True)
        print(f"容器 {container_name} 创建并启动成功！")

    except subprocess.CalledProcessError as e:
        print(f"错误: {e}")
    except Exception as e:
        print(f"未知错误: {e}")


# if __name__ == "__main__":
#     create_docker_container()
