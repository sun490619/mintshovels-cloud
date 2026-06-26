#!/bin/bash
# ══════════════════════════════════════════════════════════════
# MintShovels · 一键同步到 GitHub (Mac/Linux)
# 双击运行即可自动推送工具代码到 GitHub Pages
# ══════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "═══════════════════════════════════════"
echo "  🔧 MintShovels 一键同步工具"
echo "  金牌铲子工坊 · GitHub Auto Sync"
echo "═══════════════════════════════════════"
echo ""

# Check if git is available
if ! command -v git &> /dev/null; then
    echo "❌ 未找到 git，请先安装: https://git-scm.com"
    exit 1
fi

# Check if this is a git repo
if [ ! -d ".git" ]; then
    echo "📦 首次运行 — 初始化 Git 仓库..."
    git init
    echo ""
    echo "🔗 请配置你的 GitHub 仓库地址:"
    echo "   如果没有，请先去 https://github.com/new 创建一个"
    echo ""
    read -p "请输入仓库地址 (例: https://github.com/你的用户名/mintshovels-tools.git): " REPO_URL
    git remote add origin "$REPO_URL"
    echo "✅ 远程仓库已配置"
fi

echo "📊 当前状态:"
git status --short | head -20
echo ""

echo "📤 同步步骤:"
echo "  1/3 添加变更文件..."
git add -A

echo "  2/3 提交变更..."
COMMIT_MSG="Auto-sync: $(date '+%Y-%m-%d %H:%M:%S')"
# 如果有生成的工具，加入提交信息中
TOOL_COUNT=$(ls -1 tools/ 2>/dev/null | wc -l | tr -d ' ')
[ "$TOOL_COUNT" -gt 0 ] 2>/dev/null && COMMIT_MSG="$COMMIT_MSG | $TOOL_COUNT tools"
git commit -m "$COMMIT_MSG" 2>/dev/null || echo "    (没有新变更)"

echo "  3/3 推送到 GitHub..."
git push -u origin main 2>/dev/null || git push -u origin master 2>/dev/null || {
    echo ""
    echo "⚠️  推送失败！请确认:"
    echo "  1. 仓库地址正确: $(git remote get-url origin 2>/dev/null || echo '未设置')"
    echo "  2. 你有推送权限 (可能需要 GitHub Token)"
    echo ""
    echo "💡 如何获取 GitHub Token:"
    echo "   1. 打开 https://github.com/settings/tokens"
    echo "   2. 点击 'Generate new token (classic)'"
    echo "   3. 勾选 'repo' 权限"
    echo "   4. 生成后复制 Token"
    echo "   5. 用 Token 替换密码:"
    echo "      git remote set-url origin https://TOKEN@github.com/用户名/仓库名.git"
    exit 1
}

echo ""
echo "═══════════════════════════════════════"
echo "  ✅ 同步成功！"
echo "  🌐 访问你的 GitHub 查看更新:"
echo "  $(git remote get-url origin 2>/dev/null | sed 's/\.git$//' || echo '你的仓库')"
echo "═══════════════════════════════════════"

# 如果是 Cloudflare Pages 绑定了 GitHub，网站会自动更新
echo ""
echo "💡 提示: 如果已绑定 Cloudflare Pages/GitHub Pages，网站会在1分钟内自动更新！"

# 保持窗口打开让用户看到结果
echo ""
read -p "按 Enter 键关闭..."
