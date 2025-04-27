import sys
import os
import time
import shutil
import argparse
from os import getenv, mkdir
from os.path import expandvars, exists, join
from dataclasses import dataclass, field, fields

import qbittorrentapi
from packaging.version import Version
import dotenv

from utils.avalon import Avalon
from utils.dataclass_util import load_dataclass_from_env, expandvars_fields


@expandvars_fields("backup_path")
@dataclass
class Config:
    """存储从环境变量加载的 qBittorrent 配置。"""
    host: str = "http://127.0.0.1"
    port: int = 8080
    username: str = ""
    password: str = ""
    backup_path: str = field(
        default_factory=lambda: expandvars(getenv("QB_BACKUP_PATH_DEFAULT", r"%LOCALAPPDATA%\qBittorrent\BT_backup")))


class QBittorrentSkipCheck:

    def __init__(self, config):
        self.config = config
        self.qbt_client = None
        self.temp_dir = "./temp"
        self.temp_backup_dir = "./temp_BT_Backup"
        self.use_new_export_api = True
        self.processed_count = 0
        self.failed_count = 0

        self._setup_working_directory()
        self._create_temp_directory()
        self.qbt_client = self._login_qbittorrent()
        self._check_qbittorrent_version()

    def _setup_working_directory(self):
        """设置工作目录到脚本所在位置"""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            os.chdir(script_dir)
        except NameError:  # 如果在交互式环境或特殊情况下运行
            os.chdir(sys.path[0])
            Avalon.warning("无法确定脚本文件路径，已切换到 sys.path[0]")

    def _create_temp_directory(self):
        """创建临时目录"""
        if not exists(self.temp_dir):
            try:
                mkdir(self.temp_dir)
            except OSError as e:
                Avalon.error(f"创建临时目录 {self.temp_dir} 失败: {e}")
                sys.exit(1)

    def _login_qbittorrent(self):
        """登录 qBittorrent Web UI"""
        Avalon.info("尝试登录 Web UI……", front="\n")
        conn_info = dict(
            host=self.config.host,
            port=self.config.port,
            username=self.config.username,
            password=self.config.password
        )
        qbc = qbittorrentapi.Client(**conn_info)
        try:
            qbc.auth_log_in()
            Avalon.info(f"{self.config.host} 连接成功！")
            Avalon.info(f"qBittorrent: {qbc.app.version}")
            Avalon.info(f"qBittorrent Web API: {qbc.app.web_api_version}")
            return qbc
        except qbittorrentapi.LoginFailed as e:
            Avalon.error(f"登录失败: {e}")
            Avalon.error(
                f"请检查您的主机 ({self.config.host}:{self.config.port})、用户名和密码是否在环境变量文件中正确设置。")
            sys.exit(1)
        except qbittorrentapi.exceptions.APIConnectionError as e:
            Avalon.error(f"连接 qBittorrent Web UI 失败: {e}")
            Avalon.error(f"请确保 qBittorrent 正在运行，并且 Web UI 已在 {self.config.host}:{self.config.port} 上启用。")
            sys.exit(1)

    def _check_qbittorrent_version(self):
        """检查 qBittorrent 版本并决定使用哪个 API"""
        try:
            qbt_version = Version(self.qbt_client.app.version.lstrip("v"))
            if qbt_version < Version("4.5.0"):
                Avalon.warning("qBittorrent 版本低于 v4.5.0，可能不支持种子导出 API。")
                if Avalon.ask("是否尝试使用旧版 API (复制 BT_backup 中的文件)？(y/n)", default=False):
                    self.use_new_export_api = False
                    if not exists(self.config.backup_path):
                        Avalon.error(f"旧版 API 需要的 BT_backup 文件夹不存在于：{self.config.backup_path}")
                        sys.exit(1)
                    Avalon.info(f"将使用旧版 API，从 {self.config.backup_path} 复制文件。")
                else:
                    Avalon.info("操作已取消，因为需要旧版 API 但用户拒绝。")
                    sys.exit(0)
        except Exception as e:
            Avalon.error(f"检查 qBittorrent 版本时出错: {e}")
            sys.exit(1)

    def _backup_bt_backup_folder(self):
        """备份 BT_backup 文件夹（旧版 API 使用）"""
        if not self.use_new_export_api:
            try:
                if exists(self.temp_backup_dir):
                    shutil.rmtree(self.temp_backup_dir)
                shutil.copytree(self.config.backup_path, self.temp_backup_dir, dirs_exist_ok=True)
                Avalon.info(f"已备份种子文件夹：{self.config.backup_path} 到 {self.temp_backup_dir}")
            except Exception as e:
                Avalon.error(f"备份 BT_backup 文件夹时出错: {e}")
                sys.exit(1)

    def process_torrents(self):
        """处理符合条件的种子"""
        target_torrents = self._get_target_torrents()
        if not target_torrents:
            Avalon.info("没有需要处理的种子。")
            return

        self._backup_bt_backup_folder()

        for torrent in target_torrents:
            self._process_single_torrent(torrent)

        self._cleanup()
        Avalon.info(f"执行完毕！成功处理 {self.processed_count} 个种子，失败 {self.failed_count} 个。", front="\n")

    def _get_target_torrents(self):
        """获取符合条件的种子"""
        try:
            target_torrents = self.qbt_client.torrents.info(
                status_filter='paused',  # 筛选暂停状态的种子
                tag='IYUU自动辅种'  # 筛选标签
            )
            Avalon.info(f"找到符合条件（IYUU自动辅种 + 暂停状态）的种子数：{len(target_torrents)}，开始处理...")
            return target_torrents
        except Exception as e:
            Avalon.error(f"获取种子信息时出错: {e}")
            sys.exit(1)

    def _process_single_torrent(self, torrent):
        """处理单个种子"""
        torrent_hash = torrent.get('hash')
        torrent_name = torrent.get('name', '未知名称')
        if not torrent_hash:
            Avalon.warning(f"跳过一个无法获取 Hash 的种子: {torrent_name}")
            return

        torrent_filename = f"{torrent_hash}.torrent"
        torrent_filepath = join(self.temp_dir, torrent_filename)
        tracker_backup_filepath = join(self.temp_dir, f"{torrent_hash}.txt")  # 用于旧版 API tracker 备份

        Avalon.info(f"处理中: {torrent_name} (Hash: {torrent_hash[:8]}...)")

        try:
            # 1. 导出/复制种子文件
            self._export_or_copy_torrent_file(torrent_hash, torrent_filepath, torrent_name, tracker_backup_filepath)

            # 2. 删除种子(不删除文件)
            self._delete_torrent(torrent_hash, torrent_name)

            # 3. 重新添加种子
            if self._re_add_torrent(torrent, torrent_filepath, torrent_name):
                self.processed_count += 1

                # 4. 检查和恢复tracker(如果需要)
                self._check_and_restore_trackers(torrent_hash, torrent_name, tracker_backup_filepath, torrent)

                # 清理种子文件
                os.remove(torrent_filepath)

        except Exception as e:
            Avalon.error(f"处理种子 {torrent_name} 时发生错误: {e}")
            self.failed_count += 1
            import traceback
            Avalon.error(f"错误追踪:\n{traceback.format_exc()}")

    def _export_or_copy_torrent_file(self, torrent_hash, torrent_filepath, torrent_name, tracker_backup_filepath):
        """导出或复制种子文件"""
        if self.use_new_export_api:
            with open(torrent_filepath, 'wb') as f:
                f.write(self.qbt_client.torrents.export(torrent_hash))
        else:
            source_torrent_path = join(self.config.backup_path, f"{torrent_hash}.torrent")
            if exists(source_torrent_path):
                shutil.copy(source_torrent_path, torrent_filepath)

                # 保存备份tracker列表
                with open(tracker_backup_filepath, 'w', encoding='utf-8') as f:
                    f.write(self.qbt_client.torrents.properties(torrent_hash).get('tracker', ''))
            else:
                raise FileNotFoundError(
                    f"在 BT_backup 文件夹 {self.config.backup_path} 中找不到种子文件 {torrent_hash}.torrent")

    def _delete_torrent(self, torrent_hash, torrent_name):
        """删除种子"""
        self.qbt_client.torrents_delete(delete_files=False, torrent_hashes=torrent_hash)
        Avalon.info(f"  - 已删除种子 (保留文件): {torrent_name}")
        time.sleep(0.5)

    def _re_add_torrent(self, torrent, torrent_filepath, torrent_name):
        """重新添加种子"""
        add_params = dict(
            torrent_files=torrent_filepath,
            save_path=torrent['save_path'],
            content_path=torrent['content_path'],
            is_skip_checking=True,
            category=torrent['category'],
            tags=torrent['tags'],
            upload_limit=torrent['up_limit'],
            download_limit=torrent['dl_limit']
        )

        res = self.qbt_client.torrents_add(**add_params)

        if "OK" in res.upper():
            Avalon.info(f"  + 种子重新添加成功: {torrent_name}")
            time.sleep(1)  # 在tracker操作前必要的暂停
            return True
        else:
            Avalon.error(f"  X 种子添加失败: {torrent_name}. 响应: {res}")
            return False

    def _check_and_restore_trackers(self, torrent_hash, torrent_name, tracker_backup_filepath, torrent):
        """检查和恢复tracker"""
        try:
            # 获取新添加种子的tracker列表
            current_trackers_info = self.qbt_client.torrents.trackers(torrent_hash)
            current_tracker_urls = {t['url'] for t in current_trackers_info}

            # 获取原始tracker(来自torrent字典或备份文件)
            original_tracker_str = torrent.get('tracker', '')
            if not self.use_new_export_api and exists(tracker_backup_filepath):
                with open(tracker_backup_filepath, 'r', encoding='utf-8') as f:
                    original_tracker_str = f.read()

            original_trackers_list = [trk.strip() for trk in original_tracker_str.splitlines() if trk.strip()]

            # 如果当前tracker为空或数量明显少于原始tracker，且原始tracker不为空
            if (not current_tracker_urls or len(current_tracker_urls) < len(
                    original_trackers_list)) and original_trackers_list:
                Avalon.warning(f"  ! 种子 {torrent_name} 的tracker列表为空或不完整，尝试添加原始tracker...")
                trackers_to_add_str = "\n".join(original_trackers_list)
                try:
                    self.qbt_client.torrents.add_trackers(torrent_hash=torrent_hash, urls=trackers_to_add_str)
                    Avalon.info(f"    -> 已尝试添加 {len(original_trackers_list)} 个原始tracker。")
                except Exception as add_trk_err:
                    Avalon.error(f"    -> 添加tracker时出错: {add_trk_err}")

            elif not original_trackers_list:
                Avalon.info(f"  - 种子 {torrent_name} 原本就没有tracker或tracker列表为空，无需添加。")
            else:
                Avalon.info(f"  - Tracker状态似乎正常: {torrent_name}")

            # 清理旧版API的tracker备份文件
            if not self.use_new_export_api and exists(tracker_backup_filepath):
                try:
                    os.remove(tracker_backup_filepath)
                except OSError as e:
                    Avalon.warning(f"  ! 清理tracker备份文件 {tracker_backup_filepath} 失败: {e}")

        except qbittorrentapi.exceptions.NotFound404Error:
            Avalon.warning(f"  ! 添加种子 {torrent_name} 后立即查询tracker失败(404)，可能需要稍等或手动检查。")
        except Exception as track_err:
            Avalon.warning(f"  ! 检查或添加tracker时出错 ({torrent_name}): {track_err}")

    def _cleanup(self):
        """清理临时文件和目录"""
        # 如果使用了旧版API，清理临时备份目录
        if not self.use_new_export_api and exists(self.temp_backup_dir):
            try:
                shutil.rmtree(self.temp_backup_dir)
                Avalon.info(f"已清理临时备份目录 {self.temp_backup_dir}")
            except Exception as e:
                Avalon.warning(f"清理临时备份目录 {self.temp_backup_dir} 时出错: {e}")

        # 登出Web UI会话
        try:
            self.qbt_client.auth_log_out()
            Avalon.info("已退出Web UI会话。")
        except Exception as e:
            Avalon.warning(f"退出Web UI会话时出错: {e}")


def _load_environment_variables(env_file_path):
    """加载环境变量文件"""
    try:
        if exists(env_file_path):
            dotenv.load_dotenv(dotenv_path=env_file_path, override=True)
            Avalon.info(f"已从{env_file_path}加载环境变量。")
        elif env_file_path == ".env":
            dotenv.load_dotenv(override=True)
            Avalon.info("尝试加载默认.env文件(如果存在)。")
        else:
            Avalon.warning(f"指定的环境变量文件{env_file_path}不存在，将仅使用系统环境变量或默认值。")
    except Exception as e:
        Avalon.error(f"加载环境变量文件{env_file_path}时出错: {e}")
        if not Avalon.ask("加载环境变量出错，是否继续尝试（可能缺少配置）？(y/n)", default=False):
            sys.exit(1)


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="IYUU辅种免验助手")
    parser.add_argument("-e", "--env-file", type=str, default=".env", help="指定要加载的环境变量文件路径 (默认为.env)")
    args = parser.parse_args()

    # 加载环境变量
    _load_environment_variables(args.env_file)

    # 加载配置
    config = load_dataclass_from_env(Config, 'QB_')

    # 基本验证
    if not config.username or not config.password:
        Avalon.warning("环境变量QB_USERNAME或QB_PASSWD未设置或为空。")
        if not Avalon.ask("是否继续尝试匿名或使用之前的会话？ (y/n)", default=False):
            sys.exit(0)

    # 创建并初始化处理器
    processor = QBittorrentSkipCheck(config)
    processor.process_torrents()


if __name__ == '__main__':
    main()
