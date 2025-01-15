import matplotlib.pyplot as plt
import json
import os
from matplotlib.ticker import MaxNLocator
from pathlib import Path

# 读取JSON文件
def read_json(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

def process_json_files_in_directory(directory_path):
    """
    遍历给定目录及其子目录，处理所有的 JSON 文件并绘制图表。
    """
    # 遍历目录及子目录
    for root, dirs, files in os.walk(directory_path):
        for file in files:
            # 检查文件是否为 JSON 文件
            if file.endswith('.json'):
                json_file_path = os.path.join(root, file)
                print(f'Processing: {json_file_path}')
                try:
                    # 读取数据
                    sessions = read_json(json_file_path)
                    points = [{'rel_time': 0.00, 'count': 0}]
                    for session in sessions:
                        rel_time = session['rel_time']
                        point = points[-1]
                        if point and point['rel_time'] == rel_time:
                            point['count'] += 1
                        else:
                            points.append({'rel_time': rel_time, 'count': 1})

                    print(points)
                    # 提取 rel_time 和 count
                    rel_times = [point['rel_time'] for point in points]
                    counts = [point['count'] for point in points]

                    # 创建直方图
                    plt.figure(figsize=(40, 6))  # 调整图片长度
                    plt.bar(rel_times, counts, width=0.001, edgecolor='black')  # 调整宽度以增加间隔

                    # 设置图表标题和标签
                    plt.title(f'{file} - Relative Time Distribution', fontsize=14)
                    plt.xlabel('Relative Time (s)', fontsize=12)
                    plt.ylabel('Count', fontsize=12)
                    plt.gca().yaxis.set_major_locator(MaxNLocator(integer=True))
                    # 保存图表
                    output_image_path = Path(json_file_path).with_suffix('.png')
                    plt.savefig(output_image_path, dpi=300)
                    plt.close()

                except Exception as e:
                    print(f'Error processing {json_file_path}: {e}')

file_path = r'E:\Study\Code\trace_spider\data\20250104\douban.com'  # 请根据实际文件路径修改
process_json_files_in_directory(file_path)