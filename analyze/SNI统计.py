# 从pyshark库中导入filecapture类，该类用于从PCAP文件中读取数据包
from pyshark import FileCapture
import re
import csv
import os
import glob


# 消除转义序列函数
def eliminate_ANSI(tls_describe):
    # 移除 ANSI 转义序列的正则表达式
    ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')    
    # 将提取到的移除ANSI转义序列
    clean_tls_describe = ansi_escape.sub('',f'{str(tls_describe)}\n')
    return clean_tls_describe

# 提取cipher_suite函数
def extract_sni(clean_tls_describe):
    # 提取 Cipher Suite的正则表达式
    server_name_list_length_pattern = r'Server Name list length:\s*(.*?)(?=\s{2,})'
    server_name_type_pattern = r'Server Name Type:\s*(.*?)(?=\s{2,})'
    server_name_len_pattern = r'Server Name length:\s*(.*?)(?=\s{2,})'
    server_name_pattern = r'Server Name:\s*(.*?)(?=\s{2,})'
    # 在干净的TLS描述中提取匹配cipher suite
    server_name_list_length_match = re.search(server_name_list_length_pattern, clean_tls_describe)
    server_name_type_match = re.search(server_name_type_pattern, clean_tls_describe)
    server_name_len_match = re.search(server_name_len_pattern, clean_tls_describe)
    server_name_match = re.search(server_name_pattern, clean_tls_describe)
    if server_name_list_length_match and server_name_type_match and server_name_len_match and server_name_match:
        server_name_list_length = server_name_list_length_match.group(1)
        server_name_type = server_name_type_match.group(1)
        server_name_len = server_name_len_match.group(1)
        server_name = server_name_match.group(1)
    return server_name_list_length, server_name_type, server_name_len, server_name

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

# 创建一个FileCapture对象读取pcap文件
capture = FileCapture(pcap_file_path)
# 初始化列表存放SNI信息
sni = []
for packet in capture: 
    # 检查包是否存在tls属性，如果存在且是TLS握手包，提取SNI信息
    if hasattr(packet, 'tls') and hasattr(packet.tls, 'handshake') and packet.tls.handshake == "Handshake Protocol: Client Hello": 
        # SNI信息在tls的值里面，属于是描述，所以还要另外在描述中提取出来
        tls_describe = packet.tls
        # 将tls_describe转换为字符，并消除转义字符
        clean_tls_describe = eliminate_ANSI(tls_describe)
        # 在干净的字符串中提取SNI信息
        server_name_list_length, server_name_type, server_name_len, server_name = extract_sni(clean_tls_describe)
        sni.append(server_name)

# 去除重复的sni地址
unique_sni = list(set(sni))    

# 打开一个名为 output.txt 的文件，以写入模式打开（'w'）
with open('sni.csv', 'w', newline='') as pcap_csvfile:
#     # 定义一个写入文件对象并写入第一行标题
    writer_pcap = csv.writer(pcap_csvfile)
    # writer_pcap.writerow(['order_num', 'server_name_list_len', 'server_name_type', 'server_name_len','server_name', 'src_ip', 'dst_ip'])
    writer_pcap.writerow(['order_num', 'server_name'])
    
    order_num = 0
    for sni in unique_sni:
        # each_packet = [order_num, server_name_list_length, server_name_type, server_name_len, server_name, packet.ip.src, packet.ip.dst]
        order_num += 1
        each_packet = [order_num, sni]
        writer_pcap.writerow(each_packet)
    
capture.close()
                                    



