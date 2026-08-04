@echo off
title XiaoA Presentation
cd /d "%~dp0"

echo ============================================
echo   Hello, XiaoA - Presentation Launcher
echo ============================================
echo.

set PY=D:\ProgramData\anaconda3\envs\enterprise_agent\python.exe
if exist "%PY%" goto :gotpy
where python >nul 2>&1
if errorlevel 1 goto :nopy
for /f "delims=" %%i in ('where python') do (set PY=%%i)
goto :gotpy

:nopy
echo [ERROR] Python not found
pause
exit /b 1

:gotpy
echo [Python] %PY%

echo.
echo [1/3] Starting HTTP server on http://localhost:8765 ...
tasklist /fi "WINDOWTITLE eq XiaoAPresentation" 2>nul | find /i "XiaoAPresentation" >nul
if not errorlevel 1 (
  echo       Server already running
) else (
  start "XiaoAPresentation" /min "%PY%" -m http.server 8765
  echo       Started in background
)

echo.
echo [2/3] Waiting for server to be ready ...
set /a tries=0
:waitready
set /a tries+=1
timeout /t 1 /nobreak >nul
curl -s -o nul http://localhost:8765/index.html 2>nul
if not errorlevel 1 (
  echo       Server is ready (attempt %tries%)
  goto :openchrome
)
if %tries% lss 8 goto :waitready
echo [WARN] Timeout, attempting to open anyway...

:openchrome
echo.
echo [3/3] Locking dGPU via registry and opening Chrome ...
set CHROME=C:\Users\Lenovo\AppData\Local\Google\Chrome\Application\chrome.exe
if exist "%CHROME%" goto :lockgpu
where chrome >nul 2>&1
if errorlevel 1 goto :nochrome
for /f "delims=" %%i in ('where chrome') do (set CHROME=%%i)
goto :lockgpu

:lockgpu
echo [Chrome] %CHROME%
echo [GPU  ] Registry-locked to high performance dGPU

:: Kill any existing Chrome to clear GPU cache
taskkill /f /im chrome.exe >nul 2>&1
timeout /t 1 /nobreak >nul

:: Set GPU preference via registry (GpuPreference=2 = High Performance)
powershell -NoProfile -Command "$p='%CHROME:\=\\%'; New-Item -Path 'HKCU:\Software\Microsoft\DirectX\UserGpuPreferences' -Force | Out-Null; Set-ItemProperty -Path 'HKCU:\Software\Microsoft\DirectX\UserGpuPreferences' -Name '%CHROME%' -Value 'GpuPreference=2;' -Force; Write-Host 'Registry preference set: GpuPreference=2 (dGPU)'"

echo.
start "" "%CHROME%" --new-window --window-size=1920,1080 "http://localhost:8765/index.html"
goto :done

:nochrome
echo [WARN] Chrome not found, using default browser
start "" "http://localhost:8765/index.html"
timeout /t 3 /nobreak >nul
goto :done

:done
echo ============================================
echo   All done!
echo   - Chrome launched WITHOUT GPU flags
echo   - dGPU routing is handled by Windows registry
echo   - Verify: open chrome://gpu, check GL_RENDERER
echo   - Navigate: Left/Right/Space or F=fullscreen
echo ============================================
echo.
pause
