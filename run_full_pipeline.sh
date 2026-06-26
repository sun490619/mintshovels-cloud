#!/bin/bash
# ═══════════════════════════════════════════
#  MintShovels 全自动流水线 — 一键启动
#  流程: 数据采集 → 需求雷达 → 工厂生产 → 测试 → 提交部署
# ═══════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +'%Y%m%d_%H%M%S')
LOG_FILE="$LOG_DIR/pipeline_$TIMESTAMP.log"

exec > >(tee -a "$LOG_FILE") 2>&1

echo "╔══════════════════════════════════════╗"
echo "║  MintShovels 全自动流水线           ║"
echo "║  启动: $(date '+%Y-%m-%d %H:%M:%S')        ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── 阶段 -1: 数据采集（CF/GA4/GSC/Bing） ──
echo "═══════════════════════════════════════"
echo "📡 阶段 -1: 数据引擎采集"
echo "═══════════════════════════════════════"
python3 data_engine.py 2>&1 || echo "⚠️ 数据采集有错误（非致命，继续）"
echo ""

# ── 阶段 0-3: 全自动流水线（雷达 → 工厂 → 测试 → 部署） ──
echo "═══════════════════════════════════════"
echo "🚀 阶段 0-3: 全自动流水线"
echo "═══════════════════════════════════════"
python3 engine/pipeline.py --max 3 2>&1
EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ 全流程通过！$(date '+%Y-%m-%d %H:%M:%S')"
else
    echo "⚠️ 流水线存在警告/失败，退出码: $EXIT_CODE — $(date '+%Y-%m-%d %H:%M:%S')"
fi

# ── 保留最近 30 天日志 ──
find "$LOG_DIR" -name "pipeline_*.log" -mtime +30 -delete 2>/dev/null || true

exit $EXIT_CODE
