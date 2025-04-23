@echo off
setlocal

:: 切换到 bat 文件所在的路径
cd /d %~dp0

:: 激活虚拟环境（按需）
call .venv\Scripts\activate

:: 执行 main.py
python main.py

endlocal
pause
