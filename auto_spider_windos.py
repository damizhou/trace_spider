import json
import shutil
import subprocess
import os
from ssl import create_default_context
# 修改文件的权限
def remove_readonly(func, path, excinfo):
    os.chmod(path, 0o777)  # 使文件可写
    func(path)

def create_docker_container(index, category, container_name, loacl_volume_mount):
    current_docker_url_path = os.path.join(loacl_volume_mount, 'current_docker_url_list.txt')
    with open(current_docker_url_path, 'w', encoding='utf-8') as file:
        for url in category["url_list"]:
            file.write(url + '\n')  # 每行写入一个 URL
    # 定义需要的参数
    volume_mount = f"{loacl_volume_mount}:/app"

    # 构建Docker命令
    command = ["docker", "run", "--volume", volume_mount, "--privileged", "-itd", "--name",
        container_name, "chuanzhoupan/trace_spider:0712", "/bin/bash"]
    subprocess.run(command, check=True)

    ethtool_command = ["docker", "exec", container_name, "ethtool", "-K", "eth0", "tso", "off", "gso", "off", "gro", "off"]
    subprocess.run(ethtool_command, check=True)

    start_command = ["docker", "exec", container_name, "python", "/app/main.py", "novpn", f"{category["category"]}"]
    subprocess.run(start_command, check=True)


if __name__ == "__main__":
    with open('category_urls.json', 'r', encoding='utf-8') as file:
        categorys = json.load(file)
    original_code_path = r"E:\Docker\Voacategory"
    # if os.path.exists(original_code_path):
    #     # 使用 shutil.rmtree 删除文件夹及其内容
    #     shutil.rmtree(original_code_path)
    #
    # git_command = ["git", "clone", "--branch", "voacategory", "https://github.com/damizhou/trace_spider.git", f"{original_code_path}"]
    # result = subprocess.run(git_command, check=True, text=True, capture_output=True)

    # 输出命令的标准输出
    # print(result.stdout)

    for index, category in enumerate(categorys):
        print(category["category"])
        print(category["url_list"][0])
        print(index)
        container_name = f'voa_spider{index}'
        dst = original_code_path.replace('Voacategory', container_name)
        if os.path.exists(dst):
            # 使用 shutil.rmtree 删除文件夹及其内容
            shutil.rmtree(dst, onerror=remove_readonly)
        shutil.copytree(original_code_path, dst)
        create_docker_container(index, category, container_name, dst)
        break

