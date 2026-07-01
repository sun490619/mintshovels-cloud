# MintShovels 基础设施复用清单

> 从工具站迁移到内容站，哪些留、哪些改、哪些丢

---

## ✅ 直接复用（不动或微调）

| 文件 | 原用途 | 内容站用途 |
|------|--------|----------|
| `_headers` | Cloudflare Pages 安全头 | 直接复用 |
| `robots.txt` | 爬虫规则 | 更新 sitemap 路径 |
| `sitemap.xml` | SEO 站点地图 | 重新生成（文章 URL） |
| `sw.js` | PWA Service Worker | 直接复用 |
| `manifest.json` | PWA 配置 | 更新名称/描述 |
| `favicon.ico` / `favicon.png` | 网站图标 | 更新为新品牌图标 |
| `icon-192.png` / `icon-512.png` | PWA 图标 | 稍后更新 |
| `og-image.png` / `og-image.svg` | 社交分享图 | 更新设计 |
| `.github/workflows/tool-tests.yml` | 自动测试 | 改造为内容站 CI/CD |
| `api-config.js` | API 配置 | 更新 API 端点 |
| `package.json` | npm 依赖 | 保留 serve 等依赖 |
| `mintshovels_full_check.py` | 体检脚本 | 改造为内容站体检 |
| `data_engine.py` | 数据聚合引擎 | 保留（分析流量） |
| `dashboard.html` / `dashboard_server.py` | 监控面板 | 保留改造 |
| `analytics_history.json` | 历史流量数据 | 保留存档 |
| `health_snapshot.json` | 健康快照 | 保留 |

---

## 🔄 可改造复用

| 文件 | 原用途 | 内容站改造方案 |
|------|--------|-------------|
| `engine/demand_radar.py` | 全网需求扫描 | → **关键词雷达**：搜 Google 热门搜索词 |
| `engine/demand_filter.py` | 需求过滤 | → **话题过滤器**：筛掉非内容站话题 |
| `engine/intent_classifier.py` | 意图分类 | → **内容类型分类器**：教程/评测/列表 |
| `engine/pipeline.py` | 工具生成流水线 | → **内容生产流水线**：雷达→AI写→人审→发布 |
| `index.html` | 工具站首页 | → **完全重写**为内容站首页 |
| `app.py` | FastAPI 后端 | → 精简，只保留数据/健康/雷达 API |
| `test_tools.mjs` | Playwright 工具测试 | → 改造为内容页加载测试 |
| `auto_health_check.py` | 定时体检 | → 内容站自动体检 |
| `mintshovels_monitor.py` | 网站监控 | → 保留，更新 URL |

---

## 🗑️ 不再需要（已归档/待清理）

| 文件 | 原因 |
|------|------|
| `tools_archive/` (77个HTML) | ✅ 已归档，随时可查看 |
| `tool_generator.py` | 工具生成逻辑，内容站不需要 |
| `template_rewriter.py` | 工具模板重写器，不需要 |
| `garbage_tool_scanner.py` | 垃圾工具扫描，不需要 |
| `functional_test_runner.py` | 工具功能测试，不需要 |
| `live_test_harness.py` | 工具真机测试，不需要 |
| `module_quality_enhancer.py` | 工具质量增强，不需要 |
| `tool_name_cleaner.py` | 工具名称清洗，不需要 |
| `auto_extract_ids.py` | ID 提取，不需要 |
| `generated_tools_log.json` | 自动工具日志，归档即可 |
| `build_safeguard_report.json` | 安全报告，归档 |
| `bad_cases.json` | 工具站错题本，保留思路 |
| `mistake_book.json` | 工具站错题本，保留思路 |
| `review_queue.json` | 审核队列，不需要 |
| `demand_report.json` | 需求报告，不需要 |
| `scraper_cache.json` / `scraper_seen.json` | 抓取缓存，不需要 |
| `test_results.json` | 测试结果，归档 |
| `functional_test_report.json` | 功能测试报告，归档 |
| `live_test_report.json` | 真机测试报告，归档 |
| `garbage_audit_report.json` | 垃圾审计报告，归档 |
| `dashboard_data.json` | 仪表盘数据，保留 |
| `pipeline_output.txt` | 流水线输出，归档 |
| `demand_pipeline.py` | 需求流水线，不需要 |
| `demand_scraper.py` | 需求抓取，不需要 |
| `demand_filter.py` | 需求过滤，保留在 engine/ |
| `intent_classifier.py` | 意图分类，保留在 engine/ |
| `llm_intent_classifier.py` | LLM 意图分类，保留在 engine/ |
| `pain_point_search.py` | 痛点搜索，不需要 |
| `mintshovels_dashboard.py` | 独立仪表盘，不需要 |
| `setup_cloudflare.py` | CF 配置脚本，归档 |
| `mintshovels_config.json` | 项目配置，更新后保留 |
| `com.mintshovels.pipeline.plist` | macOS 定时任务 | → 更新为内容站定时任务 |
| `start_pipeline.sh` / `run_full_pipeline.sh` | 流水线启动 | → 更新为内容站启动 |
| `sync_to_github.command` / `.bat` | Git 同步脚本 | ✅ 保留 |
| `setup_launchd.sh` | macOS 定时任务设置 | → 更新 |
| `SETUP_GUIDE.md` | 部署指南 | → 更新为内容站部署指南 |
| `VERSION_v1.6_MILESTONE.md` | 版本里程碑 | 归档留存 |

---

## 💎 核心资产保留

| 资产 | 说明 |
|------|------|
| GitHub 仓库 | 保留全部 Git 历史，所有版本 Tag 不动 |
| Cloudflare Pages 部署 | 继续用，域名为 mintshovels.com |
| 域名 | mintshovels.com（$12 成本），不卖不改 |
| Git Tags | v1.1 ~ v1.8 全部保留，可随时回退 |
| 项目说明书 | `MintShovels_项目完整说明书.md` 保留 |
| 复盘文档 | `MintShovels_项目复盘_20260630.md` ✅ 已创建 |
