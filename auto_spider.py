import asyncio
import json
import re
import time
import threading
import paramiko
import os
from sever_info import servers_info


# 异步执行并监控命令输出
async def async_exec_command(client, command):
    print(f"{command}")
    stdin, stdout, stderr = client.exec_command(command)

    while not stdout.channel.exit_status_ready():
        # 逐行读取输出
        line = stdout.readline()
        if line:
            print(f"{line.strip()}")
        await asyncio.sleep(0.1)  # 异步等待，避免阻塞

    # 读取剩余的输出
    err = stderr.read().decode()
    if err:
        print(f"{err}")


def run_command(ssh, command):
    stdin, stdout, stderr = ssh.exec_command(command)
    print(f"{command}")
    print(stdout.read().decode())
    print(stderr.read().decode())


# 异步上传文件
async def async_upload_file(sftp, local_file, remote_file):
    if os.path.exists(local_file):
        sftp.put(local_file, remote_file)
        print(f"File '{local_file}' successfully uploaded to '{remote_file}'")
    else:
        print(f"Warning: Local file '{local_file}' does not exist.")


# 在服务器上异步执行一系列命令
async def handle_server(server):
    hostname = server["hostname"]
    password = os.environ.get('SERVER_PASSWORD', server["password"])
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    each_docker_task_count = server["each_docker_task_count"]
    try:
        # 连接服务器,并初始化服务器
        client.connect(hostname, username='root', password=password)
        sftp = client.open_sftp()
        # 执行 git clone 命令
        sever_commands = [
            'sudo apt update',
            'sudo apt install -y docker.io',
            'sudo ethtool -K docker0 tso off gso off gro off',
        ]
        # for sever_command in sever_commands:
        #     await async_exec_command(client, sever_command)
        spider_commands = []  # 用于存储异步任务的列表
        # 初始化docker
        for docker_info in server["docker_infos"]:
            if docker_info["docker_index"] == 0:
                continue
            container_name = docker_info["docker_name"] + str(docker_info["docker_index"])
            docker_run_command = (f'docker run --volume /root/{container_name}:/app -e HOST_UID=$(id -u $USER) '
                                  f'-e HOST_GID=$(id -g $USER) --privileged -itd --name {container_name} '
                                  f'chuanzhoupan/trace_spider:0712 /bin/bash')
            init_docker_commands = [
                f'git clone --branch vpn https://github.com/damizhou/trace_spider.git {container_name}',
                f'git clone https://github.com/damizhou/clash-for-linux.git {container_name}/clash-for-linux',
                docker_run_command
            ]
            for init_docker_command in init_docker_commands:
                await async_exec_command(client, init_docker_command)

            time.sleep(5)
            await async_exec_command(client, f'docker exec {container_name} ethtool -K eth0 tso off gso off gro off')

            # 获取vpn配置
            vpn_info = docker_info["vpn_yml_info"]
            main_commmand = f'docker exec {container_name} python /app/main.py {server["loaction"]} {server["os"]}'

            # 拆分任务列表,并上传到对应的docker
            with open(f"url_list.txt", 'r') as file:
                lines = file.readlines()
            urls = [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]
            start_url_index = docker_info["docker_index"] * server["each_docker_task_count"]
            end_url_index = start_url_index + server["each_docker_task_count"]
            local_current_urls_path = f'current_docker_url_list.txt'
            remote_current_urls_path = f"/root/{container_name}/current_docker_url_list.txt"
            with open(local_current_urls_path, 'w') as file:
                for url in urls[start_url_index: end_url_index]:
                    file.write(f"{url}\n")

            await async_upload_file(sftp, local_current_urls_path, remote_current_urls_path)

            # 配置vpn
            if vpn_info:
                local_file = "./clash/config.yaml"
                vpn_info_str = '- ' + json.dumps(vpn_info)
                pattern = r"- \{ name: 'vpnnodename'.*?\}"
                with open(local_file, 'r', encoding='utf-8') as file:
                    yml_content = file.read()
                updated_yml_content = re.sub(pattern, vpn_info_str, yml_content)
                updated_yml_content = updated_yml_content.replace('vpnnodename', vpn_info['name'])
                # 将处理后的内容写入文件
                upload_file = "./clash/upload_config.yaml"
                with open(upload_file, 'w', encoding='utf-8') as file:
                    file.write(updated_yml_content)
                remote_file = f"/root/{container_name}/clash-for-linux/conf/config.yaml"
                # vpn配置上传到服务器
                await async_upload_file(sftp, upload_file, remote_file)

                if vpn_info["udp"]:
                    protocol = "udp"
                else:
                    protocol = "tcp"

                main_commmand += f'{docker_info["vpn_location"]} {vpn_info["type"]} {protocol}'
            else:
                main_commmand += f'novpn'

            # 开启爬虫命令
            # 收集任务而不是立即等待
            spider_commands.append(main_commmand)

        # 创建线程列表
        threads = []

        # 启动线程
        for spider_command in spider_commands:
            thread = threading.Thread(target=run_command, args=(client, spider_command))
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
async def main():
    tasks = [handle_server(server) for server in servers_info]
    await asyncio.gather(*tasks)


# 运行主程序
asyncio.run(main())
