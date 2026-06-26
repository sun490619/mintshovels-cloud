# MintShovels 看板自动刷新 · 执行记录

## 最近执行: 2026-06-26 04:58

### 执行结果
- ✅ `mintshovels_dashboard.py --html` 成功生成 dashboard.html
- ✅ localhost:8765 正常运行 (PID 90809)，无需重启

### 数据状态
| 数据源 | 状态 | 关键指标 |
|--------|------|----------|
| Cloudflare | 🔴 API异常 | HTTP 400 Bad Request — Token 未修复 |
| GA4 | 🟢 正常 | 今日 1 活跃用户, 1 会话, 1 浏览 · 7天 62 用户 · 321 浏览 |
| GSC | 🟢 连接正常 | 0 点击 / 0 展示 / 0% CTR — 新站收录中 |
| Bing | ⚪ 无数据 | 未显示卡片，API 未正常连接 |

### 诊断
- CF API 持续 400 Bad Request，Token 问题未修复
- GA4 跳出率 100% 持续警告
- GSC 仍无搜索数据，新站正常现象
- SEO 评分 65（中等）
