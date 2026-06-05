@echo off
cd /d %~dp0
if not exist .venv py -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
set DATA_DIR=data
set ENABLE_SCHEDULER=1
set ENABLE_READER=1
python app.py
pause
