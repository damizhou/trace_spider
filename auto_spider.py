import os
import paramiko
from sever_info import servers_info


def execute_commands(client, commands):
    for command in commands:
        try:
            stdin, stdout, stderr = client.exec_command(command)
            output = stdout.read()
            error = stderr.read()

            if output is not None:
                output = output.decode()
                print(f"Command: {command}")
                print("Output:")
                print(output)
            if error is not None:
                error = error.decode()
                print("Errors:")
                print(error)

            if output is None and error is None:
                print(f"Command: {command} did not produce any output.")

        except Exception as e:
            print(f"Error executing command {command}: {e}")


def upload_file(sftp, local_file, remote_file):
    try:
        sftp.put(local_file, remote_file)
        print(f"File '{local_file}' successfully uploaded to '{remote_file}'")
    except Exception as e:
        print(f"Error uploading file '{local_file}': {e}")


def main():
    for server in servers_info:
        # 服务器的 IP 地址或者域名
        hostname = server["hostname"]
        # 密码（考虑使用密钥对更安全）
        password = os.environ.get('SERVER_PASSWORD', server["password"])
        # 本地文件路径
        local_file = "./clash/conf/config.yaml"

        # 服务器上的目标文件路径
        remote_file = "/root/vpn_spider/clash/conf/config.yaml"

        # 创建 SSH 客户端
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            # 尝试连接服务器
            client.connect(hostname, username='root', password=password)

            # 创建 SFTP 客户端
            sftp = client.open_sftp()

            # 执行命令
            commands = [
                'sudo apt update',
                'sudo apt install -y docker.io',
                'sudo ethtool -K docker0 tso off gso off gro off',
                'git clone --branch vpn https://github.com/damizhou/trace_spider.git vpn_spider'
            ]

            execute_commands(client, commands)

            # 上传本地文件到服务器
            upload_file(sftp, local_file, remote_file)

        except Exception as e:
            print(f"Error connecting to or executing commands on {hostname}: {e}")
        finally:
            # 关闭 SFTP 连接
            if 'sftp' in locals():
                sftp.close()
            # 关闭 SSH 连接
            client.close()


if __name__ == "__main__":
    main()