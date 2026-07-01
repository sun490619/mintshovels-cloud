# 建站通用工具箱

> **这是什么**：以后不管建工具站、内容站、还是别的什么站，翻这一份就够了。  
> **怎么用**：别从头看到尾。需要配什么翻哪章就行。开工前看第二部分。  
> **来源**：MintShovels v1.0-v1.8 实战踩坑全记录  
> **最后更新**：2026-06-30

---

## 目录

### 第一部分：通用工具箱（换项目直接拿来用）

- [1. 托管与域名：Cloudflare 全家桶方案](#1-托管与域名cloudflare-全家桶方案)
- [2. 分析套件：五件套怎么配](#2-分析套件五件套怎么配)
- [3. 前端技术栈：用什么、为什么](#3-前端技术栈用什么为什么)
- [4. 安全头与 SEO 模板](#4-安全头与-seo-模板)
- [5. PWA 模板：manifest + Service Worker](#5-pwa-模板manifest--service-worker)
- [6. CI/CD 模板：GitHub Actions](#6-cicd-模板github-actions)
- [7. AI 调用链：多层模型 fallback 模式](#7-ai-调用链多层模型-fallback-模式)
- [8. 监控体检模板](#8-监控体检模板)
- [9. 版本管理规范：Tag + CHANGELOG](#9-版本管理规范tag--changelog)
- [10. 本地自动化：macOS launchd 模板](#10-本地自动化macos-launchd-模板)
- [11. 设计系统：双主题 CSS 变量](#11-设计系统双主题-css-变量)
- [12. 外部服务总清单](#12-外部服务总清单)

### 第二部分：决策框架（开工前想清楚）

- [13. 开工前 5 件必做](#13-开工前-5-件必做)
- [14. 变现模式选择](#14-变现模式选择)
- [15. AI 批量适用判断](#15-ai-批量适用判断)
- [16. 死线与止损](#16-死线与止损)

### 附录：MintShovels 项目快照

- [A. 项目资产清单（文件级）](#a-项目资产清单文件级)
- [B. 从工具站到内容站：迁移对照](#b-从工具站到内容站迁移对照)

---

## 1. 托管与域名：Cloudflare 全家桶方案

### 为什么全用 Cloudflare

- **一个账号管一切**：域名、DNS、CDN、安全、分析、边缘计算全在一个面板
- **免费额度够小站用**：Pages 无限带宽、Workers 10万次/天、D1 5GB、KV 1GB
- **全球 CDN 自带**：不需要再配 CDN
- **自动 HTTPS**：不用自己搞证书

### 域名

```
在哪买：Cloudflare Registrar（$10-15/年，按成本价）
好处：直接配 DNS，不需要等 NS 生效
如果域名在别处：把 NS 指向 Cloudflare，DNS 面板照用
```

### 前端托管：Cloudflare Pages

```yaml
连接方式：直接连 GitHub 仓库
构建：纯静态不需要构建命令；如果有构建步骤填 npm run build
输出目录：/ 或 dist/
自动部署：git push 即触发
自定义域名：在 Pages 面板绑，自动配 SSL
```

### 后端（如果需要）

```
优先级从高到低：

1. 不需要后端 ✅ 最佳方案
   纯静态 HTML + 前端 JS，能解决绝大多数需求

2. Cloudflare Workers ⭐ 推荐
   免费 10 万次/天，全球边缘节点执行
   适合：API 代理、表单处理、简单的 CRUD

3. Cloudflare D1 + Workers
   需要数据库时的免费方案
   D1 5GB 存储 + Workers 边缘计算

4. Railway / Fly.io / Render
   需要完整 Python/Node 后端时才用
   注意：$5/月起，小站不划算
```

### Cloudflare Zaraz（服务端加载第三方脚本）

```
干什么的：把 GA4、Clarity 等第三方脚本从客户端搬到 Cloudflare 边缘执行
好处：页面加载更快（少加载几十KB的第三方JS）
怎么配：
  1. CF Dashboard → Zaraz → 添加工具
  2. 选 Google Analytics 4，填 Measurement ID
  3. 添加触发条件（比如排除测试流量）
  4. 前端不用再放 gtag.js
```

---

## 2. 分析套件：五件套怎么配

每个工具解决一个问题，组合起来全覆盖：

```
┌─────────────────────────────────────────────────┐
│  CF Web Analytics ─── 基础流量（PV/UV/来源/国家）  │
│  免费、无采样、隐私友好                           │
├─────────────────────────────────────────────────┤
│  Google Analytics 4 ── 深度行为（事件/转化/漏斗）  │
│  免费、功能强大、但学习曲线陡                     │
├─────────────────────────────────────────────────┤
│  Google Search Console ── 搜索表现（关键词/排名）  │
│  免费、必装、SEO 核心数据                         │
├─────────────────────────────────────────────────┤
│  Bing Webmaster Tools ── 必应搜索表现             │
│  免费、流量小但有、顺便做了不亏                   │
├─────────────────────────────────────────────────┤
│  Microsoft Clarity ── 用户录屏 + 热力图 + 点击追踪│
│  免费、不限流量、能看到用户真实操作               │
└─────────────────────────────────────────────────┘
```

### 配置步骤

```
1. CF Web Analytics
   → Cloudflare Dashboard → Web Analytics → 添加站点
   → 复制 JS snippet 放到 <head>
   → 搞定

2. Google Analytics 4
   → analytics.google.com → 创建账号/媒体资源
   → 获取 Measurement ID（格式：G-XXXXXXXXXX）
   → 通过 CF Zaraz 服务端加载（推荐）或用 gtag.js 客户端加载

3. Google Search Console
   → search.google.com/search-console → 添加资源
   → 验证域名所有权（用 DNS TXT 记录，Cloudflare 一键）
   → 提交 sitemap.xml
   → 等 2-3 天开始有数据

4. Bing Webmaster Tools
   → bing.com/webmasters → 添加站点
   → 可从 GSC 一键导入（省事）

5. Microsoft Clarity
   → clarity.microsoft.com → 新建项目
   → 获取 Project ID → 嵌入 JS snippet
   → 即开即用，无需等待

测试模式（开发时不污染数据）：
  URL 加 ?test=1 → 设置 cookie mntest=1
  → Zaraz 触发条件配 "Cookie mntest ≠ 1"
  → 测试时不触发任何追踪
```

---

## 3. 前端技术栈：用什么、为什么

### 选型原则

```
1. 零构建步骤 → 不需要 webpack/vite，写完扔上去就能跑
2. CDN 加载 → 不打包依赖，HTML 里直接引
3. 单文件或少量文件 → 维护简单，不需要复杂的目录结构
4. 自带暗色模式 → 现在用户期待的功能
```

### 推荐组合

```
CSS 框架   → Tailwind CSS（CDN 版本）
  为什么：utility-first，写起来快，自带暗色模式支持
  版本：3.x CDN
  地址：https://cdn.tailwindcss.com

图标库    → Lucide Icons（CDN 版本）
  为什么：开源、轻量、图标全、风格统一
  版本：最新稳定版
  地址：https://unpkg.com/lucide@latest

字体      → 系统字体栈
  为什么：零加载时间，不依赖 Google Fonts
  推荐：system-ui, -apple-system, sans-serif
  等宽：'Geist Mono', 'JetBrains Mono', monospace

其他      → 需要什么用什么（QRCode.js、Chart.js 等）
  原则：只引 CDN，不 npm install
```

### SPA 单文件架构（小型站推荐）

```
一个 index.html 搞定全站：
  - <style> 块：全局 CSS + 组件样式
  - <body>：HTML 结构
  - <script>：全部 JS 逻辑
  
  好处：部署简单（一个文件），不用构建
  适用：页面数 < 50、不需要路由的站
  不适用：复杂交互、多页面、需要 SSR 的站
```

### 什么时候不该用 SPA

```
页面超过 50 个 → 考虑静态站点生成器（Hugo/Astro/11ty）
需要 SEO 深度优化 → SSR 或静态生成
多人维护 → 需要模块化，拆文件
```

---

## 4. 安全头与 SEO 模板

### _headers 文件（Cloudflare Pages）

直接抄，改三个地方：域名、CDN 域名、后端 API 地址。

```
/*
  Content-Security-Policy: default-src 'self'; 
    script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com;
    style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com;
    img-src 'self' data: https:;
    connect-src 'self' https://你的后端地址;
    frame-ancestors 'none'
  Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=()

/admin/*
  Cache-Control: no-store

/404.html
  Cache-Control: public, max-age=3600
  X-Robots-Tag: noindex
```

### robots.txt

```
User-agent: *
Allow: /
Sitemap: https://你的域名/sitemap.xml
```

### sitemap.xml（示例结构）

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://你的域名/</loc>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://你的域名/分类页/</loc>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>
  <!-- 每个页面一个 <url> 块 -->
</urlset>
```

### 页面 SEO Meta 模板

直接放 `<head>` 里：

```html
<!-- 基础 SEO -->
<title>页面标题 - 网站名</title>
<meta name="description" content="150字以内的页面描述">
<meta name="keywords" content="关键词1, 关键词2, 关键词3">

<!-- Open Graph（社交分享用） -->
<meta property="og:title" content="页面标题">
<meta property="og:description" content="页面描述">
<meta property="og:image" content="https://你的域名/og-image.png">
<meta property="og:url" content="https://你的域名/页面路径">
<meta property="og:type" content="website">

<!-- Twitter Card -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="https://你的域名/og-image.png">

<!-- 结构化数据（JSON-LD，帮助搜索引擎理解页面） -->
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "WebApplication",  // 或 Article / FAQ / HowTo 等
  "name": "应用名",
  "description": "描述",
  "url": "https://你的域名"
}
</script>
```

### og-image（社交分享图）

```
尺寸：1200 x 630 px
内容：Logo + 网站名 + 一句话描述
格式：PNG
放根目录：/og-image.png
建议：做一个 SVG 模板，改文字就能生成
```

---

## 5. PWA 模板：manifest + Service Worker

### manifest.json

```json
{
  "name": "网站全名",
  "short_name": "简称",
  "start_url": "/",
  "display": "standalone",
  "theme_color": "#09090b",
  "background_color": "#09090b",
  "icons": [
    {
      "src": "/icon-192.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any maskable"
    },
    {
      "src": "/icon-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any maskable"
    }
  ]
}
```

### sw.js（Service Worker 模板）

```javascript
const CACHE_NAME = 'site-cache-v1';
const PRE_CACHE = ['/', '/index.html', '/manifest.json'];

// 安装：预缓存核心文件
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(PRE_CACHE))
  );
});

// 激活：清理旧缓存
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
});

// 请求：缓存优先，网络回退
self.addEventListener('fetch', e => {
  // 跳过 admin 路径和 Chrome 扩展
  if (e.request.url.includes('/admin/') || !e.request.url.startsWith('http')) return;
  
  e.respondWith(
    caches.match(e.request).then(cached =>
      cached || fetch(e.request).then(resp => {
        if (resp.ok) {
          const clone = resp.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(e.request, clone));
        }
        return resp;
      })
    )
  );
});
```

### PWA 图标

```
需要准备：
  icon-192.png  (192×192)
  icon-512.png  (512×512)
  favicon.ico   (32×32，浏览器标签)
  favicon.png   (备用)
  icon.svg      (矢量源文件，方便以后缩放)

HTML <head> 引用：
  <link rel="manifest" href="/manifest.json">
  <link rel="icon" type="image/x-icon" href="/favicon.ico">
  <link rel="apple-touch-icon" href="/icon-192.png">
  <meta name="theme-color" content="#09090b">
```

---

## 6. CI/CD 模板：GitHub Actions

### 自动部署（push 即部署到 Cloudflare Pages）

```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]
  workflow_dispatch:

concurrency:
  group: production-deploy
  cancel-in-progress: false

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      # 可选：构建安全校验
      - name: Build safeguard
        run: python3 scripts/build_safeguard.py
      
      # 部署到 Cloudflare Pages
      - name: Deploy to Cloudflare Pages
        uses: cloudflare/wrangler-action@v3
        with:
          apiToken: ${{ secrets.CF_API_TOKEN }}
          accountId: ${{ secrets.CF_ACCOUNT_ID }}
          command: pages deploy . --project-name=你的项目名
```

### 定时体检

```yaml
# .github/workflows/health-check.yml
name: Health Check
on:
  schedule:
    - cron: '0 */6 * * *'  # 每6小时
  workflow_dispatch:

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install requests
      - run: python3 health_check.py
      # 把体检结果提交回仓库
      - run: |
          git config user.name "health-bot"
          git config user.email "bot@health"
          git add health_snapshot.json
          git diff --staged --quiet || git commit -m "体检快照 $(date +%Y%m%d-%H%M)"
          git push
```

### Secrets 需要配的

```
GitHub 仓库 → Settings → Secrets and variables → Actions：

CF_API_TOKEN        Cloudflare API Token（Pages 部署权限）
CF_ACCOUNT_ID       Cloudflare 账号 ID
GEMINI_API_KEY      如果用了 Gemini
DEEPSEEK_API_KEY    如果用了 DeepSeek
```

---

## 7. AI 调用链：多层模型 fallback 模式

### 核心思路

```
不依赖单一 AI 模型 → 多个模型按优先级排队 → 前面的挂了自动切后面的

优先级设计原则：
  1. 本地免费（Ollama）→ 最快、不要钱
  2. 云端免费（Gemini → HuggingFace）→ 次快、免费
  3. 自费便宜（DeepSeek）→ 兜底、便宜
  4. 最后备选（OpenAI/Claude）→ 保底、贵但可靠
```

### Python 实现骨架

```python
# ai_client.py 核心逻辑
import requests, json, os

class AIClient:
    """AI 统一客户端：自动 fallback"""
    
    MODELS = [
        ('ollama', 'http://localhost:11434/api/generate'),
        ('gemini', 'https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent'),
        ('huggingface', 'https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct'),
        ('deepseek', 'https://api.deepseek.com/v1/chat/completions'),
        ('openai', 'https://api.openai.com/v1/chat/completions'),
    ]
    
    def generate(self, prompt: str, max_tokens=2000) -> str:
        for model_name, endpoint in self.MODELS:
            try:
                result = self._call(model_name, endpoint, prompt, max_tokens)
                if result:
                    return result
            except Exception as e:
                print(f"[{model_name}] 挂了: {e}")
                continue
        raise Exception("所有模型都挂了")
    
    def _call(self, model, endpoint, prompt, max_tokens):
        # 根据 model 类型构造不同的请求
        if model == 'ollama':
            return self._ollama(endpoint, prompt)
        elif model == 'gemini':
            return self._gemini(endpoint, prompt)
        # ... 其他模型
```

### 关键教训

```
1. 每个模型 API 格式不同 → 封装在 _call 里，对外统一接口
2. 免费额度有限 → Gemini 每天 1500 次，HuggingFace 有速率限制
3. timeout 必须设 → 别让一个模型卡死整个流水线
4. 成本和速率要监控 → 打印每次调用的模型名和耗时
5. 别全自动无监管 → AI 跑完人看一眼再上线
```

---

## 8. 监控体检模板

### 体检脚本骨架

```python
#!/usr/bin/env python3
"""网站健康体检：每一项返回 🟢正常 / 🔴异常"""
import requests, json, sys, os
from datetime import datetime

class HealthChecker:
    def __init__(self, domain, backend_url=None):
        self.domain = domain
        self.backend_url = backend_url
        self.results = []
    
    def check(self, name, condition, detail=""):
        status = "🟢正常" if condition else "🔴异常"
        self.results.append({
            "name": name, "status": status,
            "detail": detail, "time": datetime.now().isoformat()
        })
    
    def run_all(self):
        # 1. 网站可达性
        try:
            r = requests.get(f"https://{self.domain}", timeout=10)
            self.check("网站首页", r.status_code == 200, f"HTTP {r.status_code}")
        except Exception as e:
            self.check("网站首页", False, str(e)[:100])
        
        # 2. HTTPS 证书
        try:
            r = requests.get(f"https://{self.domain}", timeout=10)
            self.check("HTTPS", True, "证书有效")
        except:
            self.check("HTTPS", False, "证书异常")
        
        # 3. 后端（如果有）
        if self.backend_url:
            try:
                r = requests.get(self.backend_url, timeout=10)
                self.check("后端服务", r.status_code == 200, f"HTTP {r.status_code}")
            except Exception as e:
                self.check("后端服务", False, str(e)[:100])
        
        # 4. 自定义检查（按项目需求加）
        # self.check("工具数量达标", len(tools) >= min_count)
        # self.check("最新内容时间", hours_since_last < 24)
        
        return self.results
    
    def report(self):
        for r in self.results:
            print(f"  {r['status']} {r['name']}: {r['detail']}")
        bad = [r for r in self.results if r['status'] == '🔴异常']
        print(f"\n结果: {len(self.results)-len(bad)}正常 / {len(bad)}异常")
        return len(bad) == 0

if __name__ == '__main__':
    checker = HealthChecker(domain="你的域名.com")
    checker.run_all()
    checker.report()
    
    # 保存快照
    with open('health_snapshot.json', 'w') as f:
        json.dump({"results": checker.results, "time": datetime.now().isoformat()}, f)
```

### 定时运行

```
方式 1：GitHub Actions（推荐）
  在 health-check workflow 里跑，每次提交快照到仓库
  好处：免费、不需要自己服务器

方式 2：macOS launchd
  本地 Mac 每 6 小时跑一次
  plist 配在 ~/Library/LaunchAgents/

方式 3：crontab（Linux 服务器）
  0 */6 * * * cd /path && python3 health_check.py
```

---

## 9. 版本管理规范：Tag + CHANGELOG

### Git Tag 策略

```bash
# 每个稳定版本打 tag
git tag v1.0-stable
git tag v1.1-stable
# ...

# 推送 tag
git push --tags

# 回退到任意历史版本（一秒搞定）
git checkout v1.1-stable

# 关键原则：
# ✅ 每个版本独立 tag，不覆盖旧 tag
# ✅ 命名用 vX.Y-stable，清晰表达"这是一个稳定节点"
# ❌ 绝不用 git push --force
# ❌ 绝不删除旧 tag
```

### CHANGELOG.md 规范

```markdown
# CHANGELOG

## v1.2 (2026-07-05)
### 新增
- 加了文章搜索功能，支持标题和正文全文搜索

### 修改
- 首页加载速度从 3.2s 优化到 0.8s
- 修复移动端导航栏被截断的问题

### 移除
- 删了没人用的 PDF 工具分类

## v1.1 (2026-07-01)
...
```

```
原则：
✅ 每句话用大白话，对着未来自己说话的语气
✅ 每条写具体改了什么，不写"优化了性能"这种废话
✅ 有新增、修改、移除三个分类就够
❌ 不写技术实现细节（commit message 干的事）
❌ 不凑字数，没改动就不写
```

---

## 10. 本地自动化：macOS launchd 模板

### .plist 文件模板

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.你的项目.pipeline</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/path/to/你的脚本.py</string>
        <string>--max</string>
        <string>3</string>
    </array>
    
    <key>WorkingDirectory</key>
    <string>/path/to/项目目录</string>
    
    <key>StartInterval</key>
    <integer>10800</integer>  <!-- 3小时 = 10800秒 -->
    
    <key>StandardOutPath</key>
    <string>/path/to/pipeline.log</string>
    
    <key>StandardErrorPath</key>
    <string>/path/to/pipeline.err</string>
    
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
```

### 安装与常用命令

```bash
# 安装（放到 LaunchAgents 目录）
cp com.项目.plist ~/Library/LaunchAgents/

# 加载
launchctl load ~/Library/LaunchAgents/com.项目.plist

# 手动触发一次
launchctl start com.项目.pipeline

# 查看状态
launchctl list | grep 项目

# 停止
launchctl unload ~/Library/LaunchAgents/com.项目.plist

# 看日志
tail -f pipeline.log
```

### GitHub Actions vs launchd 选哪个

```
用 GitHub Actions（推荐）：
  ✅ 免费、不需要自己机器一直开着
  ✅ 日志在 GitHub 上随时看
  ❌ 最多 6 小时执行时间
  ❌ 定时精度 ±15 分钟

用 launchd：
  ✅ 需要本地文件/Chrome/GPU 的场景
  ✅ 精确到秒的定时
  ❌ 需要 Mac 不关机
  ❌ 断电就停了
```

---

## 11. 设计系统：双主题 CSS 变量

### 直接抄的 CSS 变量模板

```css
/* 暗色主题（默认） */
[data-theme="dark"] {
  --bg-page:        #09090b;    /* 页面背景 */
  --bg-card:        #18181b;    /* 卡片背景 */
  --bg-card-hover:  #27272a;    /* 卡片悬停 */
  --bg-input:       #18181b;    /* 输入框背景 */
  --text-primary:   #fafafa;    /* 主文字 */
  --text-secondary: #a1a1aa;    /* 次要文字 */
  --border:         #27272a;    /* 边框 */
  --accent:         #3b82f6;    /* 强调色（蓝） */
  --accent-hover:   #2563eb;    /* 强调色悬停 */
  --danger:         #ef4444;    /* 错误/警告红 */
  --success:        #22c55e;    /* 成功绿 */
  --radius:         0.5rem;     /* 统一圆角 */
  --transition:     150ms ease; /* 统一过渡 */
}

/* 亮色主题 */
[data-theme="light"] {
  --bg-page:        #ffffff;
  --bg-card:        #f4f4f5;
  --bg-card-hover:  #e4e4e7;
  --bg-input:       #ffffff;
  --text-primary:   #18181b;
  --text-secondary: #71717a;
  --border:         #e4e4e7;
  --accent:         #2563eb;
  --accent-hover:   #1d4ed8;
  --danger:         #dc2626;
  --success:        #16a34a;
  --radius:         0.5rem;
  --transition:     150ms ease;
}
```

### 主题切换按钮实现

```javascript
// 读取/保存主题偏好
const theme = localStorage.getItem('theme') || 'dark';
document.documentElement.setAttribute('data-theme', theme);

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
}
```

### 常用组件 CSS 类（Vercel 风格）

```css
/* 卡片 */
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.5rem;
  transition: all var(--transition);
}
.card:hover {
  background: var(--bg-card-hover);
  border-color: var(--accent);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

/* 输入框 */
.input {
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-primary);
  padding: 0.5rem 0.75rem;
  outline: none;
  transition: border-color var(--transition);
}
.input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

/* 按钮 */
.btn {
  padding: 0.5rem 1rem;
  border-radius: var(--radius);
  font-weight: 500;
  transition: all var(--transition);
  cursor: pointer;
}
.btn-primary {
  background: var(--accent);
  color: white;
}
.btn-primary:hover {
  background: var(--accent-hover);
}
```

---

## 12. 外部服务总清单

> 建一个站大概需要这些外部服务。括号里是免费额度。

### 必须配的

| 服务 | 用途 | 费用 |
|------|------|------|
| **Cloudflare** | 域名 + DNS + CDN + Pages 托管 + 安全 | 域名 $10-15/年，其余免费 |
| **GitHub** | 代码仓库 + CI/CD (Actions) | 免费 |
| **Google Search Console** | SEO 搜索表现数据 | 免费 |

### 强烈建议配的

| 服务 | 用途 | 费用 |
|------|------|------|
| **CF Web Analytics** | 基础流量统计 | 免费 |
| **Google Analytics 4** | 深度用户行为分析 | 免费 |
| **Microsoft Clarity** | 用户录屏 + 热力图 | 免费 |
| **Bing Webmaster** | 必应 SEO | 免费 |

### 按需的

| 服务 | 用途 | 费用 |
|------|------|------|
| **Cloudflare Workers** | 轻量后端/API（10万次/天免费） | 免费起 |
| **Cloudflare D1** | SQLite 数据库（5GB 免费） | 免费起 |
| **Cloudflare KV** | 键值存储（1GB 免费） | 免费起 |
| **Railway** | 完整后端托管 | $5/月起 |
| **OpenAI API** | AI 能力 | 按量 |
| **DeepSeek API** | AI 能力（便宜替代） | 按量 |
| **Gemini API** | AI 能力（有免费额度） | 免费额度 |

### 变现相关

| 服务 | 用途 | 门槛 |
|------|------|------|
| **AdSense** | 展示广告 | 需要内容审核通过 |
| **Amazon Associates** | 联盟营销 | 需要前 3 笔销售激活 |
| **Gumroad** | 卖数字产品 | 无门槛，抽成 10% |
| **Lemon Squeezy** | 卖数字产品（支持中国） | 无门槛，抽成 5%+$0.5 |

---

## 13. 开工前 5 件必做

### 1. 验证有没有人搜

```
拿你要做的 5-10 个关键词，逐一验证：

工具：
  Google Keyword Planner（需要广告账号，免费）
  Ahrefs Free Keyword Generator
  Semrush 免费版（每天 10 次）
  Ubersuggest 免费版
  
看什么：
  月搜索量 < 50 → 放弃，没人搜
  月搜索量 50-500 → 能做，是小众赛道
  月搜索量 500+ → 竞争激烈，看竞品

看搜索结果第一页：
  全是 wikipedia、reddit、youtube → 放弃，大站垄断
  有小博客、个人站混在第一页 → 有机会
```

### 2. 仔细看竞品

```
搜你要做的核心词，打开第一页所有结果，逐个问：

这个站做了多久？（whois 查域名年龄）
内容多深？（字数、功能数、图表数、视频数）
怎么变现？（广告/联盟/自有产品/咨询）
流量多大？（Similarweb 免费版粗略估计）

给自己打分：
能不能做出比这 10 个里至少 3 个更好的？
  不能 → 换赛道
  能 → 下一步
```

### 3. 先想清楚钱从哪来

> 见下一章「变现模式选择」

### 4. 判断适不适合 AI 批量

> 见「AI 批量适用判断」

### 5. 预估维护成本

```
黄金法则：手动跑通 3 轮，再考虑自动化

● 内容站维护项：
  - 内容更新频率（每周几篇？谁写？）
  - 外链建设（需要联系其他站长？）
  - 工具/功能更新（如果有交互功能）
  - 分析数据解读

● 自动化维护项：
  - 数据源稳定性（API 会不会挂？）
  - 产出质量检查（AI 生成的东西人要看）
  - 垃圾清理（自动生成会有坏结果）

● 死线：如果周维护 > 2 小时 → 说明自动化比手动更费时间 → 关掉
```

---

## 14. 变现模式选择

### 内容站变现

```
模式 1：展示广告
  适合：日 PV > 5000
  平台：AdSense（门槛低）→ Mediavine（日 5 万 PV）→ Raptive（日 10 万 PV）
  收入：每千次展示 $2-15（看行业）

模式 2：联盟营销
  适合：内容里有推荐产品/工具的场景
  平台：Amazon Associates / Impact / CJ / ShareASale
  做法：文章里推荐产品，放专属链接，成交拿佣金
  注意：Amazon 前 3 单必须 180 天内完成，否则封号
  
模式 3：信息产品
  适合：有专业知识积累
  产品：PDF 模板 / Checklist / 课程 / Notion 模板
  平台：Gumroad / Lemon Squeezy
  收入：定价 × 销量，100% 你的（减平台抽成）

模式 4：咨询/服务
  适合：B2B 方向的站
  做法：页面底挂"找我咨询/做项目"，留联系方式
```

### 工具站变现

```
模式 1：Freemium
  免费版：限次数/限功能/带水印
  付费版：$5-20/月，解锁所有限制

模式 2：广告
  工具页面嵌入 AdSense
  注意：工具站 PV 增长慢，可能要等很久才够门槛

模式 3：联盟
  工具输出结果旁推荐付费工具
  比如"转完 PDF → 需要编辑吗？试试 XXX"
```

### 关键教训

```
❌ 我们犯的错：36 个工具全免费，CPS 链接无佣金，变现框架全是占位符
✅ 正确做法：
  1. 上线的第一天就挂至少一个变现点
  2. 别等"流量大了再说"——那天可能永远不会来
  3. 哪怕只是一个 Gumroad 链接，也比空着强
```

---

## 15. AI 批量适用判断

### 适合 AI 批量（初稿 + 人审）

```
✔ 结构化内容
  教程步骤、How-to 指南、对比表、FAQ 列表
  
✔ 数据驱动
  排行榜、统计数据汇总、"最佳XX"列表
  
✔ 模板类
  邮件模板、Prompt 集合、Checklist、SOP 流程
  
✔ 解释定义类
  "什么是XX"、"XX怎么用"这类解释性内容
```

### 不适合 AI 批量

```
✘ 需要真实体验的
  产品上手评测、使用心得、踩坑记录
  
✘ 工具功能性页面
  每个工具交互都要单独开发测试，AI 只能出 HTML 壳
  
✘ 时效性强的
  行业新闻、政策变化、热点事件

✘ 需要可信度的
  医疗建议、法律咨询、投资分析
```

### 核心原则

```
AI 写初稿 + 人改关键部分 ✓
全自动无人审 ✗

50 个 AI 生成的烂内容 < 1 个人工打磨的精品
```

---

## 16. 死线与止损

> 什么时候该停下来、换方向、或者放弃。

### 项目级死线

```
⏰ 2 周内：
  网站上线 + 基础内容 + 提交 GSC
  如果 2 周还没上线 → 说明方向有问题或执行力不够

⏰ 1 个月内：
  GSC 开始有数据
  如果没有任何搜索点击 → 内容方向可能不对

⏰ 3 个月内：
  日均 PV 应该 > 50
  如果还是个位数 → 内容不够或 SEO 有问题

⏰ 6 个月内：
  应该看到增长曲线（至少缓慢上升）
  如果完全平的 → 赛道太小或竞品太强
```

### 自动化死线

```
如果自动化流水线的维护时间 > 手动做的时间 → 关掉自动化

具体指标：
  每周维护 > 2 小时 → 关
  产出质量 < 50% 可用 → 关
  3 次以上大面积故障 → 关

黄金法则：手动跑通 3 轮，再考虑自动化
```

### 放弃不丢人

```
以下情况果断放弃：
  - 验证发现没人搜（月搜 < 50）
  - 竞品太强追不上（第一页都是大站）
  - 3 个月了没有任何搜索流量
  - 维护成本太高、占用主业时间

换赛道比死磕明智。教训记下来下个站用。
```

---

## 附录 A：MintShovels 项目资产清单

> 仅作参考。以下列出 v1.8-stable 所有文件及在新项目中的处理建议。

### 前端文件

| 文件 | 说明 | 处理 |
|------|------|:--:|
| `index.html` (4600行 SPA) | 主站，工具网格+搜索+双主题+中英双语 | 🔄 |
| `api-config.js` | 注入 API 地址 | 🔄 |
| `manifest.json` | PWA 清单 | ✅ 通用 |
| `sw.js` | Service Worker | ✅ 通用 |
| `robots.txt` / `sitemap.xml` | SEO | ✅ 通用 |
| `_headers` | 安全头 | ✅ 通用 |
| `404.html` | 404 页面 | ✅ 通用 |

### 后端文件

| 文件 | 说明 | 处理 |
|------|------|:--:|
| `app.py` (4600行) | FastAPI 主后端，17 个端点 | 🗑️ |
| `engine/main.py` | 第二套 FastAPI（功能重叠） | 🗑️ |
| `Procfile` / `runtime.txt` | Railway 配置 | 🗑️ |
| `requirements.txt` / `package.json` | 依赖 | 📦 |

### Engine 核心引擎

| 文件 | 说明 | 处理 |
|------|------|:--:|
| `engine/pipeline.py` | 全自动流水线主控 | 🔄 |
| `engine/ai_client.py` | AI 多层 fallback 客户端 | ✅ 通用 |
| `engine/demand_radar.py` | 需求雷达 v2.1（19 个水源） | 🔄 |
| `engine/ai_tool_generator.py` | AI 工具生成器 | 🔄 |
| `engine/ai_demand_analyzer.py` | 需求分析 | 🔄 |
| `engine/ai_quality_validator.py` | 质量验证 | 🔄 |
| `engine/demand_filter.py` | 需求过滤器 v4.0 | 🔄 |
| `engine/intent_classifier.py` | 意图分类器 | 🔄 |
| `engine/template_rewriter.py` | 模板重写 | 🗑️ |
| `engine/functional_test_runner.py` | 功能测试 | 🗑️ |
| `engine/__init__.py` | 包标记 | 📦 |

### GitHub Actions（5 个 workflow）

| 文件 | 说明 | 处理 |
|------|------|:--:|
| `deploy.yml` | push → 部署 | ✅ 通用 |
| `health-check.yml` | 定时体检 | ✅ 通用 |
| `mintshovels-pipeline.yml` | 每3h 跑流水线 | 🗑️ |
| `pipeline-scheduler.yml` | 同上（重复） | 🔄 |
| `tool-tests.yml` | Playwright 测试 | 🗑️ |

### 根目录脚本（25+ 个）

```
✅ 通用（换项目直接改域名就能用）：
  mintshovels_full_check.py  6大类体检
  auto_health_check.py        网站+工具健康检查
  data_engine.py              数据聚合引擎
  dashboard_server.py          看板服务器
  scripts/build_safeguard.py   部署前校验
  scripts/purge_cf_cache.py    清 CF 缓存

🗑️ 工具站专用（新项目不需要）：
  auto_extract_ids.py / demand_*.py / garbage_tool_scanner.py
  template_rewriter.py / functional_test_runner.py
  intent_classifier.py / llm_intent_classifier.py
  tool_generator.py / tool_name_cleaner.py
  module_quality_enhancer.py / pain_point_search.py
  live_test_harness.py / mintshovels_dashboard.py
```

### 数据与分析配置

| 资产 | 值 | 处理 |
|------|-----|:--:|
| CF Zone ID | `4a5e0a77d5483837f773bbe390fb2084` | 换 |
| GA4 ID | `G-D53DQ3JKKL` | 换 |
| Clarity ID | `xavbiwb9dt` | 换 |
| Bing API Key | `937c378993144746af783d701c826b06` | 换 |
| CF API Token 1 | `cfut_955py0...` (Analytics 只读) | 换 |
| CF API Token 2 | `cfut_Blorfr...` (Zone 只读) | 换 |
| 账号邮箱 | `Sun490619@gmail.com` | 换 |

### Shell 脚本与定时任务

| 文件 | 说明 | 处理 |
|------|------|:--:|
| `run_full_pipeline.sh` | 完整流水线启动 | 🔄 |
| `start_pipeline.sh` | 流水线启动 | 🔄 |
| `sync_to_github.command` | macOS Git 同步（双击） | ✅ 通用 |
| `sync_to_github.bat` | Windows Git 同步 | ✅ 通用 |
| `com.mintshovels.pipeline.plist` | launchd 定时 | 🔄 |
| `setup_launchd.sh` | launchd 安装脚本 | 🔄 |

---

## 附录 B：从工具站到内容站：迁移对照

> 如果从 MintShovels 工具站改成内容站，每样东西怎么处理。

### 保留不改的

```
_headers                 安全头，改后端地址即可
sw.js                    Service Worker 不变
manifest.json            改 name/description/icon
robots.txt               改 sitemap 路径
404.html                 改样式适配新站
favicon.* / icon-*.png   换新图标
.github/workflows/deploy.yml     改校验逻辑
.github/workflows/health-check.yml 改造检查项
scripts/purge_cf_cache.py        不变
sync_to_github.command/bat       不变
```

### 需要重写的

```
index.html           → 工具网格 → 文章列表/文章页
api-config.js        → 更新或删除（纯静态不需要）
sitemap.xml          → 按文章 URL 重新生成
dashboard.html       → 工具仪表盘 → 内容数据看板
admin/index.html     → 改认证逻辑和后台功能
data_engine.py       → 改数据源和聚合逻辑
mintshovels_full_check.py → 改检查项
auto_health_check.py       → 改检查项
scripts/build_safeguard.py → 改校验规则
```

### 引擎改造思路

```
engine/pipeline.py           → 内容生产流水线
engine/demand_radar.py       → 关键词/话题雷达
engine/ai_tool_generator.py  → AI 文章生成器
engine/ai_demand_analyzer.py → 话题分析器
engine/ai_quality_validator.py → 内容质量检查
engine/demand_filter.py      → 话题过滤器
engine/intent_classifier.py  → 内容类型分类器
engine/ai_client.py          → 直接复用，不改
```

### 可以扔的

```
app.py / engine/main.py            不需要后端了
Procfile / runtime.txt            停用 Railway
template_rewriter.py              内容站不需要模板重写
functional_test_runner.py         内容站不需要工具功能测试
test_tools.mjs                    不需要 Playwright 测试
demand_*.py / garbage_*.py 等      工具站专用，全丢
tool_*.py / module_*.py 等        同上
engine/extract_common.py          不需要 yt-dlp
大部分根目录脚本                   工具站专用的 20+ 个脚本
```

### 需要新增的

```
文章内页模板（article.html）
分类聚合页（category.html）
RSS feed（rss.xml）
结构化数据模板（Article / FAQ / HowTo JSON-LD）
内容生产流水线（pipeline 改造版）
图片处理脚本（文章配图自动生成/压缩）
```

---

## 最后

> 建站三句话：
> 1. 验证搜索需求再动手
> 2. 上线第一天挂变现
> 3. 手动跑通再自动化

这份工具箱会随每次实战持续更新。下次建完站回来补充新发现的东西。
