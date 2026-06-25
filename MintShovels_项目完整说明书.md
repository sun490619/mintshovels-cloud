# MintShovels · 金牌铲子工坊 — 项目完整说明书

> **用途**：在任何新对话/新 Agent 中发送此文件，即可无缝继续项目开发。
> **最后更新**：2026-06-21 13:13
> **域名**：https://mintshovels.com/

---

## 一、项目概览

**MintShovels（金牌铲子工坊）** 是一个全自动在线工具工厂网站。

- 提供 **33 个免费在线工具**，覆盖 6+1 个分类
- 支持中英双语切换
- 后端自动 Pipeline：全网嗅探 → 工具生成 → 测试 → 部署
- 已集成完整的变现框架（CPS推广、AdSense广告、付费订阅、赞助）

---

## 二、项目架构

```
┌─────────────────────────────────────────────┐
│          mintshovels.com (用户访问)           │
│          Cloudflare Pages 部署               │
│                                             │
│  index.html (271KB, ~4560行)                 │
│  单页应用，包含全部前端逻辑                     │
│  - 工具列表/分类/搜索                          │
│  - 国际化 (zh/en)                            │
│  - Footer (社交链接/CPS/广告/赞助/定价弹窗)      │
└──────────────┬──────────────────────────────┘
               │ API 调用
               ▼
┌─────────────────────────────────────────────┐
│      Railway 部署 (后端 API)                  │
│  https://efficient-reverence-production-     │
│        1b4a.up.railway.app                  │
│                                             │
│  app.py (4604行, FastAPI v1.3.0)             │
│  - 43 个 API 端点                            │
│  - 视频提取 / 雷达嗅探 / Pipeline             │
│  - 工厂系统 / AI客服 / 邮件通知              │
│  - 纯内存存储，无数据库依赖                    │
└─────────────────────────────────────────────┘
```

---

## 三、代码仓库位置

### 前端 (部署到 Cloudflare Pages)
```
本地路径: /Users/dawei/CodeBuddy/mintshovels-site/
核心文件: index.html (271KB, ~4560行)
部署命令: npx wrangler pages deploy . --project-name=mintshovels
Cloudflare 账号: Sun490619@gmail.com
Cloudflare Account ID: 79c00d5c90b9a218b8867186e12c6df7
```

### 后端 (部署到 Railway)
```
本地路径: /Users/dawei/CodeBuddy/20260619190045/tool-factory/
核心文件: app.py (211KB, 4604行)
依赖文件: requirements.txt, Procfile, runtime.txt
Python 版本: 3.11
GitHub 仓库: github.com/sun490619/tool-factory (🔒 私有仓库, 2026-06-21 由公开改为私有)
Railway 域名: efficient-reverence-production-1b4a.up.railway.app
```

### CI/CD
```
路径: mintshovels-site/.github/workflows/deploy.yml
触发: 每6小时自动 / Push到main / 手动
流程: Radar扫描 → 工具生成 → Cloudflare Pages部署
```

---

## 四、全部配置项速查

### 前端 (index.html:450)
```javascript
const API = "https://efficient-reverence-production-1b4a.up.railway.app";
```

### 前端社交链接 (index.html Footer区域)
| 平台 | URL |
|------|-----|
| Twitter/X | `https://x.com/wangqwkl` |
| GitHub | `https://github.com/sun490619` |
| Discord | `https://discord.gg/` (待创建服务器) |

### 后端变现配置 (app.py:64-115 `_MONETIZATION` 字典)
| 配置项 | 当前值 | 状态 |
|--------|--------|------|
| 面包多商城 | `https://mbd.pub/` | 占位符，待注册 |
| 爱发电赞助 | `https://afdian.com/` | 占位符，待注册 |
| 基础版订阅 | $3/月 → mbd.pub | 占位符 |
| 专业版订阅 | $9.9/月 → mbd.pub | 占位符 |
| 订阅合集包 | mbd.pub | 占位符 |
| AdSense | enabled: false, publisher_id: 占位符 | 待申请 |
| Namecheap CPS | `https://www.namecheap.com/` | 官网直链(无佣金) |
| OKX CPS | `https://www.okx.com/join/REFERRAL` | 官网直链(无佣金) |
| NordVPN CPS | `https://nordvpn.com/` | 官网直链(无佣金) |
| Trezor CPS | `https://surfshark.com/` | 官网直链(无佣金) |

### 环境变量 (后端 Railway)
| 变量名 | 必须 | 状态 | 用途 |
|--------|------|------|------|
| `OPENAI_API_KEY` | 是 | ✅ 已配置 | AI生成/Whisper转写/客服 |
| `OPENAI_BASE_URL` | 否 | 未配 | 默认 api.openai.com/v1 |
| `OPENAI_MODEL` | 否 | 未配 | 默认 gpt-4o-mini |
| `ADMIN_KEY` | 是 | ✅ mintshovels.com0118 | 管理后台 & API 认证 |
| `SMTP_HOST` | 否 | ✅ smtp.resend.com | 邮件通知 |
| `SMTP_PORT` | 否 | ✅ 587 | 邮件通知 |
| `SMTP_USER` | 否 | ✅ resend | 邮件通知 |
| `SMTP_PASS` | 否 | ✅ 已配置 | 邮件通知 |
| `SMTP_FROM` | 否 | ✅ noreply@mintshovels.com | 邮件通知 |

### Railway 项目信息
| 项目 | 值 |
|------|-----|
| 项目名 | efficient-reverence |
| 服务名 | efficient-reverence |
| 环境 | production |
| 公开域名 | efficient-reverence-production-1b4a.up.railway.app |
| 项目ID | d53f301f-ae94-4b5a-ba9b-ada9f7ff2a6f |
| 调度器状态 | ✅ 正常运行（已修复 key bug，2个工具已自动生成上线）

---

## 五、已实现功能完整清单

### 前端功能 (index.html)
| # | 功能 | 状态 |
|---|------|------|
| 1 | 首页工具列表 + 6分类展示 | ✅ |
| 2 | 工具搜索 (实时过滤) | ✅ |
| 3 | 中英双语切换 | ✅ |
| 4 | 工具详情页 (功能说明/标签/状态) | ✅ |
| 5 | PWA 支持 (离线访问) | ✅ |
| 6 | SEO (sitemap/OG/meta/结构化数据) | ✅ |
| 7 | 雷达状态指示器 | ✅ |
| 8 | 风控审计显示 | ✅ |
| 9 | CPS推广卡片 (Namecheap/OKX/VPN/Trezor) | ✅ |
| 10 | AdSense 广告位占位 | ✅ |
| 11 | 付费分级定价弹窗 ($3/$9.9) | ✅ |
| 12 | 订阅合集包 CTA横幅 | ✅ |
| 13 | 信任徽章 (开源/零后门/MIT) | ✅ |
| 14 | 社交链接 (Twitter/GitHub) | ✅ |
| 15 | Service Worker 缓存 | ✅ |
| 16 | 许愿池功能 | ✅ |
| 17 | Footer 完整信息栏 | ✅ |

### 后端 API (app.py, 43个端点)
| # | 端点 | 功能 |
|---|------|------|
| 1 | GET / | 服务信息 |
| 2 | GET /healthz | 健康检查 |
| 3 | POST /v1/extract | 多平台视频提取 |
| 4 | GET /v1/stream/{sid} | 流式下载 |
| 5 | POST /v1/search-log | 搜索日志 |
| 6 | GET /v1/radar | 雷达数据 |
| 7 | POST /v1/wish | 许愿池 |
| 8 | GET /v1/monetization | 变现配置API |
| 9 | POST /v1/transcribe | 音频转文字 |
| 10 | POST /v1/extract-audio | 提取音频 |
| 11 | GET /v1/workshop/status | 工厂状态 |
| 12 | GET /v1/workshop/templates | 工具模板列表 |
| 13 | GET/POST /v1/workshop/queue | 需求队列 |
| 14 | POST /v1/workshop/generate | 生成工具 |
| 15 | GET /v1/workshop/tools | 已生成工具列表 |
| 16 | POST /v1/workshop/deploy | 部署工具 |
| 17 | POST /v1/workshop/auto-generate | 自动批量生成 |
| 18 | GET/POST /v1/workshop/config | 工厂配置 |
| 19 | POST /v1/radar/scan | 全网需求嗅探(43数据源) |
| 20 | POST /v1/pipeline/run | 全自动流水线 |
| 21 | GET /v1/pipeline/status | 流水线状态 |
| 22 | GET /tools/{tool_id} | 工具页面 |
| 23 | GET /dashboard | 仪表盘HTML |
| 24 | GET /v1/scheduler/status | 调度器状态 |
| 25 | POST /v1/scheduler/start | 启动调度器 |
| 26 | POST /v1/scheduler/stop | 停止调度器 |
| 27 | GET /v1/radar/risk-audit | 风险审核列表 |
| 28 | POST /v1/radar/risk-audit/approve | 审核批准 |
| 29 | POST /v1/notify/send | 发送邮件通知 |
| 30 | GET /v1/notify/queue | 通知队列 |
| 31 | POST /v1/notify/tool-ready | 工具就绪通知 |
| 32 | POST /v1/chatbot/message | AI客服 |
| 33 | GET /v1/chatbot/history/{id} | 对话历史 |
| 34 | GET /v1/tools/similar/{id} | 相似工具推荐 |
| 35 | GET /v1/tools/recommend | 工具推荐 |
| 36 | GET /v1/tools/{id}/seo | 工具SEO |
| 37 | GET /v1/tools/seo/all | 全站SEO |

---

## 六、账号信息汇总

| 服务 | 账号/链接 | 状态 |
|------|----------|------|
| **域名** | mintshovels.com | ✅ 运行中 |
| **Cloudflare** | Sun490619@gmail.com | ✅ |
| **GitHub** | github.com/sun490619 | ✅ |
| **Twitter/X** | @wangqwkl | ✅ |
| **Discord** | sun490619_43454 (用户名) | ⚠️ 需创建服务器 + 邀请链接 |
| **Railway** | 自动部署中 | ✅ |
| **面包多 mbd.pub** | 未注册 | 🔴 待注册 |
| **爱发电 afdian.com** | 未注册 | 🔴 待注册 |
| **Google AdSense** | 未申请 | 🔴 网站有流量后申请 |
| **SMTP邮件** | 未配置 | 🟡 推荐用 Resend |

---

## 七、部署方式

### 前端部署 (Cloudflare Pages)
```bash
cd /Users/dawei/CodeBuddy/mintshovels-site
npx wrangler pages deploy . --project-name=mintshovels
```
或通过 GitHub Actions 自动部署 (`.github/workflows/deploy.yml`)

### 后端部署 (Railway)
```bash
cd /Users/dawei/CodeBuddy/20260619190045/tool-factory
# 推送到 GitHub，Railway 自动检测并部署
# 或通过 sync_to_github.command 一键同步
```

### 手动同步到 GitHub
```bash
cd /Users/dawei/CodeBuddy/20260619190045/tool-factory
# Mac/Linux
./sync_to_github.command
# Windows
sync_to_github.bat
```

---

## 八、待办事项

### 🔴 高优先级
- [ ] **Discord**：创建服务器 → 生成邀请链接 → 替换前后端 Discord 链接
- [ ] **面包多 mbd.pub**：注册 → 创建店铺 → 创建3个商品(基础版$3/专业版$9.9/合集包) → 替换所有 mbd.pub 占位链接
- [ ] **爱发电 afdian.com**：注册 → 获取创作者链接 → 替换占位链接

### 🟡 中优先级
- [ ] **SMTP邮件**：注册 Resend (resend.com) → 配置环境变量 `SMTP_HOST/PORT/USER/PASS`
- [ ] **CPS推广**：去 Namecheap/OKX/NordVPN/Trezor 申请 Affiliate → 替换推广链接

### 🟢 低优先级
- [ ] **Google AdSense**：网站流量起来后申请 → 获取 publisher_id → 改 `enabled: true`
- [x] **Cloudflare Web Analytics**：✅ 已配置，token 已存入密钥链 (cloudflare-web-analytics)

---

## 九、已知问题

1. Discord 链接为空：`discord.gg/` 没有具体邀请码
2. 所有变现链接为占位符：面包多、爱发电、AdSense 均未配置真实链接
3. CPS 链接为官网直链：无佣金
4. 🟡 **Railway GitHub 自动部署断连**：仓库变私有后 OAuth 可能失效，需手动 `railway up` 部署（已临时用本地 CLI 推送解决）

### 2026-06-21 Pipeline Bug 诊断报告 (已修复 ✅)

**症状**：网站工具列表不更新，全部显示 "Coming Soon"，调度器每3小时运行但 `generated_today = 0`

**根因**：`pipeline_run()` 函数中连续 3 处调用内部 API 时忘记传 `key` 参数：
1. `radar_scan()` → 403 → 全网扫描失败
2. `generate_tool()` → 403 → 工具生成失败
3. `deploy_tool()` → 403 → 部署失败

每个错误被 `try/except` 静默吞掉，表面看调度器正常运行，实际全链路空转。

**已修复** (commit `4e4dad5`)：
- `app.py:3305` — `radar_scan()` → `radar_scan(key=key)` ✅
- `app.py:3361` — `generate_tool(...)` → `generate_tool(..., key=key)` ✅
- `app.py:3419` — `deploy_tool(...)` → `deploy_tool(..., key=key)` ✅
- `app.py:484` — `max_per_day: 10` → `999` ✅

**验证结果** (2026-06-21 13:38)：
```
Step 1: ✅ 全网嗅探 → 25 signals from 25/50 sources
Step 2: ✅ 质量过滤 → 2 queued
Step 3: ✅ AI 生成 → 2 tools generated
Step 4: ✅ 自动测试 → 2/2 passed (100%)
Step 5: ✅ 自动部署 → 2/2 deployed to live
```

## 十、安全态势

| 风险等级 | 项目 | 状态 |
|----------|------|------|
| ✅ 已修复 | 敏感API未认证（pipeline/radar/workshop/notify） | 已加 ADMIN_KEY |
| ✅ 已修复 | 管理后台直接暴露密钥在URL | 改为本地密码验证（SHA-256） |
| ✅ 已修复 | 日志中泄露API key前缀 | 已移除 |
| ✅ 已修复 | 硬编码默认密码 mintshovels-admin | 已移除, ADMIN_KEY 必须从环境变量读取 |
| ✅ 已修复 | GitHub 仓库为公开(Public) | 已设为私有(Private) |
| 🟡 已知 | AI客服/转写/提取端点无频率限制 | 可能被刷额度，建议加 rate limiting |
| 🟡 已知 | OpenAI API key 设月度消费上限 | 平台端已加保护 |
| ✅ 已配 | Cloudflare Web Analytics | ✅ 已配置并部署 |
| 🟢 低 | CORS 允许 localhost | 仅开发环境使用，不影响生产

### 安全审计总结 (2026-06-21)
对 GitHub 公开仓库进行了全面审计，发现并修复了以下问题：

| # | 问题 | 风险 | 处理结果 |
|---|------|------|---------|
| 1 | app.py 硬编码默认密码 mintshovels-admin | 🔴 高 | ✅ 已移除 |
| 2 | GitHub 仓库为公开(Public) | 🔴 高 | ✅ 已设为私有 |
| 3 | Railway 生产地址在公开代码中 | 🟡 中 | ✅ 仓库私有后不再暴露 |
| 4 | SMTP 配置结构在公开代码中 | 🟡 中 | ✅ 仓库私有后不再暴露 |
| 5 | Gmail/GitHub/Twitter 个人账号 | 🟢 低 | 本就是公开社交信息 |
| 6 | OPENAI_API_KEY 等真实密钥 | 🟢 安全 | 仅在 Railway 环境变量中, 未入代码 |

## 十一、变更日志

| 日期 | 变更内容 |
|------|---------|
| 2026-06-21 | 🎉 **Pipeline 全线修复并验证成功**：5步全绿，2个AI工具已生成&部署上线 |
| 2026-06-21 | 🐛 **修复 3 个级联 Bug**：pipeline_run 调用 radar_scan/generate_tool/deploy_tool 时均未传 key，导致全链路 403 |
| 2026-06-21 | 🚀 **取消每日限制**：max_per_day 10 → 999，全网有需求就生产，不限量 |
| 2026-06-21 | 🎨 更新网站 Logo（金色铲子+电路板风格），favicon/icon/og-image 全部替换 |
| 2026-06-21 | 🖼 导航栏左上角图标换为新 Logo favicon（替换 Lucide pickaxe 图标） |
| 2026-06-21 | 📊 Cloudflare Web Analytics 配置完成，令牌存入密钥链 |
| 2026-06-21 | 🔒 GitHub 仓库由公开→私有，阻止代码被外部查看 |
| 2026-06-21 | 🔑 移除硬编码默认密码 mintshovels-admin |
| 2026-06-21 | 🔒 安全加固：7个敏感API加 ADMIN_KEY 认证，无密钥返回403 |
| 2026-06-21 | 🔐 管理后台改为密码登录页，SHA-256验证，源码无明文密码 |
| 2026-06-21 | ⏱ 调度器间隔 6h → 3h（加快新工具上线频率） |
| 2026-06-21 | 🪵 移除日志中的 API key 前缀泄露 |
| 2026-06-21 | 🛡️ mintshovels.com/admin → 密码验证页 → Railway管理面板 |
| 2026-06-21 | ✅ 管理后台 /admin + API 认证加锁 (ADMIN_KEY) |
| 2026-06-21 | ✅ SMTP 邮件通知配置 (Resend) → 许愿池/工具上线可发邮件 |
| 2026-06-21 | ✅ 配置 OpenAI API Key → 调度器启动 → AI 引擎上线 |
| 2026-06-20 | ✅ 更新社交链接 (Twitter/GitHub)，修复雷达离线，部署前端 |
| 2026-06-20 | ✅ 生成项目完整说明书 |

### 网站 Logo 资源清单
| 文件 | 尺寸 | 用途 |
|------|------|------|
| `assets/logo.png` | 200×200 | 首页大 Logo |
| `favicon.png` | 32×32 | 浏览器标签页图标 |
| `favicon.ico` | 多尺寸 | 浏览器兼容 favicon |
| `icon-192.png` | 192×192 | PWA 桌面图标（小） |
| `icon-512.png` | 512×512 | PWA 桌面图标（大） |
| `og-image.png` | 1200×630 | 社交分享预览图 |

> Logo 源文件位置：`/Users/dawei/Desktop/A_minimalist_tech_logo_of..._realistic_photos_shading.png`

### ⚠️ 运维提醒
- OpenAI 后台设月度消费上限，防止 API Key 泄露后超额消费
- 地址：https://platform.openai.com/settings/organization/billing/limits

---

## 十二、审核队列 (风控系统)

### 工作原理
雷达扫描到敏感词需求后自动拦截，存入审核队列等待审批。

### 审核 API
| 操作 | API | 认证 |
|------|-----|------|
| 查看待审数量（公开） | `GET /v1/radar/risk-audit` | 无需 |
| 查看待审详情 | `GET /v1/radar/risk-audit?key=密码` | 需要 ADMIN_KEY |
| 批准/驳回 | `POST /v1/radar/risk-audit/approve?key=密码` | 需要 ADMIN_KEY |
| 管理后台 | `mintshovels.com/admin` → 输入密码 → Railway管理面板 | 本地密码验证（SHA-256） + 后端 ADMIN_KEY |
| 持久化文件 | `待厂长亲自审核清单.txt` | - |

### 🔐 管理后台访问
1. 浏览器打开 **`mintshovels.com/admin`**
2. 输入管理密码 → 自动跳转 Railway 完整管理面板
3. 密码在传输前做 SHA-256 哈希比对，源码中无明文

### ⚠️ 待做
- ~~前端缺少审核操作界面~~ ✅ 已通过 /admin 管理后台解决

### 🔒 安全加固 (2026-06-21)
以下敏感端点已加 ADMIN_KEY 认证，无密钥调用返回 403：
| 端点 | 风险 |
|------|------|
| `POST /v1/pipeline/run` | 触发全自动流水线 |
| `POST /v1/radar/scan` | 全网需求嗅探 |
| `POST /v1/workshop/generate` | 工具代码生成 |
| `POST /v1/workshop/deploy` | 工具部署上线 |
| `POST /v1/workshop/auto-generate` | 批量自动生成 |
| `POST /v1/workshop/config` | 修改工厂配置 |
| `POST /v1/notify/send` | 发送邮件 |
| `POST /v1/scheduler/start` | 启动调度器 |
| `POST /v1/scheduler/stop` | 停止调度器 |

公开端点（无需认证，正常使用）：
- `GET /v1/radar/risk-audit` — 只返回待审数量
- `POST /v1/wish` — 用户许愿
- `POST /v1/search-log` — 搜索日志
- `POST /v1/extract` — 视频提取
- `POST /v1/transcribe` — 语音转文字
- `POST /v1/chatbot/message` — AI客服

## 十三、如何在新对话中使用本文档

1. 将此文件发送给 AI Agent
2. 说明你要做的事情（如"把 Discord 链接替换为 xxx"）
3. AI 会自动定位到对应文件和代码位置进行修改

### 快速指令示例

- "把 Discord 邀请链接改成 https://discord.gg/xxxxx" → 同时修改 `index.html` 和 `app.py`
- "把面包多链接全部替换为 https://mbd.pub/xxx" → 改 `_MONETIZATION` 配置
- "修复雷达离线问题" → 改 `index.html` 中的判断逻辑
- "部署前端到生产环境" → 运行 `npx wrangler pages deploy`
- "推送后端到 GitHub" → 运行 `sync_to_github.command`
- "查看当前变现配置" → 读 `app.py` 的 `_MONETIZATION`

---

## 附：关键代码定位速查

| 要找什么 | 文件 | 大致行号 |
|----------|------|---------|
| 前端 API 地址 | mintshovels-site/index.html | 450 |
| 前端社交链接 | mintshovels-site/index.html | 218-230 |
| 前端 CPS 链接 | mintshovels-site/index.html | 220-227 |
| 前端 AdSense 占位 | mintshovels-site/index.html | 228-234 |
| 前端定价弹窗 | mintshovels-site/index.html | 287-303 |
| 前端信任徽章 | mintshovels-site/index.html | 259-263 |
| 前端雷达判断 | mintshovels-site/index.html | 搜索 `d.status === "patrolling"` |
| 后端全部配置 | tool-factory/app.py | 64-124 |
| 后端变现配置 | tool-factory/app.py | 64-115 (`_MONETIZATION`) |
| 后端 SMTP 配置 | tool-factory/app.py | 118-124 |
| 后端路由定义 | tool-factory/app.py | 搜索 `@app.get` / `@app.post` |
| 后端 Pipeline | tool-factory/app.py | 3263-3460 |
| 后端调度器 | tool-factory/app.py | 搜索 `_scheduler` |
| CI/CD 配置 | mintshovels-site/.github/workflows/deploy.yml | 全文 |
