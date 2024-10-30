import asyncio
import paramiko
import os
from sever_info import servers_info


# 异步执行并监控命令输出
async def async_exec_command(client, command):
    print(f"Executing: {command}")
    stdin, stdout, stderr = client.exec_command(command)

    while not stdout.channel.exit_status_ready():
        # 逐行读取输出
        line = stdout.readline()
        if line:
            print(f"Output: {line.strip()}")
        await asyncio.sleep(0.1)  # 异步等待，避免阻塞

    # 读取剩余的输出
    err = stderr.read().decode()
    if err:
        print(f"Error in command '{command}': {err}")


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
    local_file = "./clash/conf/config.yaml"
    remote_file = "/root/vpn_spider/clash/conf/config.yaml"

    commands = [
        'sudo apt update',
        'sudo apt install -y docker.io',
        'sudo ethtool -K docker0 tso off gso off gro off',
        'docker run --volume /root/vpn_spider:/app -e HOST_UID=$(id -u $USER) -e HOST_GID=$(id -g $USER) --privileged '
        '-d --name vpn_spider chuanzhoupan/trace_spider:0712 tail -f /dev/null',
        'docker exec vpn_spider ethtool -K eth0 tso off gso off gro off',
        'docker exec vpn_spider python /app/main.py'
    ]

    try:
        # 连接服务器
        client.connect(hostname, username='root', password=password)
        sftp = client.open_sftp()

        # 执行 git clone 命令
        clone_command = 'git clone --branch vpn https://github.com/damizhou/trace_spider.git vpn_spider'
        await async_exec_command(client, clone_command)

        # 上传本地文件到服务器
        await async_upload_file(sftp, local_file, remote_file)

        # 逐条执行命令
        for command in commands:
            await async_exec_command(client, command)

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
