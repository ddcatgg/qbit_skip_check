import os
import sys
from os import getenv

import requests

# 配置项
QBITTORRENT_URL = f'{str(getenv("QB_HOST", "http://127.0.0.1"))}:{getenv("QB_PORT", 8080)}'
USERNAME = str(getenv("QB_USERNAME", "admin"))
PASSWORD = str(getenv("QB_PASSWD", ""))
SAVE_PATH = str(getenv("SAVE_PATH", input("输入保存路径（双斜杆）：")))


def login(session):
    """登录 qBittorrent Web API"""
    login_url = f"{QBITTORRENT_URL}/api/v2/auth/login"
    response = session.post(login_url, data={"username": USERNAME, "password": PASSWORD})
    if response.text != "Ok.":
        raise Exception("Failed to log in to qBittorrent. Check username and password.")
    print("Logged in successfully.")


def add_torrent(session, torrent_path):
    """添加种子并跳过校验"""
    add_url = f"{QBITTORRENT_URL}/api/v2/torrents/add"

    if not os.path.exists(torrent_path):
        raise FileNotFoundError(f"Torrent file not found: {torrent_path}")

    with open(torrent_path, "rb") as torrent_file:
        files = {"torrents": torrent_file}
        data = {
            "savepath": SAVE_PATH,
            "skip_checking": "true",  # 跳过校验
            "paused": "false",  # 添加后立即开始下载
        }
        response = session.post(add_url, files=files, data=data)

    if response.status_code == 200 and "Ok" in response.text:
        print(f"Torrent added successfully: {torrent_path}")
    else:
        raise Exception(f"Failed to add torrent. Response: {response.text}")


def main():
    os.chdir(sys.path[0])

    # 创建会话
    session = requests.Session()

    try:
        # 登录
        login(session)

        # 添加种子文件（修改为你的种子文件路径）
        torrent_file_path = "../temp/d03fab89a976e11982ec20717dce05591df3fd67.torrent"
        add_torrent(session, torrent_file_path)

    except Exception as e:
        print(f"Error: {e}")

    finally:
        # 退出登录
        session.post(f"{QBITTORRENT_URL}/api/v2/auth/logout")
        print("Logged out.")


if __name__ == "__main__":
    main()
