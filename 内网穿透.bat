@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 聊天室内网穿透（关闭本窗口就断开）

rem ============================================================
rem  一键内网穿透：把本机的 8000 端口临时发布到公网，
rem  让不在同一个 WiFi 里的人（比如外地的老师）也能打开聊天室。
rem
rem  原理：cpolar 客户端主动去连它自己的服务器，建立一条隧道；
rem        外面的人访问隧道给的网址，流量就顺着隧道回到你这台电脑的 8000 端口。
rem
rem  安全提醒：隧道开着的时候，网上任何人拿到这个网址都能注册账号、
rem           读写你的数据，所以演示完请按 Ctrl+C 把隧道关掉。
rem ============================================================

set "BACKEND_PORT=8000"
set "CPOLAR_EXE=%~dp0tools\cpolar\cpolar.exe"
set "TOKEN_FILE=%~dp0tools\cpolar_token.txt"
set "BACKEND_BAT=%~dp0backend\启动后端.bat"

echo ============================================================
echo   聊天室内网穿透（用 cpolar 免费版）
echo   作用：把本机 8000 端口临时发布到公网
echo ============================================================
echo.

rem ---------- 第 1 步：cpolar 客户端在不在 ----------
if not exist "%CPOLAR_EXE%" goto nocpolar

rem ---------- 第 2 步：authtoken（只有第一次需要填） ----------
if exist "%TOKEN_FILE%" goto havetoken

echo 【第一次使用，需要填一次 authtoken】
echo   1. 浏览器打开 https://www.cpolar.com 注册并登录（免费）
echo   2. 登录后点右上角进「验证」页面，复制那一串 authtoken
echo   3. 粘贴到下面回车。以后就不用再填了
echo.
set "TOKEN="
set /p TOKEN=请粘贴 authtoken：
if "%TOKEN%"=="" goto notoken
echo %TOKEN%> "%TOKEN_FILE%"
echo   [OK] 已保存到 tools\cpolar_token.txt，以后不用再填
echo.

:havetoken
rem 先清空 TOKEN 再读文件：否则读不到时会带上同名的环境变量（比如系统里本来就有 TOKEN）
set "TOKEN="
set /p TOKEN=<"%TOKEN_FILE%"
if "%TOKEN%"=="" goto notoken
"%CPOLAR_EXE%" authtoken %TOKEN% >nul 2>&1

rem ---------- 第 3 步：后端没跑就先拉起来 ----------
netstat -ano | findstr /r /c:":%BACKEND_PORT% .*LISTENING" >nul
if not errorlevel 1 goto havebackend

echo 【后端还没启动，正在新开一个窗口把它拉起来 ...】
start "聊天室后端(8000)" cmd /k "%BACKEND_BAT%"
echo   等那个新窗口里出现「聊天室页面：http://127.0.0.1:8000/」再往下用
timeout /t 8 /nobreak >nul
goto starttunnel

:havebackend
echo 【检测到 8000 端口已经有后端在跑，直接用它】

:starttunnel
echo.
echo ------------------------------------------------------------
echo   接下来在这个窗口里会滚动出 cpolar 的输出，其中会有
echo   https://xxxx.cpolar.top 这样一行，那就是公网地址：
echo     1. 把它发给你要演示的人（或自己关掉 WiFi、用手机流量试一次）
echo     2. 对方打开这个网址，看到的就是你这台电脑上的聊天室
echo.
echo   如果信息里一直是 connecting 或写着 authToken auth failed，
echo   说明 authtoken 填错了：删掉 tools\cpolar_token.txt 再双击本文件重填。
echo.
echo   注意：本窗口和「聊天室后端」窗口都不要关，关了链接就失效；
echo         演示结束按 Ctrl+C，公网链接立刻失效。
echo ------------------------------------------------------------
echo.

"%CPOLAR_EXE%" http %BACKEND_PORT%

echo.
echo   隧道已经关闭，刚才的公网网址立刻失效。
echo   如果后端窗口是本次脚本新开的，记得把那个窗口也关掉。
pause
exit /b 0

rem ==================== 出错时的提示 ====================

:nocpolar
echo [错误] 找不到 cpolar 客户端：%CPOLAR_EXE%
echo        正常情况下它应该就在上面这个位置，确认一下有没有被误删。
echo        重新下载：https://www.cpolar.com/download
echo        选 Windows 64-bit，解压后把 cpolar.exe 放到 tools\cpolar\ 目录下。
pause
exit /b 1

:notoken
echo [错误] 没有输入 authtoken，没法建立隧道。
echo        authtoken 在 cpolar 官网登录后的「验证」页面里，复制粘贴过来即可。
pause
exit /b 1
