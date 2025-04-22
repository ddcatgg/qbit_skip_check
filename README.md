## 简介
此项目用于快速跳过 qBittorrent 中正在校验的种子文件。尤其适用于 IYUU 自动辅种后的情形。

主要思路为：删除种子，重新添加，并选择“跳过哈希校验”，此时 qB 会仅仅检查文件是否存在，而不会再次校验文件的完整性。

## 注意
1. 请确保你了解“跳过校验”意味着什么，仅在确定文件完整时使用！也就是说，如果是由于“下载过程意外中断”引起的确有必要的校验，则不建议使用此脚本。
2. 主要适用于 Windows 平台，其他平台请自行对路径做一些修改。
3. 如果你觉得有必要，在运行前，请备份 qB 的种子目录。（在某些情况下，程序也会将其备份到当前目录）

## 环境与依赖配置

建议使用虚拟环境来管理依赖。以下是使用 `venv` 创建虚拟环境并安装依赖的步骤：

1. 创建虚拟环境：
    ```bash
    python -m venv venv
    ```

2. 激活虚拟环境：
    - Windows:
        ```bash
        .\venv\Scripts\activate
        ```
    - Unix 或 MacOS:
        ```bash
        source venv/bin/activate
        ```

3. 安装依赖：
    ```bash
    pip install -r requirements.txt
    ```

## 运行脚本

在运行项目之前，需要设置以下环境变量：

- `QB_HOST`: qBittorrent Web UI 的主机地址 (默认: `http://127.0.0.1`)
- `QB_PORT`: qBittorrent Web UI 的端口 (默认: `8080`)
- `QB_USERNAME`: qBittorrent Web UI 的用户名
- `QB_PASSWD`: qBittorrent Web UI 的密码
- `QB_BACKUP_PATH`: qBittorrent 种子备份路径 (默认: `%LOCALAPPDATA%\qBittorrent\BT_backup`)

Tips: 也支持建立一个 `.env` 文件来设置以上环境变量，参照 `env.example` 文件。

随后，在设置好的环境中运行 `main.py` 即可：

```bash
python main.py
```

如果有种子添加失败，对应的种子文件会保存在 `./temp` 目录下，可以手动处理。

## 其他

项目提供了 `run.example.bat` 脚本，用于快速设置环境变量并启动，可按需修改取用。

程序入口为 `main.py`，tests 目录仅用于测试 API 调用方式，非标准的 pytest 测试，可忽略。

仓库中的 `torrent_move.py` 为一个简单的图形化脚本，可独立运行。用于在手动移动种子位置后，为种子设定新路径并跳过校验。（详见 #1，注意脚本自身并不移动文件，仅做路径处理）

## 致谢
一定程度上参考了此项目： [Qbittorrent 强制跳过校验 python 脚本](https://github.com/Hugo7650/qb_skip_hash_check_script)，感谢各位作者的付出。

<details>
  <summary>其他</summary>
  为什么还要造轮子呢？我使用上述脚本时出现了意外，添加了近百个不包含 Tracker 信息的种子，而删除了原种子，造成了一些麻烦。
  <br>意外的原因在于，该项目是从 qB 种子目录复制种子，不包含 Tracker 信息。此项目改为使用 “导出” API 操作，Tracker 信息得以保留。
  <br>此外，在重新添加种子后，此项目能保留种子原有的标签，限速设置等。
</details>
