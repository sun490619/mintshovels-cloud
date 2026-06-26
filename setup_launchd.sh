#!/bin/bash
# ═══════════════════════════════════════════
#  安装 MintShovels 自动定时任务 (macOS)
#  使用方法: bash setup_launchd.sh
# ═══════════════════════════════════════════
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_SRC="$SCRIPT_DIR/com.mintshovels.pipeline.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.mintshovels.pipeline.plist"

# 创建日志目录
mkdir -p "$SCRIPT_DIR/logs"

# 确保 Python 可用
PYTHON=$(which python3 2>/dev/null || echo "/usr/local/bin/python3")
echo "🐍 Python: $PYTHON"
$PYTHON --version

# 复制 plist 到 LaunchAgents
cp "$PLIST_SRC" "$PLIST_DST"
echo "📋 plist 已复制到: $PLIST_DST"

# 卸载旧的（如果存在）
launchctl unload "$PLIST_DST" 2>/dev/null || true

# 加载新任务
launchctl load "$PLIST_DST"
echo "✅ 定时任务已加载！"

# 验证
echo ""
echo "📊 当前状态:"
launchctl list | grep mintshovels || echo "  (稍等片刻启动...)"

echo ""
echo "=== 管理命令 ==="
echo "  查看状态:    launchctl list | grep mintshovels"
echo "  手动停止:    launchctl unload $PLIST_DST"
echo "  手动启动:    launchctl load $PLIST_DST"
echo "  查看日志:    tail -f $SCRIPT_DIR/logs/pipeline_stdout.log"
echo "  查看错误:    tail -f $SCRIPT_DIR/logs/pipeline_stderr.log"
echo ""
echo "⏰ 每3小时自动运行一次，首次加载后立即运行"
