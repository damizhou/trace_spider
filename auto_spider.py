import asyncio
import json
import re
import time
import threading
import paramiko
import os
from sever_info import servers_info

index = 0
# 异步执行并监控命令输出
def async_exec_command(client, command, password):
    print(f"{command}")
    stdin, stdout, stderr = client.exec_command(command)
    # if 'sudo' in command:
    #     stdin.write(f'{password}\n')
    #     stdin.flush()

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
    try:
        # 连接服务器,并初始化服务器
        client.connect(hostname, username=username, password=password)
        sftp = client.open_sftp()
        print(f"{hostname}连接成功")
        # 执行 git clone 命令

        # sever_commands = [
        #     f"echo '{password}' | sudo -S apt update",
        #     f"echo '{password}' | sudo -S apt install -y docker.io",
        #     f"docker stop $(docker ps -q)",
        #     f"docker rm -f $(docker ps -a -q)",
        #     f"echo '{password}' | sudo -S rm -rf trace_spider* spiderCode",
        #     f"echo '{password}' | sudo -S ethtool -K docker0 tso off gso off gro off",
        #     f'git clone --branch novpn https://github.com/damizhou/trace_spider.git spiderCode',
        #     f'git clone https://github.com/damizhou/clash-for-linux.git spiderCode/clash-for-linux',
        # ]
        # for sever_command in sever_commands:
        #     async_exec_command(client, sever_command, password)
        spider_commands = []  # 用于存储异步任务的列表
        # 初始化docker
        for vpn_info in server["vpn_infos"]:
            docker_index = vpn_info["docker_index"]
            container_name = server["docker_basename"] + str(docker_index)
            init_docker_commands = [
                f"rm -rf trace_spider*/data/20250122",
                f"echo '{password}' | sudo -S ethtool -K docker0 tso off gso off gro off",
                f'docker start {container_name}',
            ]
            # docker_run_command = (f'docker run --volume ~/{container_name}:/app -e HOST_UID=$(id -u $USER) '
            #                       f'-e HOST_GID=$(id -g $USER) --privileged -itd --name {container_name} '
            #                       f'chuanzhoupan/trace_spider:0712 /bin/bash')

            main_commmand = f'docker exec {container_name} python /app/main.py {server["loaction"]} {server["os"]} '
            # init_docker_commands.append(docker_run_command)

            for init_docker_command in init_docker_commands:
                async_exec_command(client, init_docker_command, password)

            time.sleep(5)
            async_exec_command(client, f'docker exec {container_name} ethtool -K eth0 tso off gso off gro off',
                               password)
            time.sleep(5)
            if vpn_info["vpn_yml_info"] == {}:
                main_commmand += f'novpn'
                spider_commands.append(main_commmand)
            else:
                # 获取vpn配置
                vpn_info = vpn_info["vpn_yml_info"]

                # 配置vpn
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
                remote_file = f"{container_name}/clash-for-linux/conf/config.yaml"
                # vpn配置上传到服务器
                async_upload_file(sftp, upload_file, remote_file)
                time.sleep(5)

                if vpn_info["udp"]:
                    protocol = "udp"
                else:
                    protocol = "tcp"

                main_commmand += f'{vpn_info["name"]} {vpn_info["type"]} {protocol}'

                # 开启爬虫命令
                # 收集任务而不是立即等待
                spider_commands.append(main_commmand)

            # # 拆分任务列表,并上传到对应的docker
            # with open(f"url_list.txt", 'r', encoding='utf-8') as file:
            #     lines = file.readlines()
            # urls = [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]
            # start_url_index = docker_index * server["each_docker_task_count"] % len(urls)
            # end_url_index = start_url_index + server["each_docker_task_count"]
            # local_current_urls_path = f'{container_name}_url_list.txt'
            # remote_current_urls_path = f"{container_name}/current_docker_url_list.txt"
            # with open(local_current_urls_path, 'w', encoding='utf-8') as file:
            #     for url in urls[start_url_index: end_url_index]:
            #         file.write(f"{url}\n")
            # print('local_current_urls_path', local_current_urls_path)
            # print('remote_current_urls_path', remote_current_urls_path)
            # # 上传任务列表到对应的docker
            # async_upload_file(sftp, local_current_urls_path, remote_current_urls_path)

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


# 运行主程序
asyncio.run(main())
