import asyncio
import json
import re
import time
import threading
import paramiko
import os
import math
from sever_info import servers_info
TASK_LIST_PATH = f'test.csv'
index = 0
# 异步执行并监控命令输出
def async_exec_command(client, command, password):
    print(f"{command}")
    stdin, stdout, stderr = client.exec_command(command)

    while not stdout.channel.exit_status_ready():
        # 逐行读取输出
        line = stdout.readline()
        if line:
            print(f"{line.strip()}")
        time.sleep(1)  # 异步等待，避免阻塞

    # 读取剩余的输出
    err = stderr.read().decode()
    if err:
        print(f"{err}")


def run_command(ssh, command):
    print(command)
    stdin, stdout, stderr = ssh.exec_command(command)
    print(stdout.read().decode())
    print(stderr.read().decode())


# 异步上传文件
def async_upload_file(sftp, local_file, remote_file):
    if os.path.exists(local_file):
        sftp.put(local_file, remote_file)
        print(f"File '{local_file}' successfully uploaded to '{remote_file}'")
    else:
        print(f"Warning: Local file '{local_file}' does not exist.")


# 在服务器上异步执行一系列命令
def handle_server(server):
    hostname = server["hostname"]
    password = os.environ.get('SERVER_PASSWORD', server["password"])
    username = os.environ.get('SERVER_USERNAME', server["username"])
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    base_path = f"trace_spider"
    try:
        # 连接服务器,并初始化服务器
        client.connect(hostname, username=username, password=password)
        sftp = client.open_sftp()
        print(f"{hostname}连接成功")
        # 执行 git clone 命令

        sever_commands = [
            f"docker stop $(docker ps -q -f \"name=^{base_path}\") | docker rm -f $(docker ps -aq -f \"name=^{base_path}\")",
            f"echo '{password}' | sudo -S rm -rf {base_path}* spiderCode",
            f"echo '{password}' | sudo -S ethtool -K docker0 tso off gso off gro off",
            f'git clone --branch novpn https://github.com/damizhou/trace_spider.git spiderCode',
        ]
        for sever_command in sever_commands:
            async_exec_command(client, sever_command, password)
        spider_commands = []  # 用于存储异步任务的列表

        # 获取务列表,并计算每个docker的任务数量
        with open(f"{TASK_LIST_PATH}", 'r', encoding='utf-8') as file:
            lines = file.readlines()
        each_docker_task_count = math.ceil(len(lines) / len(server["vpn_infos"]))
        print(f"每个docker需要处理的URL数量：{each_docker_task_count}")
        print("len(lines)", len(lines))
        current_index = 0
        # 初始化docker
        for vpn_info in server["vpn_infos"]:
            if each_docker_task_count == 1:
                current_index += 1
                if current_index > len(lines):
                    break
            docker_index = vpn_info["docker_index"]
            container_name = base_path + str(docker_index)
            init_docker_commands = [
                f'cp -r spiderCode {container_name}',
            ]
            docker_run_command = (f'docker run --volume ~/{container_name}:/app -e HOST_UID=$(id -u $USER) '
                                  f'-e HOST_GID=$(id -g $USER) --privileged -itd --name {container_name} '
                                  f'chuanzhoupan/trace_spider:250912 /bin/bash')

            main_commmand = f'docker exec {container_name} python /app/main.py {server["loaction"]} {server["os"]} '
            init_docker_commands.append(docker_run_command)

            for init_docker_command in init_docker_commands:
                async_exec_command(client, init_docker_command, password)

            main_commmand += f'novpn'
            spider_commands.append(main_commmand)

            # 拆分任务列表,并上传到对应的docker
            start_url_index = docker_index * each_docker_task_count
            end_url_index = start_url_index + each_docker_task_count
            local_current_urls_path = f'{container_name}_url_list.txt'
            remote_current_urls_path = f"{container_name}/current_docker_url_list.txt"
            with open(local_current_urls_path, 'w', encoding='utf-8') as file:
                for line in lines[start_url_index: end_url_index]:
                    file.write(f"{line.split(",")[1]}")
            # 上传任务列表到对应的docker
            async_upload_file(sftp, local_current_urls_path, remote_current_urls_path)
            async_exec_command(client, f'docker exec {container_name} ethtool -K eth0 tso off gso off gro off',
                               password)
            # 删除本地临时文件
            # os.remove(local_current_urls_path)
        # 创建线程列表
        threads = []

        # 启动线程
        for spider_command in spider_commands:
            thread = threading.Thread(target=run_command, args=(client, spider_command))
            time.sleep(1)
            thread.start()
            threads.append(thread)

        # 等待所有线程完成
        for thread in threads:
            thread.join()

    except Exception as e:
        print(f"Error handling server {hostname}: {e}")
    finally:
        sftp.close()
        client.close()


# 主函数：并行处理所有服务器
async def auto_main():
    # 创建线程列表
    sever_threads = []

    # 启动线程
    for server in servers_info:
        thread = threading.Thread(target=handle_server, args=(server,))
        thread.start()
        sever_threads.append(thread)

    # 等待所有线程完成
    for thread in sever_threads:
        thread.join()

def main():
    asyncio.run(auto_main())

if __name__ == "__main__":
    main()

