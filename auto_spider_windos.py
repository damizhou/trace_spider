import asyncio
import json
import shutil
import subprocess
import os


# 定义一个异步执行 `subprocess` 的辅助函数
async def run_subprocess(command):
    # 异步运行命令
    process = await asyncio.create_subprocess_exec(*command)
    await process.communicate()


async def create_docker_container(category, container_name, loacl_volume_mount):
    current_docker_url_path = os.path.join(loacl_volume_mount, 'current_docker_url_list.txt')
    with open(current_docker_url_path, 'w', encoding='utf-8') as file:
        for url in category["url_list"]:
            file.write(url + '\n')  # 每行写入一个 URL

    # 定义需要的参数
    volume_mount = f"{loacl_volume_mount}:/app"

    # 构建Docker命令
    command = ["docker", "run", "--volume", volume_mount, "--privileged", "-itd", "--name", container_name,
               "chuanzhoupan/trace_spider:0712", "/bin/bash"]
    await run_subprocess(command)

    ethtool_command = ["docker", "exec", container_name, "ethtool", "-K", "eth0", "tso", "off", "gso", "off", "gro",
                       "off"]
    await run_subprocess(ethtool_command)

    start_command = ["docker", "exec", container_name, "python", "/app/main.py", "bj", "windows10", "novpn",
                     f"{category['category']}"]
    await run_subprocess(start_command)


async def run_in_thread(index, category, container_name, dst):
    # 在异步环境中执行 Docker 容器创建任务
    await create_docker_container(category, container_name, dst)


async def main():
    with open('category_urls.json', 'r', encoding='utf-8') as file:
        categorys = json.load(file)
    original_code_path = r"E:\Docker\Voacategory"

    # 使用 asyncio 运行所有的异步任务
    tasks = []
    for index, category in enumerate(categorys):
        print(f"处理 {category['category']}...")
        container_name = f'voa_spider{index}'
        dst = original_code_path.replace('Voacategory', container_name)
        shutil.copytree(original_code_path, dst)
        tasks.append(run_in_thread(index, category, container_name, dst))

    # 执行所有的异步任务
    await asyncio.gather(*tasks)

    print("主线程继续执行其他任务")


if __name__ == "__main__":
    # 运行主协程
    asyncio.run(main())
