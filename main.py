import os
import shutil
import sys
import time
from os import getenv, mkdir
from os.path import expandvars

import dotenv
import qbittorrentapi
from packaging.version import Version

from utils.avalon import Avalon

dotenv.load_dotenv()

qb_host = str(getenv("QB_HOST", "http://127.0.0.1"))
qb_port = int(getenv("QB_PORT", 8080))
qb_username = str(getenv("QB_USERNAME", ""))
qb_passwd = str(getenv("QB_PASSWD", ""))
qb_backup_path = str(expandvars(getenv("QB_BACKUP_PATH", r"%LOCALAPPDATA%\qBittorrent\BT_backup")))


def qb_login(host: str, port: int, username: str, password: str) -> qbittorrentapi.Client:
    Avalon.info("尝试登录 Web UI……", front="\n")
    conn_info = dict(host=host, port=port, username=username, password=password)
    qbc = qbittorrentapi.Client(**conn_info)
    try:
        qbc.auth_log_in()
    except qbittorrentapi.LoginFailed as e:
        Avalon.error(e)
        exit(1)
    return qbc


if __name__ == '__main__':
    os.chdir(sys.path[0])
    mkdir("temp") if not os.path.exists("temp") else None

    if not all([qb_host, qb_port, qb_username, qb_passwd]):
        Avalon.warning("请检查环境变量是否配置正确！")
        None if Avalon.ask("是否继续？", default=False) else sys.exit(0)

    qbt_client = qb_login(qb_host, qb_port, qb_username, qb_passwd)
    Avalon.info(f"qBittorrent: {qbt_client.app.version}")
    Avalon.info(f"qBittorrent Web API: {qbt_client.app.web_api_version}")

    USE_NEW_EXPORT_API = True  # 是否使用新版 API
    if Version(qbt_client.app.version.lstrip("v")) < Version("4.5.0"):
        Avalon.warning("qBittorrent 版本过低，可能不支持种子导出 API.")
        if Avalon.ask("是否尝试旧版 API (可能会有意外)？(y/n)", default=False):
            USE_NEW_EXPORT_API = False
        else:
            sys.exit(0)

    torrents = qbt_client.torrents.info()
    Avalon.info(f"读取到的种子数为：{len(torrents)}, 开始处理...")

    checking_torrents = [torrent for torrent in torrents if torrent['state'] in ["checkingDL", "checkingUP"]]
    Avalon.info(f"正在校验的种子数为：{len(checking_torrents)}")

    # BACKUP 旧版 API
    if not USE_NEW_EXPORT_API:
        shutil.rmtree("./temp_BT_backup") if os.path.exists("./temp_BT_Backup") else None
        shutil.copytree(qb_backup_path, "./temp_BT_Backup")
        Avalon.info(f"已备份种子文件夹：{qb_backup_path} 到当前目录")

    for torrent in checking_torrents:
        torrent_filename = torrent['hash'] + '.torrent'
        if USE_NEW_EXPORT_API:
            with open(f"./temp/{torrent_filename}", 'wb') as f:
                f.write(qbt_client.torrents.export(torrent['hash']))  # 导出种子文件
        else:
            shutil.copy(os.path.join(qb_backup_path, torrent_filename), f"./temp/{torrent_filename}")  # 复制出种子文件
            with open(f"./temp/{torrent['hash']}.txt", 'w') as f:
                f.write(torrent['tracker'])  # 保存备份 tracker 列表

        qbt_client.torrents_delete(delete_files=False, torrent_hashes=torrent['hash'])  # 删除种子

        time.sleep(1)

        res = qbt_client.torrents_add(
            torrent_files=f"./temp/{torrent_filename}",
            save_path=str(torrent['save_path']),
            is_skip_checking=True,
            category=torrent['category'],
            tags=torrent['tags'],
            upload_limit=torrent['up_limit'],
            download_limit=torrent['dl_limit']
        )  # 重新添加种子

        if "OK" in res.upper():
            Avalon.info(f"种子：{torrent['name']} 处理成功！ Hash：{torrent['hash']}")
            os.remove(f"./temp/{torrent_filename}")  # 删除种子文件

            time.sleep(1)  # 必要的，否则太快了会有 404
            # 检查 tracker 是否为空, 若为空则添加
            if not qbt_client.torrents.trackers(torrent['hash']):
                qbt_client.torrents.add_trackers(torrent['hash'], torrent['tracker'])
                Avalon.warning(f"种子：{torrent['name']} 的 tracker 列表为空，已添加！ Tracker：{torrent['tracker']}")
        else:
            Avalon.warning(f"种子：{torrent['name']} 添加失败！ Hash：{torrent['hash']}")

    Avalon.info("执行完毕", front="\n")
    qbt_client.auth_log_out()
