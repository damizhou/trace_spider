from scapy.all import rdpcap, IP
import csv
import glob
import os

# 获取当前工作目录
current_directory = os.getcwd()
# 使用glob.glob寻找当前目录中的第一个.pcapng文件
pcapng_files = glob.glob(os.path.join(current_directory, '*.pcapng'))
# 检查是否找到.pcapng文件
if pcapng_files:
    pcap_file_path = pcapng_files[0]  # 获取找到的第一个.pcapng文件的路径
    print(f"Found pcapng file: {pcap_file_path}")
else:
    print("No .pcapng files found in the directory.")
# 修改为你的PCAP文件路径
# pcap_file_path = 'googlevideo_20240511.pcap.pcapng'
# 修改为你想要保存的CSV文件路径
csv_file_path = 'inbound_packets_ip.csv'

# 读取PCAP文件
packets = rdpcap(pcap_file_path)

# 假设本地网络接口的IP地址是 '192.168.1.1'
# 请根据你的实际情况修改这个地址
# local_ip = '192.168.192.128'
local_ip = '192.168.137.237'

# 初始化列表来存储流入包的IP信息
inbound_ips = []

# 遍历PCAP文件中的每个包
for packet in packets:
    # 检查是否为IP包，并且目的IP是本地接口的IP
    if packet.haslayer(IP) and packet[IP].dst == local_ip:
        # 添加源IP到列表
        inbound_ips.append(packet[IP].src)

# 去除重复的IP地址
unique_inbound_ips = list(set(inbound_ips))

# 将IP信息写入CSV文件
with open(csv_file_path, 'w', newline='') as csvfile:
    csvwriter = csv.writer(csvfile)
    # 写入标题
    csvwriter.writerow(['Inbound Source IP'])
    # 写入唯一的流入包源IP地址
    for ip in unique_inbound_ips:
        csvwriter.writerow([ip])

print(f"Inbound packet IP information has been written to {csv_file_path}")