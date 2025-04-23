import os
import shutil
import sys
import time
import tkinter as tk
import tkinter.filedialog as fd
from os import getenv, mkdir
from os.path import expandvars
from tkinter import ttk

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


# 获取种子信息并按文件大小降序排列, 其次以保存路径、名称升序排列
def get_torrents(client):
    _torrents = client.torrents_info()
    return sorted(_torrents, key=lambda x: (-x.size, x.save_path, x.name))


# 更新种子列表
def update_torrent_list(_torrents, search_text=""):
    for item in tree.get_children():  # 载入新的之前先清空
        tree.delete(item)
    for index, torrent in enumerate(_torrents):
        if search_text.lower() in torrent.name.lower():
            size = torrent.size
            if size >= 1 << 30:
                size_str = f"{size / (1 << 30):.2f} GB"
            elif size >= 1 << 20:
                size_str = f"{size / (1 << 20):.2f} MB"
            else:
                size_str = f"{size / (1 << 10):.2f} KB"
            # 根据行索引设置背景色
            if index % 2 == 0:
                tag = 'even_row'  # 给偶数行打上tag
            else:
                tag = ''
            # 插入数据时，新增一个空字符串作为选择列的初始值
            tree.insert("", "end",
                        values=("", torrent.name, size_str, torrent.save_path, torrent.state, torrent.hash),
                        tags=tag)


# 搜索功能
def search_torrents():
    search_text = search_entry.get()
    update_torrent_list(torrents, search_text)


# 更新选中数量
def update_selected_count():
    selected_items = [item for item in tree.get_children() if 'checked' in tree.item(item, 'tags')]
    root.title(f"qBittorrent Torrent List - Selected items: {len(selected_items)}")


# 选择功能
def toggle_check(event):
    item = tree.identify_row(event.y)
    if item:
        col = tree.identify_column(event.x)
        # 只处理第一列的点击事件
        if col == "#0" or col == "#1":
            tags = list(tree.item(item, "tags"))
            if 'checked' in tags:  # 原先已选中的情况
                tags.remove('checked')
                tree.set(item, "Selected", "")
            else:  # 原先未选中的情况
                tags.append('checked')
                tree.set(item, "Selected", "     ✔")
            tree.item(item, tags=[str(tag) for tag in tags])
            update_selected_count()


def toggle_select_all():
    global all_selected
    if all_selected:  # 原先已选中的情况
        for item in tree.get_children():
            tree.item(item, tags=[])
            tree.set(item, "Selected", "")  # 更新选择列的值为空字符串
        toggle_button.config(text="Select All")
    else:  # 原先未选中的情况
        for item in tree.get_children():
            tree.item(item, tags=['checked'])
            tree.set(item, "Selected", "     ✔")  # 更新选择列的值为 "✔"
        toggle_button.config(text="Deselect All")
    all_selected = not all_selected
    update_selected_count()


# Function to open folder selection dialog
def set_new_path():
    global torrents
    new_path = fd.askdirectory()
    if new_path:
        Avalon.info(f"New path selected: {new_path}")
        selected_items = [item for item in tree.get_children() if 'checked' in tree.item(item, 'tags')]
        selected_hashes = [tree.item(item, 'values')[columns.index("Torrent Hash")] for item in selected_items]
        if not selected_hashes:
            Avalon.warning("No item selected!")
            return  # 防止传入空列表，导致意外选中全部种子

        selected_torrents = qbt_client.torrents_info(torrent_hashes=selected_hashes)  # 根据 hash 去获取选种子信息

        ###
        # 开始为种子设定新的保存路径，并跳过校验
        ###

        # 禁用窗口操作
        root.config(cursor="wait")
        root.update_idletasks()
        root.attributes("-disabled", True)

        try:
            # 旧版 API
            if not USE_NEW_EXPORT_API:
                shutil.rmtree("./temp_BT_backup") if os.path.exists("./temp_BT_Backup") else None
                shutil.copytree(qb_backup_path, "./temp_BT_Backup")
                Avalon.info(f"已备份种子文件夹：{qb_backup_path} 到当前目录")

            for torrent in selected_torrents:
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
                    save_path=str(new_path),  # 设置新的保存路径
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
                        Avalon.warning(
                            f"种子：{torrent['name']} 的 tracker 列表为空，已添加！ Tracker：{torrent['tracker']}")
                else:
                    Avalon.warning(f"种子：{torrent['name']} 添加失败！ Hash：{torrent['hash']}")

            # 再次更新列表
            torrents = get_torrents(qbt_client)
            update_torrent_list(torrents)
            update_selected_count()

        finally:
            # 恢复窗口操作
            root.config(cursor="")
            root.update_idletasks()
            root.attributes("-disabled", False)


def on_closing():
    Avalon.info("执行完毕", front="\n")
    qbt_client.auth_log_out()
    root.destroy()


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

    # 创建主窗口
    root = tk.Tk()
    root.title("qBittorrent Torrent List")
    root.geometry("850x500")
    root.protocol("WM_DELETE_WINDOW", on_closing)

    # 创建搜索框
    search_frame = tk.Frame(root)
    search_frame.pack(fill=tk.X, padx=10, pady=5)
    search_label = tk.Label(search_frame, text="Search:")
    search_label.pack(side=tk.LEFT)
    search_entry = tk.Entry(search_frame)
    search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    search_button = tk.Button(search_frame, text="Search", command=search_torrents)
    search_button.pack(side=tk.LEFT)

    # 创建全选/反选按钮
    all_selected = False  # Added global variable to track selection state
    toggle_button = tk.Button(search_frame, text="Select All", command=toggle_select_all)  # Changed button to toggle
    toggle_button.pack(side=tk.LEFT, padx=5)

    # 创建表格和滚动条的框架
    frame = tk.Frame(root)
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    # 创建表格
    style = ttk.Style()
    style.map('Treeview', background=[('selected', 'lightgray')], foreground=[("selected", "black")])  # 当前选中行的背景、前景色

    columns = ("Selected", "Name", "Size", "Save Path", "State", "Torrent Hash")
    tree = ttk.Treeview(frame, columns=columns, show="headings")
    tree.heading("Selected", text="Selected")
    tree.heading("Name", text="Name")
    tree.heading("Size", text="Size")
    tree.heading("Save Path", text="Save Path")
    tree.heading("State", text="State")
    tree.heading("Torrent Hash", text="Torrent Hash")
    tree.column("Selected", width=60, stretch=False)
    tree.column("Name", width=400, stretch=False)
    tree.column("Size", width=100, stretch=False)
    tree.column("Save Path", width=200, stretch=False)
    tree.column("State", width=100, stretch=False)
    tree.column("Torrent Hash", width=300, stretch=False)

    tree.tag_configure('checked', background='#ccff99')  # 添加选中后的样式
    tree.tag_configure('even_row', background='#f0f0f0')  # 为偶数行设置浅灰色背景
    tree.bind("<Button-1>", toggle_check)

    # 创建滚动条
    v_scrollbar = tk.Scrollbar(frame, orient="vertical", command=tree.yview)
    h_scrollbar = tk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

    # 将表格和滚动条放置在框架中
    tree.grid(row=0, column=0, sticky='nsew')
    v_scrollbar.grid(row=0, column=1, sticky='ns')
    h_scrollbar.grid(row=1, column=0, sticky='ew')
    # 配置框架的行列权重
    frame.grid_rowconfigure(0, weight=1)
    frame.grid_columnconfigure(0, weight=1)

    # 创建一个底部框架
    bottom_frame = tk.Frame(root)
    bottom_frame.pack(fill=tk.X, pady=5)
    # 添加 "Set New Path" 按钮
    set_path_button = tk.Button(bottom_frame, text="Set New Path", command=set_new_path)
    set_path_button.pack(anchor='center', padx=5)

    # 登录并获取种子信息
    qbt_client = qb_login(qb_host, qb_port, qb_username, qb_passwd)
    torrents = get_torrents(qbt_client)
    Avalon.info(f"获取到种子数：{len(torrents)}")
    update_torrent_list(torrents)

    # 运行主循环
    root.mainloop()
