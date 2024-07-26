import pyshark
import json
import re
from collections import defaultdict
from tqdm import tqdm


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


def analyze_pcap(file_path):
    capture = pyshark.FileCapture(file_path)
    unique_snis = set()
    unique_ipv4 = set()
    ip_packet_counts = defaultdict(int)
    conversations = defaultdict(int)
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

                conversation_key = tuple(sorted([(src_ip, src_port), (dst_ip, dst_port)]))
                conversations[conversation_key] += 1

                # Check if the packet is part of a TLS session
                if hasattr(packet, 'tls') and 'handshake' in packet.tls.field_names:
                    if packet.tls.handshake_type == '1':  # Client Hello
                        clean_tls_describe = eliminate_ANSI(packet.tls)
                        sni = extract_sni(clean_tls_describe)
                        if sni:
                            unique_snis.add(sni)
                        tls_flags[conversation_key] = True

                # Count the packet as TLS if the conversation is marked as TLS
                if tls_flags[conversation_key]:
                    tls_packets += 1

            elif protocol == "UDP":
                src_port = packet.udp.srcport
                dst_port = packet.udp.dstport
                udp_packets += 1
                if dst_port == '443' or src_port == '443':
                    quic_packets += 1

                conversation_key = tuple(sorted([(src_ip, src_port), (dst_ip, dst_port)]))
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
    unique_sni_count = len(unique_snis)

    total_ip_packets = sum(ip_packet_counts.values())
    ip_packet_percentage = [(ip, (count / total_ip_packets) * 100) for ip, count in ip_packet_counts.items()]
    top_ip_packet_percentage = sorted(ip_packet_percentage, key=lambda x: x[1], reverse=True)[:5]

    conversation_packet_counts = {str(k): v for k, v in conversations.items()}

    results = {
        "unique_sni_count": unique_sni_count,
        "unique_ipv4_count": unique_ipv4_count,
        "top_ip_packet_percentage": top_ip_packet_percentage,
        "total_conversations": len(conversation_packet_counts),
        "total_packets": total_packets,
        "conversation_packet_counts": conversation_packet_counts,
        "tcp_conversations": tcp_conversations,
        "tcp_packets": tcp_packets,
        "tls_conversations": tls_conversations,
        "tls_packets": tls_packets,
        "udp_conversations": udp_conversations,
        "udp_packets": udp_packets,
        "quic_conversations": quic_conversations,
        "quic_packets": quic_packets
    }

    return json.dumps(results, indent=4)


# Example usage
pcap_file = r"C:\Study\Code\trace_spider\trace_spider\analyze\20240725_17_55_04_youtube.com.pcap"
results = analyze_pcap(pcap_file)
print(results)
