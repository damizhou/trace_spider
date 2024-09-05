# -*- coding: utf-8 -*-
# from scapy.all import *
# 将一个pcap包分成若干个pcap包
# 为了解决大pcap分隔慢的问题，使用hash + dic进行辅助定位

import os
import dpkt
from dpkt.utils import inet_to_str
from tqdm import tqdm
import json
from datetime import datetime
import glob
import collections
import csv
import traceback

# 获取当前时间
now = datetime.now()

datalink = 1


def getIP(datalink, pkt):
    IP = False
    if datalink == 1 or datalink == 239:  # ethernet frame
        IP = dpkt.ethernet.Ethernet(pkt).data
    # 是RAW_IP包，没有Ethernet层:
    elif datalink == 228 or datalink == 229 or datalink == 101:
        IP = dpkt.ip.IP(pkt)
        # dpkt.ip6.IP6
    else:
        print("不认识的链路层协议!!!!")
    return IP


def siyuanzu(ip, pro, pro_txt, oneway_stream, bi_stream, Statistic_type):
    global bi_flow_ip_count
    # 判断数据包四元组
    srcport = pro.sport
    dstport = pro.dport
    srcip = inet_to_str(ip.src)
    dstip = inet_to_str(ip.dst)
    siyuanzu1 = (
            srcip
            + "_"
            + str(srcport)
            + "_"
            + dstip
            + "_"
            + str(dstport)
            + "_"
            + pro_txt
    )
    siyuanzu2 = (
            dstip
            + "_"
            + str(dstport)
            + "_"
            + srcip
            + "_"
            + str(srcport)
            + "_"
            + pro_txt
    )
    if siyuanzu1 not in oneway_stream:
        oneway_stream[siyuanzu1] = Statistic_type
        if siyuanzu2 in oneway_stream:
            bi_stream[siyuanzu2] = Statistic_type
            # 统计ip数量最多的流
            if ((Statistic_type == 'UDP' or Statistic_type == 'TCP') and srcip != local_ip):
                bi_flow_ip_count[inet_to_str(ip.src)] += 1
    return bi_stream


def is_quic_packet(udp_data):
    if len(udp_data) < 1:
        return False

    first_byte = udp_data[0]

    # 检查第一个字节的最高位是否为1，这通常是QUIC数据包的特征
    if first_byte & 0b10000000 == 0:
        return False

    # 长包格式: 第一个字节最高位为1且第2,3,4字节包含版本号
    if len(udp_data) >= 6:
        version = udp_data[1:5]
        # 例如，检查是否为常见的QUIC版本号 (仅举例，实际应查阅具体版本号)
        common_versions = [b'\x00\x00\x00\x01', b'\x00\x00\x00\x02']
        if version in common_versions:
            return True

    # 短包格式: 第一个字节最高位为1，后续字节包含连接ID等
    # 这里可以进一步解析短包格式，根据需要进行更详细的检查

    return False


def flows_packets_count(file_name):
    oneway_tcpstream = {}
    bi_tcpstream = {}
    oneway_udpstream = {}
    bi_udpstream = {}
    oneway_tlsstream = {}
    bi_tlsstream = {}
    oneway_quicstream = {}
    bi_quicstream = {}
    f = open(file_name, "rb")
    try:
        pkts = dpkt.pcap.Reader(f)
    except ValueError:
        f.close()
        f = open(file_name, "rb")
        pkts = dpkt.pcapng.Reader(f)
    except Exception as e:
        print(f"打开{file_name}的过程中发生错误：{e}")
        f.close()
        return bi_udpstream
    global datalink
    datalink = pkts.datalink()
    try:
        for time, pkt in tqdm(pkts, desc="处理pcap文件"):
            ip = getIP(datalink, pkt)
            if not isinstance(ip, dpkt.ip.IP):
                print("不是IP层")
                continue
            pro = ip.data

            # 统计UDP流量
            if isinstance(ip.data, dpkt.udp.UDP):
                pro_txt = "UDP"
                Statistic_type = "UDP"
                global udp_packet_num
                udp_packet_num += 1
                bi_udpstream = siyuanzu(ip, pro, pro_txt, oneway_udpstream, bi_udpstream, Statistic_type)

                #  #判断是否为quic数据包
                udp = ip.data
                # 检查端口号是否为quic常用端口
                if udp.dport == 443 or udp.sport == 443:
                    # 尝试解析quic数据
                    if is_quic_packet(udp.data):
                        global quic_packet_num
                        quic_packet_num += 1
                        Statistic_type = "quic"
                        bi_quicstream = siyuanzu(ip, udp, pro_txt, oneway_quicstream, bi_quicstream, Statistic_type)
                    else:
                        print("这不是一个quic数据包或数据不完整")


            # 统计TCP流量
            elif isinstance(ip.data, dpkt.tcp.TCP):
                pro_txt = "TCP"
                Statistic_type = "TCP"
                global tcp_packet_num
                tcp_packet_num += 1
                bi_tcpstream = siyuanzu(ip, pro, pro_txt, oneway_tcpstream, bi_tcpstream, Statistic_type)

                # 判断是否为TLS数据包
                tcp = ip.data
                # 检查端口号是否为TLS常用端口
                if tcp.dport == 443 or tcp.sport == 443:
                    # 尝试解析TLS数据
                    try:
                        tls_records, bytes_used = dpkt.ssl.tls_multi_factory(tcp.data)
                        if tls_records:
                            global tls_packet_num
                            tls_packet_num += 1
                            Statistic_type = "TLS"
                            bi_tlsstream = siyuanzu(ip, tcp, pro_txt, oneway_tlsstream, bi_tlsstream, Statistic_type)
                            # 可以进一步分析tls对象来获取TLS数据包的详细信息
                    except dpkt.dpkt.NeedData:
                        # 解析TLS数据失败，这不是一个完整的TLS数据包或数据不完整
                        print("这不是一个完整的TLS数据包或数据不完整")
                    except dpkt.dpkt.UnpackError:
                        # 解析TLS数据失败，这不是一个TLS数据包
                        print("这不是一个TLS数据包")
                    except dpkt.ssl.SSL3Exception as e:
                        print(f"TLS版本错误: {e}")

            else:
                print("不是TCP或UDP协议")
                continue

    except dpkt.dpkt.NeedData:
        print(f"{file_name}PCAP capture is truncated, stopping processing...")
        traceback.print_exc()
    f.close()
    return len(bi_tcpstream), len(bi_udpstream), len(bi_tlsstream), len(bi_quicstream)


# 读取pcap文件
def pcap_file_path():
    # 获取当前工作目录
    current_directory = os.getcwd()
    # 使用glob.glob寻找当前目录中的第一个.pcapng文件
    pcapng_files = glob.glob(os.path.join(current_directory, '*.pcap'))
    # 检查是否找到.pcapng文件
    if pcapng_files:
        pcap_file_path = pcapng_files[0]  # 获取找到的第一个.pcapng文件的路径
        print(f"Found pcapng file: {pcap_file_path}")
    else:
        print("No .pcapng files found in the directory.")
    return pcap_file_path


if __name__ == "__main__":
    pcap_file = pcap_file_path()
    csv_output_path = 'flows_packets_statistics.csv'

    # 初始化packet数量
    all_packet_num = 0
    quic_packet_num = 0
    tcp_packet_num = 0
    tls_packet_num = 0
    udp_packet_num = 0
    # 文件种流的总数量
    all_flows_count = 0
    quic_bi_flows_count = 0
    tcp_bi_flows_count = 0
    tls_bi_flows_count = 0
    udp_bi_flows_count = 0
    # 创建字典，统计每个ip的流数量
    bi_flow_ip_count = collections.defaultdict(int)
    # 本地ip
    local_ip = '192.168.192.128'

    tcp_bi_flows_count, udp_bi_flows_count, tls_bi_flows_count, quic_bi_flows_count = flows_packets_count(pcap_file)
    all_flows_count = tcp_bi_flows_count + udp_bi_flows_count
    all_packet_num = tcp_packet_num + udp_packet_num
    # 找出ip数量最多的流
    max_flow_ip = max(bi_flow_ip_count, key=bi_flow_ip_count.get)  # 找出字典中数量最多的IP
    max_flow_ip_percentage = (bi_flow_ip_count[max_flow_ip] / all_flows_count) * 100
    # print(tcp_bi_flows_count, tcp_packet_num, udp_bi_flows_count, udp_packet_num)

    for flow_ip, number in bi_flow_ip_count.items():
        print(f'ip: {flow_ip}, number: {number}')

    # 将统计结果写入CSV文件
    with open(csv_output_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        # 写入标题
        writer.writerow(['all_Flow Count', 'all_packet count', 'tcp_flow Count', 'tcp_Packet Count', 'tls_flow Count',
                         'tls_Packet Count', 'udp_flow Count', 'udp_Packet Count', 'quic_flow Count',
                         'quic_Packet Count', 'max_flow_ip', 'max_flow_ip_percentage(%)'])
        # 写入统计结果
        writer.writerow(
            [all_flows_count, all_packet_num, tcp_bi_flows_count, tcp_packet_num, tls_bi_flows_count, tls_packet_num,
             udp_bi_flows_count, udp_packet_num, quic_bi_flows_count, quic_packet_num, max_flow_ip,
             max_flow_ip_percentage])
        if os.getenv('HOST_UID') is not None:
            os.chown(csv_output_path, int(os.getenv('HOST_UID')), int(os.getenv('HOST_GID')))

    print(f'Statistics have been written to {csv_output_path}')

