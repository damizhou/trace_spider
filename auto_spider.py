import paramiko


def main():
    # 服务器的 IP 地址或者域名
    hostname = "your_server_ip"
    # 用户名
    username = "your_username"
    # 密码（考虑使用密钥对更安全）
    password = "your_password"

    # 创建 SSH 客户端
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        # 尝试连接服务器
        client.connect(hostname, username=username, password=password)

        # 执行命令
        commands = [
            'sudo apt update',
            'sudo apt install -y docker.io',
            'sudo ethtool -K docker0 tso off gso off gro off'
        ]

        for command in commands:
            stdin, stdout, stderr = client.exec_command(command)
            print(f"Command: {command}")
            print("Output:")
            print(stdout.read().decode())
            print("Errors:")
            print(stderr.read().decode())

    except Exception as e:
        print(e)
    finally:
        # 关闭连接
        client.close()


if __name__ == "__main__":
    main()