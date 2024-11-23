import os
from os import getenv

import qbittorrentapi

# 配置 qBittorrent Web API 的连接信息
QB_HOST = str(getenv("QB_HOST", "http://127.0.0.1"))
QB_PORT = int(getenv("QB_PORT", 8080))
QB_USERNAME = str(getenv("QB_USERNAME", "admin"))
QB_PASSWORD = str(getenv("QB_PASSWD", ""))
SAVE_PATH = str(getenv("SAVE_PATH", input("输入保存路径（双斜杆）：")))

# 要添加的种子文件路径或磁力链接
TORRENT_FILE = "../temp/524c464737bee0764e2de2994305804201bf8766.torrent"  # 替换为实际路径


def main():
    try:
        # 连接到 qBittorrent Web API
        qb = qbittorrentapi.Client(
            host=QB_HOST,
            port=QB_PORT,
            username=QB_USERNAME,
            password=QB_PASSWORD
        )

        # 测试连接
        try:
            qb.auth_log_in()
            print(f"Successfully connected to qBittorrent on {QB_HOST}:{QB_PORT}")
        except qbittorrentapi.LoginFailed as e:
            print(f"Login failed: {e}")
            return

        # 检查保存路径是否存在
        if not os.path.isdir(SAVE_PATH):
            print(f"Save path '{SAVE_PATH}' does not exist. Please check your configuration.")
            return

        # 添加种子文件并跳过校验
        if os.path.isfile(TORRENT_FILE):
            print(f"Adding torrent file: {TORRENT_FILE}")
            res = qb.torrents_add(
                save_path=SAVE_PATH,
                torrent_files=[TORRENT_FILE],
                is_skip_checking=True,  # 跳过校验
                paused=False  # 立即开始下载
            )
            if res:
                print("Torrent added successfully.")
                os.remove(TORRENT_FILE)  # 删除种子文件
        else:
            print("No valid torrent file or magnet link provided. Please check your configuration.")
            return

        qb.auth.log_out()

    except qbittorrentapi.APIConnectionError as e:
        print(f"Failed to connect to qBittorrent Web API: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()
