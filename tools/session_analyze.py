import os
import pyshark
import json


places = 3  # 保留4位小数

def normalize_five_tuple(src_ip, src_port, dst_ip, dst_port, protocol):
    """
    规范化五元组，使源IP/端口和目标IP/端口的顺序不影响会话判断
    """
    if (src_ip < dst_ip) or (src_ip == dst_ip and src_port < dst_port):
        return (src_ip, src_port, dst_ip, dst_port, protocol)
    else:
        return (dst_ip, dst_port, src_ip, src_port, protocol)

def extract_tcp_sessions(pcap_path):
    # 存储会话的字典，五元组为键，会话的第一个包的时间为值
    sessions = {}
    first_packet_time = None  # 用于存储整个PCAP的第一个包的时间
    results = []  # 用于存储所有会话的结果

    # 读取PCAP文件
    cap = pyshark.FileCapture(pcap_path, display_filter='tcp', keep_packets=False)  # 只处理TCP包，减少内存占用
    try:
        # 遍历所有数据包
        for packet in cap:
            # 检查是否是TCP包
            if 'IP' in packet and 'TCP' in packet:
                try:
                    # 获取整个PCAP的第一个包的时间
                    if first_packet_time is None:
                        first_packet_time = float(packet.sniff_time.timestamp())  # 获取第一个包的时间戳

                    # 提取源和目标信息
                    src_ip = packet.ip.src
                    dst_ip = packet.ip.dst
                    src_port = packet.tcp.srcport
                    dst_port = packet.tcp.dstport
                    protocol = packet.transport_layer

                    # 规范化五元组，使源IP、源端口和目标IP、目标端口顺序一致
                    normalized_five_tuple = normalize_five_tuple(src_ip, src_port, dst_ip, dst_port, protocol)

                    # 如果五元组第一次出现，则记录会话的第一个包时间戳
                    if normalized_five_tuple not in sessions:
                        session_time = float(packet.sniff_time.timestamp())  # 会话的时间戳
                        sessions[normalized_five_tuple] = {'first_packet_time': session_time,  # 会话的第一个包时间
                        }

                        # 计算当前包相对于整个PCAP的第一个包的时间
                        relative_time = float(packet.sniff_time.timestamp()) - first_packet_time

                        # 更新该会话的六元组信息
                        if places == 1:
                            sessions[normalized_five_tuple]['relative_time'] = int(relative_time)
                        else:
                            sessions[normalized_five_tuple]['relative_time'] = round(relative_time, places)  # 保留4位小数

                except AttributeError:
                    # 如果包中缺少必要的字段（例如某些包没有TCP层），跳过该包
                    continue
    finally:
        # 确保在完成捕获后关闭捕获进程
        cap.close()

    # 构建输出结果，转换为JSON格式
    for five_tuple, data in sessions.items():
        result = {'src_ip': five_tuple[0], 'src_port': five_tuple[1], 'dst_ip': five_tuple[2],
            'dst_port': five_tuple[3], 'protocol': five_tuple[4], 'rel_time': data['relative_time']}
        results.append(result)
    output_file = pcap_path.replace('.pcap', f'_sessions_0{places}.json')
    # 将结果写入指定的JSON文件
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=4)

    print(f"Results have been written to {output_file}")

def process_pcap_files_in_directory(directory_path):
    """
    遍历给定目录及其子目录，处理所有的 pcap 文件。
    """
    # 遍历目录及子目录
    for root, dirs, files in os.walk(directory_path):
        for file in files:
            # 检查文件是否为 pcap 文件
            if file.endswith('.pcap'):
                pcap_file_path = os.path.join(root, file)
                print(f'Processing: {pcap_file_path}')
                extract_tcp_sessions(pcap_file_path)  # 处理每个 pcap 文件

# 使用示例
# 指定目录路径
directory_path = r'E:\Study\Code\trace_spider\data'  # 替换为你要处理的目录路径
process_pcap_files_in_directory(directory_path)
