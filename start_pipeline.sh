#!/bin/bash
# MintShovels 需求雷达 - 后台启动脚本
# 用法: bash start_pipeline.sh [间隔分钟数，默认120]

INTERVAL=${1:-120}
DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="$DIR/pipeline_bg.log"
PIDFILE="$DIR/pipeline_bg.pid"

# 检查是否已在运行
if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
    echo "⚠️  需求雷达已在运行 (PID: $(cat $PIDFILE))"
    echo "   停止: kill $(cat $PIDFILE)"
    exit 1
fi

echo "🚀 启动需求雷达后台模式 | 间隔: ${INTERVAL}分钟"
echo "   PID: $$"
echo $$ > "$PIDFILE"

cd "$DIR"
nohup python3 demand_scraper.py --schedule --interval "$INTERVAL" >> "$LOG" 2>&1 &
REALPID=$!
echo $REALPID > "$PIDFILE"

echo "✅ 已启动 (PID: $REALPID)"
echo "   日志: tail -f $LOG"
echo "   停止: kill $REALPID && rm $PIDFILE"
echo "   状态: cat $PIDFILE"
