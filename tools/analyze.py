import pyshark
import json
import re
import os
from collections import defaultdict
from tqdm import tqdm
import concurrent.futures
import psutil


def eliminate_ANSI(tls_describe):
    ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
    clean_tls_describe = ansi_escape.sub('', f'{str(tls_describe)}\n')
    return clean_tls_describe


def extract_sni(clean_tls_describe):
    server_name_pattern = r'Server Name:\s*(.*?)(?=\s{2,})'
    server_name_match = re.search(server_name_pattern, clean_tls_describe)
    if server_name_match:
        server_name = server_name_match.group(1)
        return server_name
    return None


def normalize_conversation_key(src_ip, src_port, dst_ip, dst_port, protocol):
    if (src_ip, src_port) > (dst_ip, dst_port):
        src_ip, dst_ip = dst_ip, src_ip
        src_port, dst_port = dst_port, src_port
    return (src_ip, src_port, dst_ip, dst_port, protocol)


def analyze_pcap(file_path):
    capture = pyshark.FileCapture(file_path)
    unique_snis = []
    unique_ipv4 = set()
    ip_packet_counts = defaultdict(int)
    conversations = defaultdict(int)
    conversation_details = []
    tls_flags = defaultdict(bool)
    total_packets = 0
    tcp_packets = 0
    tls_packets = 0
    udp_packets = 0
    quic_packets = 0
    tcp_conversations = 0
    udp_conversations = 0
    tls_conversations = 0
    quic_conversations = 0

    pbar = tqdm(desc="Processing packets", bar_format="{n_fmt} packets processed [{elapsed}, {rate_fmt}]")

    for packet in capture:
        total_packets += 1
        pbar.update(1)

        if 'IP' in packet:
            src_ip = packet.ip.src
            dst_ip = packet.ip.dst
            unique_ipv4.update([src_ip, dst_ip])
            ip_packet_counts[src_ip] += 1
            ip_packet_counts[dst_ip] += 1

            protocol = packet.transport_layer
            if protocol == "TCP":
                src_port = packet.tcp.srcport
                dst_port = packet.tcp.dstport
                tcp_packets += 1

                conversation_key = normalize_conversation_key(src_ip, src_port, dst_ip, dst_port, protocol)
                conversations[conversation_key] += 1

                # Check if the packet is part of a TLS session
                try:
                    if hasattr(packet,
                               'tls') and 'handshake' in packet.tls.field_names and packet.tls.handshake_type == '1':  # Client Hello
                        clean_tls_describe = eliminate_ANSI(packet.tls)
                        sni = extract_sni(clean_tls_describe)
                        if sni:
                            unique_snis.append({'address': dst_ip, 'sni': sni})
                        tls_flags[conversation_key] = True
                except AttributeError:
                    pass

                # Count the packet as TLS if the conversation is marked as TLS
                if tls_flags[conversation_key]:
                    tls_packets += 1

            elif protocol == "UDP":
                src_port = packet.udp.srcport
                dst_port = packet.udp.dstport
                udp_packets += 1
                if dst_port == '443' or src_port == '443':
                    quic_packets += 1

                conversation_key = normalize_conversation_key(src_ip, src_port, dst_ip, dst_port, protocol)
                conversations[conversation_key] += 1

                if conversations[conversation_key] == 1:
                    udp_conversations += 1
                    if dst_port == '443' or src_port == '443':
                        quic_conversations += 1

            # Count TCP conversations
            if protocol == "TCP" and conversations[conversation_key] == 1:
                tcp_conversations += 1

    pbar.close()

    # Count TLS conversations after processing all packets
    tls_conversations = sum(1 for flag in tls_flags.values() if flag)

    capture.close()

    unique_ipv4_count = len(unique_ipv4)
    unique_sni_count = len(set(s['sni'] for s in unique_snis))

    total_ip_packets = sum(ip_packet_counts.values())
    ip_packet_percentage = [
        {"address": ip, "percent": (count / total_ip_packets) * 100}
        for ip, count in ip_packet_counts.items()
        if (count / total_ip_packets) * 100 < 50  # Exclude local IP if its count is 50% or more
    ]
    top_ip_packet_percentage = sorted(ip_packet_percentage, key=lambda x: x['percent'], reverse=True)[:5]

    for (src_ip, src_port, dst_ip, dst_port, protocol), count in conversations.items():
        conversation_details.append({
            "addressA": src_ip,
            "portA": src_port,
            "addressB": dst_ip,
            "portB": dst_port,
            "protocol": protocol,
            "packet_count": count
        })

    results = {
        "unique_sni_count": unique_sni_count,
        "unique_snis": unique_snis,
        "unique_ipv4_count": unique_ipv4_count,
        "top_ip_packet_percentage": top_ip_packet_percentage,
        "total_conversations": len(conversation_details),
        "total_packets": total_packets,
        "conversation_packet_counts": conversation_details,
        "tcp_conversations": tcp_conversations,
        "tcp_packets": tcp_packets,
        "tls_conversations": tls_conversations,
        "tls_packets": tls_packets,
        "udp_conversations": udp_conversations,
        "udp_packets": udp_packets,
        "quic_conversations": quic_conversations,
        "quic_packets": quic_packets
    }

    save_results_to_json(results, file_path)


def save_results_to_json(results, pcap_file):
    json_file_path = os.path.splitext(pcap_file)[0] + '.json'
    with open(json_file_path, 'w') as json_file:
        json.dump(results, json_file, indent=4)
    print(f"Results saved to {json_file_path}")


def get_all_pcap_files(directory):
    pcap_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.pcap') or file.endswith('.pcapng'):
                pcap_files.append(os.path.join(root, file))
    return pcap_files


def monitor_system_and_run(directory):
    pcap_files = get_all_pcap_files(directory)
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for pcap_file in pcap_files:
            while True:
                cpu_usage = psutil.cpu_percent(interval=1)
                memory_usage = psutil.virtual_memory().percent
                if cpu_usage < 60 and memory_usage < 60:
                    futures.append(executor.submit(analyze_pcap, pcap_file))
                    break
                else:
                    print(f"CPU usage: {cpu_usage}%, Memory usage: {memory_usage}% - Waiting to start new thread...")
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"An error occurred: {e}")


if __name__ == "__main__":
    directory = r"/home/dataCollection/pcz/pcz/7.26"
    monitor_system_and_run(directory)
