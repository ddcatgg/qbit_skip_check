@echo off
setlocal

:: 切换到 bat 文件所在的路径
cd /d %~dp0

:: 激活虚拟环境（按需）
call venv\Scripts\activate

:: 设置环境变量
set QB_HOST=http://127.0.0.1
set QB_PORT=8080
set QB_USERNAME=admin
set QB_PASSWD=your_password
set QB_BACKUP_PATH=%LOCALAPPDATA%\qBittorrent\BT_backup

:: 执行 main.py
python main.py

endlocal
pause
