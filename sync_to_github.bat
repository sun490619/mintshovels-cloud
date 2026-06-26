@echo off
chcp 65001 >nul
REM ══════════════════════════════════════════════════════════════
REM MintShovels · 一键同步到 GitHub (Windows)
REM 双击运行即可自动推送工具代码到 GitHub Pages
REM ══════════════════════════════════════════════════════════════

cd /d "%~dp0"

echo ═══════════════════════════════════════
echo   🔧 MintShovels 一键同步工具
echo   金牌铲子工坊 · GitHub Auto Sync
echo ═══════════════════════════════════════
echo.

REM 检查 git
where git >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ 未找到 git，请先安装: https://git-scm.com
    pause
    exit /b 1
)

REM 检查是否已初始化
if not exist ".git" (
    echo 📦 首次运行 — 初始化 Git 仓库...
    git init
    echo.
    echo 🔗 请输入你的 GitHub 仓库地址:
    set /p REPO_URL="(例: https://github.com/你的用户名/mintshovels-tools.git): "
    git remote add origin "%REPO_URL%"
    echo ✅ 远程仓库已配置
)

echo 📊 当前状态:
git status --short
echo.

echo 📤 正在同步...
echo   1/3 添加变更文件...
git add -A

echo   2/3 提交变更...
for /f "tokens=1-5 delims=/:. " %%a in ("%date% %time%") do set TS=%%a-%%b-%%c_%%d:%%e
git commit -m "Auto-sync: %TS%" 2>nul || echo     (没有新变更)

echo   3/3 推送到 GitHub...
git push -u origin main 2>nul || git push -u origin master 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ⚠️  推送失败！请确认:
    echo   1. 仓库地址正确
    echo   2. 你有推送权限 (可能需要 GitHub Token)
    echo.
    echo 💡 如何获取 GitHub Token:
    echo    1. 打开 https://github.com/settings/tokens
    echo    2. 点击 "Generate new token ^(classic^)"
    echo    3. 勾选 "repo" 权限
    echo    4. 生成后复制 Token
    echo    5. 用 Token 替换密码推送
    pause
    exit /b 1
)

echo.
echo ═══════════════════════════════════════
echo   ✅ 同步成功！
echo   🌐 访问你的 GitHub 查看更新
echo ═══════════════════════════════════════
echo.
echo 💡 提示: 如果已绑定 Cloudflare Pages，网站会在1分钟内自动更新！

pause
