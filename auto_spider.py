import asyncio
import json
import re
import time
import threading
import paramiko
import os
from sever_info import servers_info
from utils.task import task_instance

CSV_PATH = r'github_fcr_monitor.csv'
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
    base_path = "github_trace_spider"

    sftp = None
    try:
        # 连接服务器
        client.connect(hostname, username=username, password=password)
        sftp = client.open_sftp()
        print(f"{hostname} 连接成功")

        # 清理旧容器与代码目录；用 || true 防止“空列表”造成脚本中断
        server_commands = [
            'docker stop $(docker ps -q -f "name=^github_trace_spider") || true',
            'docker rm -f $(docker ps -aq -f "name=^github_trace_spider") || true',
            f"echo '{password}' | sudo -S rm -rf {base_path}* spiderCode",
            'git clone --branch ssl_key_csv_github https://github.com/damizhou/trace_spider.git spiderCode',
            # 如需单独克隆 clash-for-linux，可在此追加一条 git clone
        ]
        for cmd in server_commands:
            async_exec_command(client, cmd, password)

        # 读取任务列表
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        if not all_lines:
            print("CSV 为空，跳过。")
            return
        header, lines = all_lines[0], all_lines[1:]
        n = len(lines)

        vpn_infos = server["vpn_infos"]
        m = len(vpn_infos)
        if m <= 0:
            raise ValueError("server['vpn_infos'] 不能为空")

        # 任务均匀切块
        q, r = divmod(n, m)
        print(f"任务总数: {n}，docker 数: {m} -> 前 {r} 个: {q+1} 条，其余 {m-r} 个: {q} 条")

        spider_commands = []
        offset = 0

        for i, vpn_info in enumerate(vpn_infos):
            docker_index = vpn_info["docker_index"]  # 保留你的命名规则
            container_name = f"{base_path}{docker_index}"

            # 初始化每个容器的挂载目录与容器本身
            init_docker_commands = [
                f"cp -r spiderCode {container_name}",
                f'docker run --volume ~/{container_name}:/app -e HOST_UID=$(id -u $USER) -e HOST_GID=$(id -g $USER) --privileged -itd --name {container_name} chuanzhoupan/trace_spider:250912 /bin/bash'
            ]
            for cmd in init_docker_commands:
                async_exec_command(client, cmd, password)

            # 组装 main 命令（保持你原来的参数与 key 名；注意 server["loaction"] 的拼写）
            main_command = f'docker exec {container_name} python /app/main.py {server["loaction"]} {server["os"]}'

            # VPN 配置
            if not vpn_info.get("vpn_yml_info"):
                main_command += "novpn"
            else:
                vcfg = vpn_info["vpn_yml_info"]

                # 将本地 clash 配置模板替换并上传到宿主对应目录（容器内 /app 挂载可见）
                local_tpl = "./clash/config.yaml"
                with open(local_tpl, "r", encoding="utf-8") as f:
                    yml_content = f.read()
                vpn_info_str = "- " + json.dumps(vcfg, ensure_ascii=False)
                pattern = r"- \{ name: 'vpnnodename'.*?\}"
                updated = re.sub(pattern, vpn_info_str, yml_content)
                updated = updated.replace("vpnnodename", vcfg["name"])
                upload_file = "./clash/upload_config.yaml"
                with open(upload_file, "w", encoding="utf-8") as f:
                    f.write(updated)

                remote_file = f"{container_name}/clash-for-linux/conf/config.yaml"
                async_upload_file(sftp, upload_file, remote_file)

                protocol = "udp" if vcfg.get("udp") else "tcp"
                main_command += f'{vcfg["name"]} {vcfg["type"]} {protocol}'

            spider_commands.append(main_command)

            # ====== 均匀切块：为第 i 个容器切一段相邻任务 ======
            size = q + 1 if i < r else q
            start, end = offset, offset + size
            offset = end  # 推进游标

            # 写入并上传当前容器的 URL 列表（空任务时只含表头）
            local_current_urls_path = f"{container_name}_url_list.csv"
            remote_current_urls_path = f"{container_name}/current_docker_url_list.csv"
            with open(local_current_urls_path, "w", encoding="utf-8") as f:
                f.write(header)
                for line in lines[start:end]:
                    f.write(line)

            print(
                f"{container_name}: 分配 {size} 条（[{start}, {end})），"
                f"目标: {remote_current_urls_path}"
            )

            async_upload_file(sftp, local_current_urls_path, remote_current_urls_path)
            os.remove(local_current_urls_path)

            # 关闭 offload
            async_exec_command(
                client,
                f"docker exec {container_name} ethtool -K eth0 tso off gso off gro off",
                password,
            )

        # （可选）一致性检查
        if n != 0:
            assert offset == n, f"切片游标不一致: offset={offset}, n={n}"

        # 并发启动爬虫
        threads = []
        for cmd in spider_commands:
            t = threading.Thread(target=run_command, args=(client, cmd))
            time.sleep(1)  # 轻微错峰
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

    except Exception as e:
        print(f"Error handling server {hostname}: {e}")
    finally:
        try:
            if sftp is not None:
                sftp.close()
        finally:
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
    time.sleep(5)

