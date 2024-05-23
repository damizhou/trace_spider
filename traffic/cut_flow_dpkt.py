# -*- coding: utf-8 -*-
# from scapy.all import *
# 将一个pcap包分成若干个pcap包
import os
import dpkt
from dpkt.utils import inet_to_str
from utils.logger import logger
from utils.config import config

datalink = 1


def getIP(datalink, pkt):
    IP = False
    if datalink == 1 or datalink == 239:  # ethernet frame
        IP = dpkt.ethernet.Ethernet(pkt).data
    # 是RAW_IP包，没有Ethernet层:
    elif datalink == 228 or datalink == 229 or datalink == 101:
        IP = dpkt.ip.IP(pkt)
    else:
        logger.error("不认识的链路层协议!!!!")
    return IP


def fenbao_and_restruct(file_name, tcpstream, flags, jieduan):
    # l = len(file_data)
    # data_list = [[] for _ in range(l)]
    # data_list=[[]]*l1  不能这样创建多维列表，会出问题，应该用上面的方式
    data_list = []

    f = open(file_name, "rb")
    try:
        pkts = dpkt.pcap.Reader(f)
    except ValueError:
        f.close()
        f = open(file_name, "rb")
        pkts = dpkt.pcapng.Reader(f)
    except Exception as e:
        logger.error(f"打开{file_name}的过程中发生错误：{e}")
        f.close()
        return data_list
    global datalink
    datalink = pkts.datalink()
    try:
        for time, pkt in pkts:
            ip = getIP(datalink, pkt)
            if not isinstance(ip, dpkt.ip.IP):
                logger.warn("不是IP层")
                continue
            if isinstance(ip.data, dpkt.udp.UDP):
                pro_txt = "UDP"
            elif isinstance(ip.data, dpkt.tcp.TCP):
                pro_txt = "TCP"
            else:
                logger.warn("不是TCP或UDP协议")
                continue
            pro = ip.data
            # 未知
            srcport = pro.sport
            dstport = pro.dport
            srcip = inet_to_str(ip.src)
            dstip = inet_to_str(ip.dst)
            siyuanzu1 = [srcip, srcport, dstip, dstport, pro_txt]
            siyuanzu2 = [dstip, dstport, srcip, srcport, pro_txt]
            if siyuanzu1 in tcpstream:
                j = tcpstream.index(siyuanzu1)
            elif siyuanzu2 in tcpstream:
                j = tcpstream.index(siyuanzu2)
            else:
                tcpstream.append(siyuanzu1)
                data_list.append([])
                j = len(tcpstream) - 1

            data_list[j].append((time, pkt))

    except dpkt.dpkt.NeedData:
        logger.info(f"{file_name}PCAP capture is truncated, stopping processing...")
    f.close()
    return data_list


def save_file(dir, data_list, tcpstream, flags, filename, deletetype, minlength):
    l = len(tcpstream)
    pcap_list = []
    for i in range(0, l):
        name = (
            f"{dir}/"
            + filename
            + "_"
            + str(tcpstream[i][4])
            + "_"
            + str(tcpstream[i][0])
            + "_"
            + str(tcpstream[i][1])
            + "_"
            + str(tcpstream[i][2])
            + "_"
            + str(tcpstream[i][3])
            + ".pcap"
        )
        with open(name, "wb") as f:
            writer = dpkt.pcap.Writer(f, linktype=datalink)
            writer.writepkts(data_list[i])
        pcap_list.append(name)
    return pcap_list


def cut(file_name, dir):
    """
    file_name：需要解包的pcap包
    dir：保存的路径
    """
    tcpstream = []
    flags = []
    jieduan = None
    # file_data = read_pcap(file_name)
    data = fenbao_and_restruct(file_name, tcpstream, flags, jieduan)
    namespace = file_name.split("/")
    pro = config["proxy"]["protocal"]
    args = pro + "_" + namespace[-1][:-5]
    deletetype = []
    minlength = 5
    os.makedirs(dir, exist_ok=True)
    pcap_list = save_file(dir, data, tcpstream, flags, args, deletetype, minlength)
    return pcap_list


if __name__ == "__main__":
    source = "/home/aimafan/Documents/mycode/handle_vps3_i2p/data/output.pcap"

    cut(source, "./test")
