import json
import os
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from pathlib import Path


# 读取JSON文件
def read_json(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)


# 提取rel_time字段并根据数据中的最大小数位数来保留相应的小数位数
def extract_rel_time(data):
    # 提取所有的 rel_time 值
    rel_times = [entry['rel_time'] for entry in data]

    # 计算数据中最大的精度（小数位数）
    max_decimal_places = max([len(str(value).split('.')[-1]) if '.' in str(value) else 0 for value in rel_times])

    # 使用最大的小数位数来保留数据
    return rel_times, max_decimal_places


# 生成并显示图表
def plot_rel_time_distribution(rel_times, file_name, json_file_path, bin_width, range_factor=0.1):
    # 计算数据范围（max_time - min_time）
    min_time = min(rel_times)
    max_time = max(rel_times)
    data_range = max_time - min_time

    # 根据数据范围调整图像宽度，比例因子用于放大或缩小图像宽度
    fig_width = data_range * range_factor

    # 计算直方图的bin数量
    bins = int(data_range / bin_width)

    # 创建直方图
    plt.figure(figsize=(fig_width, 6))  # 设置图像宽度与数据范围相关
    plt.hist(rel_times, bins=bins, edgecolor='black', alpha=1)

    # 设置图表标题和标签
    plt.title(f'{file_name}', fontsize=14)
    plt.xlabel('Relative Time (s)', fontsize=12)
    plt.ylabel('Frequency', fontsize=12)
    plt.gca().yaxis.set_major_locator(MaxNLocator(integer=True))
    plt.subplots_adjust(left=0.5 / fig_width, right=1 - 0.5 / fig_width)

    # 显示图表
    # plt.grid(True)
    # plt.show()

    # 保存图表，图表文件名与 JSON 文件相同
    output_image_path = Path(json_file_path).with_suffix('.png')
    plt.savefig(output_image_path, dpi=300)  # 保存为 PNG 图像，设置较高的 DPI
    plt.close()  # 关闭图表，避免多个图表重叠


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
                    data = read_json(json_file_path)

                    # 提取rel_time数据并保留数据中的最大小数位数
                    rel_times, max_decimal_places = extract_rel_time(data)

                    # 设置 bin_width 为 10 的负幂，取决于最大小数位数
                    bin_width = 10 ** -max_decimal_places

                    # 绘制分布图
                    plot_rel_time_distribution(rel_times, file, json_file_path, bin_width, range_factor=bin_width * 100)  # 你可以调整比例因子
                except Exception as e:
                    print(f'Error processing {json_file_path}: {e}')


# 主函数
def main():
    # JSON文件路径
    file_path = r'E:\Study\Code\trace_spider\data\20250102'  # 请根据实际文件路径修改
    process_json_files_in_directory(file_path)


if __name__ == "__main__":
    main()
