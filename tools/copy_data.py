import os
import shutil


def copy_data(source_root, destination_root):
    # 定义 source 和 destination 的 data 路径
    destination_data_path = os.path.join(destination_root, 'data')

    # 确保 destination 的 data 目录存在
    os.makedirs(destination_data_path, exist_ok=True)

    # 遍历 source 目录
    for root, dirs, files in os.walk(source_root):
        for dir_name in dirs:
            if dir_name == 'data':
                source_data_path = os.path.join(root, dir_name)

                # 复制 data 目录下的所有文件和子目录到 destination 的 data 目录下
                for item in os.listdir(source_data_path):
                    source_item_path = os.path.join(source_data_path, item)
                    destination_item_path = os.path.join(destination_data_path, item)

                    if os.path.isdir(source_item_path):
                        # 如果目标目录中已有同名文件夹，则不创建，直接复制其内部文件
                        if os.path.exists(destination_item_path):
                            for sub_item in os.listdir(source_item_path):
                                sub_source_item_path = os.path.join(source_item_path, sub_item)
                                sub_destination_item_path = os.path.join(destination_item_path, sub_item)
                                if not os.path.exists(sub_destination_item_path):
                                    shutil.copy2(sub_source_item_path, sub_destination_item_path)
                                else:
                                    print(f"Skipped file: {sub_destination_item_path} already exists")
                        else:
                            shutil.copytree(source_item_path, destination_item_path)
                    else:
                        if not os.path.exists(destination_item_path):
                            shutil.copy2(source_item_path, destination_item_path)
                        else:
                            print(f"Skipped file: {destination_item_path} already exists")


# 使用示例
source_root = '/home/dataCollection/pcz/pcz/7.26'
destination_root = '/home/dataCollection'


copy_data(source_root, destination_root)
