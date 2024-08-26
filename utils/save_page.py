import os
import pyautogui
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from utils.chrome import create_chrome_driver
import hashlib
from utils.task import task_instance

def get_directory_size(directory):
    """计算指定目录的总大小（单位：字节）"""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(directory):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            # 检查文件是否存在，避免文件路径无效或出现访问错误
            if os.path.exists(file_path):
                total_size += os.path.getsize(file_path)
    return total_size

def wait_for_download_to_finish(download_dir, old_size, timeout=60):
    end_time = time.time() + timeout
    while time.time() < end_time:
        new_size = get_directory_size(download_dir)
        if new_size != old_size:
            print("文件下载完成")
            return True
        time.sleep(1)  # 每隔1秒检查一次

    print("文件下载超时")
    return False


def hash_and_store(input_string, file_path='hash_results.txt'):
    # 计算输入字符串的哈希值（使用SHA-256算法）
    hash_object = hashlib.sha256(input_string.encode('utf-8'))
    hash_value = hash_object.hexdigest()

    # 返回哈希值
    return hash_value


def save_page(driver):
    # 指定要检查的目录路径
    downloads_dir = r"C:\Users\Administrator\Downloads"

    hash_results_file = os.path.join(os.getcwd(), task_instance.current_allowed_domain + '_hash_file')

    url_hash = hash_and_store(driver.current_url, hash_results_file)

    file_path = os.path.join(downloads_dir, url_hash)
    
    if not os.path.isfile(file_path + '.htm'):
        # 将原字符串和哈希值写入文本文件
        with open(file_path, 'a') as file:  # 使用 'a' 模式附加内容到文件中
            file.write(f"{driver.current_url}SHA-256TO{url_hash}\n")

        # 模拟 Ctrl+S 保存页面操作
        pyautogui.hotkey('ctrl', 's')
        
        # 等待保存对话框弹出
        time.sleep(2)

        # 输入保存的文件路径和文件名
        pyautogui.write(url_hash)

        # 选择保存类型：通过 Tab 键切换焦点到保存类型选择框
        # 如果焦点默认在保存文件名框，则需要多次 Tab 键切换
        pyautogui.press('tab')  # 切换到保存类型的下拉框
        time.sleep(1)

        # 通过向上或向下箭头选择 .mhtml 选项
        # 假设需要按 'down' 键来选择正确的格式
        pyautogui.press('down')  # 视保存格式选项数量而定，调整按键次数
        time.sleep(1)

        pyautogui.press('down')  # 视保存格式选项数量而定，调整按键次数
        time.sleep(1)

        # 模拟回车以确认xuanxiang
        pyautogui.press('enter')

        old_size_in_bytes = get_directory_size(downloads_dir)

        # 模拟回车以确认保存
        pyautogui.press('enter')

        wait_for_download_to_finish(downloads_dir, old_size_in_bytes)
        time.sleep(1)

