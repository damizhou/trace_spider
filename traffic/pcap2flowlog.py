import dpkt
from dpkt.utils import inet_to_str
import csv
import sys
import os
from utils.logger import logger
from datetime import datetime
from utils.config import config


# 按照时间，将pcap转换为流日志
def pcap2flowlog_dpkt(filename, des_dir):
    if "TCP" in filename:
        protocal = "TCP"
    elif "UDP" in filename:
        protocal = "UDP"
    else:
        protocal = "TCP"
    os.makedirs(des_dir, exist_ok=True)
    result = read_pcap(filename, 99999, protocal)
    filtered_result = [[], [], []]
    if result is None:
        logger.warning(f"将 {filename} 转换为流日志失败")
        return False
    for i in range(len(result[0])):
        # if result[0][i] != 0:  # 如果长度不为 0
        filtered_result[0].append(result[0][i])
        filtered_result[1].append(result[1][i])
        filtered_result[2].append(result[2][i])
    if len(filtered_result[0]) <= 3:
        logger.warning(f"{filename} 中有负载的数据包小于等于3个，不进行转换 ")
        return False
    save_path = des_dir
    os.makedirs(save_path, exist_ok=True)
    read_pcap_and_write_csv(
        filtered_result,
        save_path + "/" + filename.split("/")[-1].replace(".pcap", ".csv"),
    )
    return True


def read_pcap_and_write_csv(result, output_file):
    # 写入到 CSV 文件
    with open(output_file, mode="w", newline="") as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(["Time", "Length"])
        for i in range(len(result[0])):
            if result[1][i] == 0:
                result[0][i] = -result[0][i]
            csvwriter.writerow([result[2][i], result[0][i]])


def getIP(datalink, pkt):
    IP = False
    try:
        if datalink:
            IP = dpkt.ethernet.Ethernet(pkt).data
        else:
            IP = dpkt.ip.IP(pkt)
    except:
        return False
    return IP


def read_pcap(file, slice, protocal):
    f = open(file, "rb")
    try:
        pkts = dpkt.pcap.Reader(f)
    except ValueError:
        f.close()
        f = open(file, "rb")
        pkts = dpkt.pcapng.Reader(f)
    datalink = pkts.datalink()
    # print(datalink)
    if (
        datalink == 228 or datalink == 229 or datalink == 101
    ):  # 是RAW_IP包，没有Ethernet层
        datalink = 0
    else:
        datalink = 1
    filedata = []
    readPcapNum = 0
    for ts, pk in pkts:
        if not readPcapNum < slice + 3:
            break
        filedata.append((ts, pk))
        readPcapNum += 1
    f.close()
    # filedata = rdpcap(file)
    srcip = inet_to_str(getIP(datalink, filedata[0][1]).src)
    # srcip = config["spider"]["host"]

    # 通过第一个数据包的flag判断是否有三次握手
    if protocal == "TCP":
        try:
            first_flag = getIP(datalink, filedata[0][1]).data.flags
        except:
            return None
        if first_flag != 2 and config["traffic"]["complate"] == "True":
            return None

    result = [
        [],
        [],
        [],
    ]  # result[0]代表长度序列，result[1]代表方向序列，result[2]代表时延序列
    for packet in filedata:
        IP = getIP(datalink, packet[1])
        ip = inet_to_str(IP.src)
        if ip == srcip:
            result[1].append(1)
        else:
            result[1].append(0)
        result[0].append(len(IP.data.data))
        nowtime = packet[0]
        dt_object = datetime.fromtimestamp(nowtime)
        formatted_time = dt_object.strftime("%Y-%m-%d %H:%M:%S")
        result[2].append(formatted_time)

    return result


if __name__ == "__main__":
    pcap2flowlog_dpkt(
        "../data/handled_pcaps/i2p_output_1.20.187.31_33014_142.171.227.116_27472.pcap",
        "./test",
    )
