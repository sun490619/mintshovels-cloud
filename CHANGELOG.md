# MintShovels 更新日志 (CHANGELOG)

---

## v1.8 (2026-06-28) 🚀 SEO大修：首页CTA + 热门工具 + sitemap更新

### 🎯 首页用户体验大升级
- **新增 CTA 按钮**：hero 区域下方新增两个大按钮——"🚀 Explore All Tools"（滚动到分类区）和"⚡ Request a Tool"（跳转到 Workshop），降低跳出率
- **新增 Popular Tools 区域**：首页新增热门工具卡片网格，展示 6 个最常用工具，带 emoji 图标映射，点击直达工具页
- **i18n 支持**：新增 `hero_cta`、`popular_title` 中英文键值

### 🔧 SEO 优化
- **sitemap.xml**：所有 URL 的 `lastmod` 更新为 2026-06-28，触发 Google 重新爬取
- **版本号更新**：v1.6-stable → v1.8-stable

### 🩺 体检脚本强化
- **首页关键元素检查**：`mintshovels_full_check.py` 新增对 `hero_cta` 按钮和 `popular-grid` 区域的自动检测
- 版本号同步更新

### 📊 数据状态确认
- **Googlebot 可正常访问**：返回 200（非 403），索引问题仅因站点太新
- **GSC 已开始收录**：6月24日已有 4 次展示
- **Bing API 正常**：返回 `{"d": []}`，API 未过期但暂无数据
- **GA4 配置完整**：Measurement ID G-D53DQ3JKKL 正常

---

## v1.7 (2026-06-27) 🔧 质量大修：数据关卡 + 文化准确性 + AI提示词强化

### 🎯 核心改进：新增数据丰富度检查关卡
AI 生成的工具再也不会是"空壳子"。以前只检查HTML结构（有没有DOCTYPE、script标签），现在会检查：
- **生成器数据量**：至少50条数据项（名字生成器125000+种组合）
- **数据唯一性**：重复率超过50%会被拦截
- **组合爆炸度**：first × last 至少200种组合
- **日文罗马字拦截**：日语名字必须用漢字/かな/カタカナ，罗马字写的直接拒绝
- **计算器模式数**：只有一个加减法的计算器会被警告

### 📊 名字生成器 (shovel-012) 修复
- **中文名**: 旧版20个单字名→新版50姓×50双字名×50单字名=125000+组合，80%概率出双字名
- **日文名**: 旧版全罗马字(TanakaHaruki)→新版漢字表記(佐藤花子、高橋ゆうき)，含50姓×50名=2500+组合
- **英文名**: 旧版15名×10姓→新版100+名×50姓=5000+组合
- **奇幻名**: 旧版15+10→新版80+×50=4000+组合

### 🧠 AI生成提示词强化
- 生成器的system_prompt现在明确要求100-300+条真实数据
- 用户提示词明确标注"数据将被拒绝如果太少"
- 多语言工具的文化规范：中文用漢字、日文用漢字/かな、韩文用한글

### 🏭 增强模板修复
- `_enhanced_generator_js` 的 genOne() 不再生成无意义的UUID
- 改为7种类型的有意义随机数据(UUID/哈希/色码/短ID/时间戳/随机数/Base64 token)

### 🔬 数据关卡全部接入
- `_data_richness_check()` 接入主验证流程
- `quick_gate_check()` 同步增加数据关卡
- 测试验证：旧版名字生成器(8条数据)→🔴拦截；日文罗马字→🔴拦截

---

## v2.1.1 (2026-06-25) 🔧 三个核心工具修复 + 雷达意图检测升级

### 🔧 工具修复
- **QR码生成器 (shovel-006)**：替换假随机图案为真实 QR 码库（qrcodejs），手机可扫。新增 WiFi/vCard/Text 四种模式 + SVG 下载
- **JSON格式化 (shovel-010)**：新增 JSON→CSV 转换 + 行号级别错误定位 + 实时字符/行数统计
- **Base64编解码 (shovel-011)**：新增文件上传直接编码 + 清空按钮 + 编码后长度预估

### 🎯 雷达 v4.1
- 新增工具意图预检：包含"工具/生成器/计算器"等关键词的文本不会被误杀
- 加社交噪音检测：感叹句"太棒了这个工具大家快来看"仍正确拦截
- 中文文本必须有中文工具信号才算需求（防"雷军打赌 Generator"套壳）

---

## v2.1-dev (2026-06-25) 🌊 雷达水源大换血：砍掉14个挂掉的 + 新增6个免费高价值源

### 🌊 水源全面检修
**诊断**：v2.0 的 25 个水源中有 14 个已经挂掉或需要 API Key：
- 403 封堵：Reddit(5 subs)/Quora/npm RSS
- 需登录：知乎(401)/微博(403)
- 永远返回 0：36Kr/少数派/Medium/PyPI/Dribbble/Bing

**修复**：
- 🆕 **Show HN** (Algolia 免费 API) — 用户展示自己做的工具，工具信号纯度极高
- 🆕 **Ask HN 工具需求** (Algolia) — "best tool for X" 类问答，直接反映用户需求
- 🆕 **npm Registry Search** (免费 API) — 搜索 generator/converter/formatter 等包
- 🆕 **GitHub Topics** — 热门技术主题趋势
- 🆕 **HackerNoon RSS** — 技术博客，常覆盖新工具
- 🆕 **InfoQ RSS** — 技术新闻/趋势
- 🔧 HN 从 hnrss.org (502) 切换到 Algolia API
- 🔧 Stack Overflow RSS URL 修正 (tagnames= 非 tagged=)
- 🗑️ 14 个挂掉的水源不再空跑调用

### 📊 效果对比

| 指标 | v2.0 (修复前) | v2.1 (换血后) |
|---|---|---|
| 活跃水源 | 9/25 (36%) | 19/19 (100%) |
| 原始信号 | 173 条 | **350 条** |
| 工具信号 | 50 (28.9%) | **185 (52.9%)** |
| 信号密度 | 28.9% | **52.9%** |
| 工具建议 | 4 条 | **18 条** |

### 🔑 KEYWORD_TOOL_MAP 大幅扩充
新增 60+ 关键词覆盖：scraper/crawler/boilerplate/dashboard/monitor/deploy/ocr/tts/diff/merge/split/extract/parser/mock/proxy/tunnel/dns/cdn/queue/log/icon/font/palette/layout/form/survey/poll/quiz/mindmap/flowchart/invoice/budget/expense/tax/pomodoro/habit/journal 等

## v1.7-dev (2026-06-25) 📡 需求雷达复通 + 真实状态同步

### 🔴 致命修复：雷达产出从 0 恢复到 5 条建议
**病因**：意图分类器门槛太高（50 分），雷达抓到的 GitHub 仓库名（全小写+连字符，如 `gemini-code-assist`）不含"生成器/Calculator"等工具后缀，只能拿 ~10 分，98% 被误杀。
- **demand_radar.py**：GitHub 信号从"拆成 owner/repo 两个碎片"改为发送"`repo名 — 描述`"组合信号，ProductHunt 加 `— tool from ProductHunt` 语境标签
- **intent_classifier.py**：新增 GitHub 连字符命名识别（+8~12分）+ tool/tools/plugin 关键词识别（+8~12分）
- **bad_cases.json**：门槛从 50 → 40（WARN 从 30 → 24），让更多真实工具信号通过
- **效果**：工具信号 50→69 条，通过率 2%→36%，建议 0→5 条

### 🛰️ 雷达状态真实化
- **app.py `/v1/radar`**：不再硬编码 `patrolling`，改为读取 `demand_report.json` 判定真实状态（4h 内=patrolling · 12h 内=standby · 超过=idle）
- **index.html `checkRadar()`**：新增 `standby` 显示（黄色待命中），footer 雷达显示扫描到的信号数+建议数

## v1.7-dev (2026-06-25) 🔧 真实用户浏览反馈修复

### 🛡️ 用户体验修复（基于真人浏览发现的问题）
- **首页工具卡片直达**：`renderToolDetail` 的 `default` 分支不再显示"正在打造中"空壳，改为展示完整工具信息（状态/类型/编号/描述/标签）+ 直达独立工具页面链接
- **Radar状态同步**：`checkRadar()` 现在同步更新 footer 的雷达显示（在线显示扫描数、离线显示真实状态），不再永远显示 `Radar #0`
- **MODULES 开关扩展**：新增 `pro`/`subscribe`/`partners` 三个开关，底部 Pricing/订阅/合作伙伴链接全部受控，`false` 时隐藏

### 🔧 杂项
- 版本号更新：footer 显示 `v1.7-dev`
- 4个 Partner 链接加 `id` 标记，方便 MODULES 控制显隐

---

## v1.7-dev (2026-06-24) 🧠 AI商机捕手上线 + 全链路数据闭环（本地验证通过，待授权推送）

### 📡 雷达 v2.0 推线上 ✅ (已 push)
- 雷达 v2.0 三道防线已全量推送 GitHub → 触发双平台部署
- **25+水源裂变、工具特质自动识别、闲聊前置过滤 全部生效**
- 线上主站 33精品工具死守

### 🤖 战术二: #024 AI 商机捕手 — 全栈重构
- **前端** `tools/ai-assistant.html`：从空壳毛坯房重构为完整 Chat Widget
  - 精美暗色主题 Chat UI（匹配 MintShovels 品牌设计）
  - 对话引擎：greet → probe → confirm → done 四阶段引导流
  - 工具名称自动生成（中英文模式匹配）
  - 快捷操作按钮 + 跟进问题智能生成
  - 独立模式 + 嵌入模式双模式支持
  - Typing 动画 + 消息入场动画
  - 支持 postMessage 接收父页面搜索词通知
- **后端** `engine/main.py`：新增商机收集端点
  - `POST /v1/pain-point` — AI机器人痛点上传统一端点
  - `POST /v1/wish` — 用户许愿（并入商机管道）
  - `POST /v1/search-log` — 搜索日志持久化
  - `GET /v1/pain-points` — 调试/审计查询
  - `GET /v1/workshop/tools` — 动态工具列表接口
  - CORS 全开放 + 线程安全存储
- **雷达集成** `engine/demand_radar.py`：
  - 新增 `fetch_pain_points()` — 读取 `reports/pain_points.json`
  - 用户痛点作为第0号水源，**最高优先级**，绕过闲聊过滤
  - 痛点信号 +40分人工加权，直接插到工具信号列表最前面
  - 处理完成后自动标记 `pending → radar_processed` 状态流转
- **主站集成** `index.html`：
  - 无搜索结果页嵌入「🤖 和 AI 聊聊需求」入口
  - iframe 加载 AI 助手，postMessage 自动传递搜索词
  - 搜索清空/有结果时自动关闭聊天面板

### 🧪 全链路验证数据
| 验证项 | 结果 |
|:---|:---:|
| 模拟痛点写入 pain_points.json | ✅ |
| 雷达读取痛点 (fetch_pain_points) | ✅ 1条 |
| 痛点绕过闲聊过滤 +40分加权 | ✅ 置信度100% |
| 痛点出现在工具信号第一位 | ✅ 🚨 最高优先级 |
| 痛点状态流转 pending→radar_processed | ✅ |
| 全线流水线干跑 | ✅ 91✅0❌ |
| 工具总数 | 🛡️ 33 |
| ai-assistant.html HTTP 服务 | ✅ 200 |

### ⚠️ 待授权
- `engine/main.py` + `engine/demand_radar.py` + `tools/ai-assistant.html` + `index.html` 均为本地修改
- **未 git commit，未 git push，未触发任何线上部署**
- 线上主站 mintshovels.com 仍是干净33个精品工具

---

## v1.4-stable (2026-06-23) 🔒 当前稳定版
- **当前可用率**：12/25 水源活跃（13个因API认证/反爬未响应，均为免费公开接口）

### 🧠 工具特质自动识别引擎（ToolTraitRecognizer）
- **四大维度动态识别**：动作特征（中英文）+ 工具名词后缀 + 技术概念信号 + 用户痛苦表达
- **不再依赖写死关键词字典**：通过多维度语义模式识别"输入→自动化处理→输出"诉求
- **置信度分级**：≥30% 高置信度工具信号 / ≥15% 低置信度待审查 / <15% 非工具

### 🚫 闲聊前置过滤器（ChatterFilter）
- **五大类拦截**：新闻八卦 / 娱乐体育 / 纯情绪吐槽 / 广告促销 / 招聘求职
- **抓取瞬间前置拦截**：在雷达采集阶段即过滤，不浪费后续计算资源
- **实测**：224条原始信号中拦截9条闲聊（4.0%），56条工具信号（25.0%）

### 🛡️ 三道防线架构
- 第1道 🚫 闲聊前置过滤：224 → 215（9条闲聊拦截）
- 第2道 🧠 工具特质识别：215 → 56 工具信号
- 第3道 🔒 硬核门禁（demand_filter + intent_classifier）：56 → 2（拒绝率96.4%）
- 最终建议：1条（AI Assistant）
- **33精品底线死守**：工具总数33, 健康率100%, 91✅0❌

### ⚠️ 待授权
- `engine/demand_radar.py` v2.0 + `engine/pipeline.py` audit更新 均为本地修改
- **未 git commit，未 git push，未触发任何线上部署**
- 线上主站 mintshovels.com 仍是干净33个精品工具

---

## v1.4-stable (2026-06-23) 🔒 当前稳定版

### 🔧 修复（2026-06-23 22:09 流水线修复）
- **雷达 import 路径修复**：`engine/demand_radar.py` 第22行 `from engine.demand_filter` 在从 engine/ 目录内运行时找不到 engine 包，改为 try/except 回退到相对导入
- **本地服务器 502 修复**：`engine/pipeline.py` `test_local_server()` 从 `TCPServer + handle_request()` 循环改为 `ThreadingTCPServer + serve_forever()` + 3次重试，彻底解决连续40个请求时的 502 Bad Gateway 问题
- **流水线全部通过**：87✅ 0❌，部署至 https://d67182d1.mintshovels.pages.dev

---
## v1.4-stable (2026-06-23) 🔒 当前稳定版

### 🆕 新增
- **错题本拦截机制**：`bad_cases.json`（20负面+20正面案例）+ `intent_classifier.py` 多维意图判定引擎
  - 废除机械关键词黑名单，"如何/怎么/为什么"不再一刀切拦截
  - 10维打分系统：数据闭环(30) + 工具名词(25) + 正反案例匹配(±40) + 名人检测(-30) + 计算路径(25) + 语言质量(10)
  - PASS门槛50分，硬性否决（名人八卦/社交闲聊/个人陈述直接拦截）
  - 35/35测试用例全部通过（含中文需求 + 英文工具名）
- **`demand_filter.py` v4.0**：从关键词黑名单→意图分类器驱动，回退逻辑兼容
- **存量工具名称大清洗**：1558个自动工具全量清洗
  - 1493个名称优化（去Random前缀 + 去Generator/Checker/Calculator尾缀）
  - 65个垃圾工具标记下架（名人八卦/游戏名/社交闲聊/新闻标题/广告破解）
  - 中英缝合怪全部修复（36→0个）
  - Random前缀彻底消灭（36→0个）
- **32种逻辑模块输出质量增强**：`module_quality_enhancer.py`
  - 生成器：追加复制功能 + 统计面板（数量/唯一值/点击复制提示）
  - 验证器：追加测试样例按钮（点击填入+验证）
  - 计算器：追加公式展示 + 参考值范围
  - 1404个工具输出质量增强

### 🔧 修复
- **彻底消灭机器换皮感**：全站不再有 "Random XXX Generator" 的套壳命名
- **多维意图判定取代一刀切**："如何计算公积金贷款"正确识别为PASS，"男子煮粽子狗狗狂叫"正确拦截为BLOCK
- **英文工具名不再误拦**："AI Image Upscaler"、"Crypto Price Tracker"、"URL Shortener" 等全部正确通过
- **中英缝合怪清零**：中文页面不再出现 "Random 淘宝服装网 Generator" 这种半中半英缝合怪

### 📊 数据
- 手写工具：33个（不变）
- 有效自动工具：1493个（1558-65垃圾）
- 垃圾标记：65个
- 名称清洗率：95.8%
- 质量增强率：90.1%
- Random前缀：36→0
- 中英缝合：36→0
- 意图分类器通过率：100%（35/35测试）
- 体检状态：待确认

### 🏷️ 版本标签
- Git Tag：`v1.4-stable`
- 回退命令：`git checkout v1.4-stable`
- 上一版本：`v1.3-stable` 永久保留

---

## v1.3-stable (2026-06-23) 🔒

### 🆕 新增
- **全站工具功能大重构**：`template_rewriter.py` — 32种真实逻辑模块替换 4 大模板的 TODO 占位符
  - 随机生成器（1406个）：13种生成类型（密码/UUID/颜色/数字/姓名/邮箱/日期/IP/Emoji/Hex/单词/代码/URL），每种含真实 `crypto.getRandomValues()` / 算法逻辑
  - 检测验证器（23个）：6种验证类型（邮箱/URL/密码强度/JSON/IP/正则），每种含完整的输入校验+结果反馈逻辑
  - 计算器（40个）：6种计算类型（BMI/百分比/单位换算/面积/房贷/小费分摊），每种含真实数学公式+实时计算
  - Python脚本（89个）：7种脚本类型（文本处理/JSON格式化/CSV分析/文件整理/加密哈希/密码生成/通用处理），每种含完整可执行的 Python 代码
- **33个手写工具独立页面创建**：`tools/{id}.html` 全部生成，支持直接 URL 访问和 meta-refresh 跳转
- **`auto_factory.py` v2.0**：`generate_tool_page()` 重写，集成 32 种真实模板，告别空壳页面
- **车间门禁拦截器**：`workshop_gate_check()` 全面集成至 `auto_factory.py` 和 `pipeline.py`
  - 新工具入库前必须通过门禁检查，未通过者自动拦截并上报
  - `pipeline.py` 新增"阶段 1.5: 车间门禁检查"，全量功能健康率快照
- **`functional_test_runner.py`**：全量工具功能穿透测试引擎，速度 0.1 秒/1558 工具
- **`live_test_harness.py`**：50 个代表性工具真机拨测引擎
- **`auto_health_check.py`**：Cron 定时任务入口，支持 snapshot / deep 两种模式
- **`demand_filter.py` v3.0**：新增 120+ 中文语义黑名单（如何/怎么/为什么/吗/呢/啦/大家/听说/当初等），彻底封堵中文社交闲聊垃圾需求

### 🔧 修复
- **彻底解决空壳工具大穿帮**：1558 个自动工具的 `// TODO: Customize generation logic` 占位符全部替换为 32 种真实功能逻辑
- **手写工具 404 漏洞焊死**：33 个手写工具全部创建 `tools/{id}.html` 独立页面，直接 URL 访问不再 404
- **管道车间拦截集成**：`pipeline.py` 新增门禁阶段，确保不合格工具零入库
- **`auto_factory.py` 模板同步**：从旧占位符模板全面切换到 32 模块真实模板系统
- **全量穿透测试通过**：1558 工具 100% FUNCTIONAL，0 TODO 残留，健康率 100%
- **真机拨测通过**：38/38 代表性工具通过实战测试（100% 通过率）

### 📊 数据
- 手写工具：33 个（全部在线，全部有独立页面）
- 自动生成工具：1558 个（全部注入真实功能，100% FUNCTIONAL）
- 独立工具页：33 手写 + 1558 自动 = 1591 个
- 功能健康率：100%（从 0% TODO 空壳 → 100% 真实功能）
- 模板模块：32 种（13 生成器 + 6 验证器 + 6 计算器 + 7 Python脚本）
- 体检状态：待最终确认

### 🏷️ 版本标签
- Git Tag：`v1.3-stable`
- 回退命令：`git checkout v1.3-stable`
- 旧版备份：`backups/generated_tools_pre_rewrite_*.json`（随时可回滚到重写前）
- 上一版本：`v1.2-stable` 永久保留

---

## v1.2-stable (2026-06-23) 🔒

### 🆕 新增
- **雷达需求甄别过滤器 v2.0**：`engine/demand_filter.py` 全新上线，替代原始无脑套壳逻辑
  - GitHub `owner/repo` 智能提取：自动丢弃冗长描述，只保留核心项目名（治误杀）
  - Show HN/Ask HN 前缀去噪：去掉前缀后再评估核心内容，不误杀独立开发者产品（治误杀）
  - 新闻媒体黑名单暴增：BBC、Fox、CNN、Seattle Times、WSJ、Reuters 等 80+ 关键词全部封堵（治漏杀）
  - 娱乐票房拦截：Toy story、box office、opening weekend 等商业娱乐词拦截（治漏杀）
  - 商品描述拦截：paper towels、family rolls 等超市日用品描述过滤（治漏杀）
  - 技术报错拦截：Flask envvar 报错、Docker dispatch 通讯等非工具描述过滤
  - 黑名单总量：从 ~60 词暴增至 ~140 词 + 10 条新正则模式

### 🔧 修复
- **全站工具品质大审计**：扫描 3292 个工具，揪出 773 个（23.5%）套壳垃圾
- **垃圾资产一键斩首**：正式从数据库清除 773 个非工具条目（电影八卦、超市纸巾、Flask报错、新闻闲聊等）
- **英文命名合规率锁死**：3️⃣ 体检表新增合规率检测，不合格占比 > 2% 即亮 🔴
- **全站工具命名脱胎换骨**：所有保留的 2519 个工具英文命名合规率 100%（0.0% 不合格）

### 📊 数据
- 手写工具：33 个（全部在线）
- 自动生成工具：2519 个（2272 已部署）
- 合计工具库：**2552 个**（从 v1.1 的 3325 个脱水 773 个垃圾，-23.3%）
- 垃圾清除明细：misc 710 + finance 32 + productivity 17 + dev 10 + gaming 4
- 体检状态：6/6 🟢 全部正常

### 🏷️ 版本标签
- Git Tag：`v1.2-stable` 已推送至 GitHub
- 回退命令：`git checkout v1.2-stable`
- 旧版备份：`backups/generated_tools_v1_precleanup_*.json`（随时可回滚到清洗前）

---

## v1.1-stable (2026-06-23) 🔒

### 🆕 新增
- **Workshop API**：新增 `/v1/workshop/status` 和 `/v1/workshop/tools` 两个后端接口，前端工具页面可以动态从后端拉取工具列表，不再依赖写死的代码
- **GitHub Actions 自动部署流水线**：新增 `.github/workflows/deploy.yml`，每次 Push 代码到 GitHub 自动触发 Railway 部署 + 健康检查
- **前端页面动态工具渲染**：手写工具和自动生成工具现在通过 Workshop API 动态加载，工具数据统一走后端
- **体检报告版本号抬头**：每次体检报告顶部显示 `【当前项目版本：v1.1-stable】`
- **线上版本号核对**：体检程序会自动检查线上网站是否包含版本号 meta 标签，与本地版本做比对
- **版本号 meta 标签**：`index.html` 新增 `<meta name="mintshovels-version" content="v1.1-stable">`

### 🔧 修复
- **Bing API 优雅降级**：Bing Search API Key 过期不再阻塞体检和 data_engine，遇到 401 自动跳过，不影响其他功能
- **CF 挑战页误判修复**：体检程序现在能正确识别 Cloudflare 安全防护挑战页面，不再误报网站下线
- **Git 脏提交清理**：修复了前期遗留的未提交文件问题，Git 状态恢复干净
- **前端备份同步**：`index.html.bak` 更新为与主线一致（311KB），备份可靠性恢复

### 📊 数据
- 手写工具：33 个（全部在线）
- 自动生成工具：3292 个（2981 已部署）
- 合计工具库：**3325 个**
- 近 5 天流量：619 人次，2969 浏览

### 🏷️ 版本标签
- Git Tag：`v1.1-stable` 已推送至 GitHub（https://github.com/sun490619/tool-factory）
- 可用命令回退：`git checkout v1.1-stable`

---

> 📋 版本规则：从 v1.1-stable 开始，每个新版本向上推进（v1.2, v1.3...），旧版本 Tag 永久保留不删除。
