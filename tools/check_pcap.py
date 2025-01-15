import pyshark
import re
import os
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


def analyze_pcap(file_path):
    capture = pyshark.FileCapture(file_path)
    file_name = file_path.split('_')[-1].split('.pcap')[0]

    for packet in capture:
        if 'IP' in packet:
            protocol = packet.transport_layer
            if protocol == "TCP":
                # Check if the packet is part of a TLS session
                try:
                    if hasattr(packet,
                               'tls') and 'handshake' in packet.tls.field_names and packet.tls.handshake_type == '1':  # Client Hello
                        clean_tls_describe = eliminate_ANSI(packet.tls)
                        sni = extract_sni(clean_tls_describe)
                        if sni:
                            fisrt_sni = sni
                            if 'zlfbgac.site' in sni:
                                print(f'Correct VPN Pcap: {file_path}')
                                break
                            elif f'{file_name}' in sni:
                                with open('error_pcap.txt', 'a') as f:
                                    f.write(f'{file_path}\n')
                                break
                except AttributeError:
                    pass
    capture.close()

def get_all_pcap_files(directory):
    pcap_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.pcap') or file.endswith('.pcapng'):
                pcap_files.append(os.path.join(root, file))
    return pcap_files


def monitor_system_and_run(directory):
    pcap_files = get_all_pcap_files(directory)
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = []
        undeal_pcaps = []
        for pcap_file in pcap_files:
            undeal_pcaps.append(pcap_file)
        for pcap_file in undeal_pcaps:
            while True:
                cpu_usage = psutil.cpu_percent(interval=1)
                memory_usage = psutil.virtual_memory().percent
                if cpu_usage < 60 and memory_usage < 60:
                    futures.append(executor.submit(analyze_pcap, pcap_file))
                    break
                else:
                    print(f"CPU usage: {cpu_usage}%, Memory usage: {memory_usage}% - Waiting to start new process...")
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"An error occurred: {e}")


if __name__ == "__main__":
    # 解析命令行参数
    directory = r'/netdisk/dataset/vpn/data/abc.com'

    # 将解析到的参数传递给函数
    monitor_system_and_run(directory)
