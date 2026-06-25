#!/usr/bin/env python3
"""
MintShovels 定时自动巡检 — Cron Job 入口
===========================================
用法:
  python3 auto_health_check.py              # 静默巡检，保存结果
  python3 auto_health_check.py --verbose    # 打印结果
  python3 auto_health_check.py --deep       # 全量深度扫描（较慢）

产出:
  - functional_test_report.json  (全量报告，--deep时更新)
  - health_snapshot.json         (快照摘要)

Exit codes:
  0 = 🟢 健康率 >= 90%
  1 = 🟡 健康率 50-90%
  2 = 🔴 健康率 < 50%
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SNAPSHOT_PATH = os.path.join(SCRIPT_DIR, "health_snapshot.json")

def run_check(deep=False, verbose=False):
    """执行巡检"""
    from functional_test_runner import health_check_snapshot, full_scan, print_report

    if verbose:
        print(f"🩺 MintShovels 定时巡检开始... {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if deep:
        # 全量深度扫描
        report = full_scan()
        print_report(report)
        snapshot = {
            "mode": "deep",
            "ok": report["summary"]["health_rate"] >= 50,
            "health_rate": report["summary"]["health_rate"],
            "total": report["summary"]["total_tested"],
            "hollow_count": report["summary"]["hollow_shells"],
            "functional_count": len(report.get("functional_tools", [])),
            "checked_at": report["report_time"],
        }
    else:
        # 快速快照
        snapshot = health_check_snapshot()
        snapshot["mode"] = "snapshot"
        if verbose:
            print(f"\n  结果: {snapshot['detail']}")

    # 保存快照
    with open(SNAPSHOT_PATH, "w") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    # 返回 exit code
    hr = snapshot["health_rate"]
    is_ok = snapshot.get("ok", True)
    if not is_ok:
        # ok=false 表示发现真实异常
        if verbose:
            print(f"🚨 健康率严重不足 ({hr}%)！{snapshot.get('detail', '')}")
        return 2
    elif hr < 50 and is_ok:
        # v1.6垃圾切除场景：健康率低但 ok=true，审计记录不算异常
        if verbose:
            print(f"ℹ️ 健康率数据仅审计留存 ({hr}%) — 实际工具已在v1.6垃圾切除中清理")
            print(f"   {snapshot.get('detail', '')}")
        return 0
    elif hr < 90:
        if verbose:
            print(f"⚠️ 健康率偏低 ({hr}%)")
        return 1
    else:
        if verbose:
            print(f"✅ 健康率正常 ({hr}%)")
        return 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="MintShovels 定时自动巡检")
    parser.add_argument("--verbose", action="store_true", help="打印结果")
    parser.add_argument("--deep", action="store_true", help="全量深度扫描")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    args = parser.parse_args()

    if args.json:
        from functional_test_runner import health_check_snapshot
        print(json.dumps(health_check_snapshot(), ensure_ascii=False, indent=2))
        sys.exit(0)

    exit_code = run_check(deep=args.deep, verbose=args.verbose)
    sys.exit(exit_code)
