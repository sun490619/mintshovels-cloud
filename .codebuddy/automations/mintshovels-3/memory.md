# MintShovels 看板自动刷新 · 执行记录

## 最近执行: 2026-06-25 22:52

### 执行结果
- ✅ `mintshovels_dashboard.py --html` 成功生成 dashboard.html
- ✅ localhost:8765 运行正常 (PID 5496)，无需重启

### 数据状态
| 数据源 | 状态 | 关键指标 |
|--------|------|----------|
| Cloudflare | 🔴 API异常 | HTTP 400 Bad Request |
| GA4 | 🟢 正常 | 今日 10 活跃用户, 18 会话, 32 浏览 · 7天 61 用户 · 均时长 708s |
| GSC | 🟡 0数据 | 0 点击 / 0 展示 / 0% CTR — 新站收录中 |
| Bing | ⚪ 无数据 | 未显示卡片，API未正常连接 |

### 诊断
- CF API 持续 400 Bad Request，Token 问题未修复
- GA4 跳出率 100% 持续警告，但均时长 708s 良好
- GSC 仍无收录数据，新站正常现象
- SEO 评分 65（中等）
