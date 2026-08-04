@echo off
title Hello，小A 环境一键启动
cd /d D:\Project\企业agent\enterprise-agent

echo ==========================================
echo   Hello，小A —— 环境自检与一键启动
echo ==========================================
echo.

echo [1/3] 检查 Docker 引擎...
docker info >nul 2>&1
if errorlevel 1 (
    echo [提示] Docker Desktop 未运行，正在启动...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo [提示] 等待 Docker 引擎就绪（首次启动可能需要 1-2 分钟）...
    :wait_docker
    timeout /t 5 /nobreak >nul
    docker info >nul 2>&1
    if errorlevel 1 goto wait_docker
)
echo [OK] Docker 引擎正常

echo.
echo [2/3] 检查基础设施容器（etcd/minio/milvus/postgres/redis）...
set NEED_UP=0
for %%c in (enterprise-agent-etcd-1 enterprise-agent-minio-1 enterprise-agent-milvus-standalone-1 enterprise-agent-postgres-1 enterprise-agent-redis-1) do (
    docker inspect -f "{{.State.Running}}" %%c 2>nul | findstr "true" >nul
    if errorlevel 1 (
        echo [提示] 容器 %%c 未运行
        set NEED_UP=1
    )
)
if "%NEED_UP%"=="1" (
    echo [提示] 正在拉起缺失的容器...
    docker compose up -d etcd minio milvus-standalone postgres redis
    echo [提示] 等待容器健康检查通过...
    timeout /t 15 /nobreak >nul
) else (
    echo [OK] 5 个基础设施容器均在运行
)

echo.
echo [3/3] 检查 API 服务（127.0.0.1:8000）...
curl -s http://127.0.0.1:8000/health | findstr "healthy" >nul
if errorlevel 1 (
    echo [提示] API 未启动，正在后台拉起 uvicorn...
    start "小A-API" /min cmd /c "set PYTHONIOENCODING=utf-8&& D:\ProgramData\anaconda3\envs\enterprise_agent\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
    echo [提示] 等待 API 就绪（模型冷加载可能较慢）...
    :wait_api
    timeout /t 3 /nobreak >nul
    curl -s http://127.0.0.1:8000/health | findstr "healthy" >nul
    if errorlevel 1 goto wait_api
) else (
    echo [OK] API 已在运行
)
echo [OK] API 健康检查通过

echo.
echo ==========================================
echo   全部就绪，正在打开浏览器...
echo ==========================================
start "" "C:\Users\Lenovo\AppData\Local\Google\Chrome\Application\chrome.exe" http://localhost:8000/ui

echo.
echo 完成！本窗口 10 秒后自动关闭。
timeout /t 10 >nul
