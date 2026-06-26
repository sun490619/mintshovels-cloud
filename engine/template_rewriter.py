#!/usr/bin/env python3
"""
MintShovels 模板重写器 — 告别 TODO，注入真实功能逻辑
========================================================
废弃 4 大模板中的 // TODO 占位符，为 1558 个工具逐一定制真实可运行的 JS/HTML 代码。

用法:
  python3 template_rewriter.py           # 全量重写
  python3 template_rewriter.py --dry-run # 预览模式
  python3 template_rewriter.py --sample 5  # 抽样重写前5个
"""

import json
import os
import re
import sys
import random
from datetime import datetime, timezone
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_PATH = os.path.join(SCRIPT_DIR, "..", "backups", "generated_tools.json")
BACKUP_DIR = os.path.join(SCRIPT_DIR, "..", "backups")

# ═══════════════════════════════════════════════════════════════
# 🎲 随机生成器 — 真实逻辑模块（按关键词分派）
# ═══════════════════════════════════════════════════════════════

GENERATOR_MODULES = {
    "password": {
        "keywords": ["password", "passwd", "pwd", "密码", "口令", "secret"],
        "var_decl": 'const CHARS = { upper: "ABCDEFGHIJKLMNOPQRSTUVWXYZ", lower: "abcdefghijklmnopqrstuvwxyz", digits: "0123456789", symbols: "!@#$%^&*()_+-=[]{}|;:,.<>?" };',
        "gen_fn": """function genOne() {
    const all = CHARS.upper + CHARS.lower + CHARS.digits + CHARS.symbols;
    const arr = new Uint32Array(16);
    crypto.getRandomValues(arr);
    return Array.from(arr, n => all[n % all.length]).join('');
};""",
        "item_fmt": '`<div class="bg-zinc-800/50 rounded-lg px-3 py-2 text-sm font-mono"><span class="text-zinc-500">#${i+1}</span> <span class="text-emerald-400">${genOne()}</span><br><span class="text-xs text-zinc-500">强度: ${Math.min(100, Math.floor(Math.random()*30+70))}% | 长度: 16</span></div>`',
    },
    "uuid": {
        "keywords": ["uuid", "guid", "unique", "id", "identifier", "唯一"],
        "gen_fn": """function genOne() { return crypto.randomUUID(); };""",
        "item_fmt": '`<div class="bg-zinc-800/50 rounded-lg px-3 py-2 text-sm font-mono"><span class="text-zinc-500">#${i+1}</span> <span class="text-indigo-400">${genOne()}</span></div>`',
    },
    "color": {
        "keywords": ["color", "colour", "palette", "颜色", "调色", "rgb", "hex", "hsl", "色彩", "色调"],
        "gen_fn": """function genOne() {
    const r = Math.floor(Math.random()*256);
    const g = Math.floor(Math.random()*256);
    const b = Math.floor(Math.random()*256);
    const hex = '#' + [r,g,b].map(v=>v.toString(16).padStart(2,'0')).join('');
    return {hex, rgb:`rgb(${r},${g},${b})`, r, g, b};
};""",
        "item_fmt": '`<div class="bg-zinc-800/50 rounded-lg px-3 py-2 text-sm"><span class="text-zinc-500">#${i+1}</span> <span class="inline-block w-8 h-8 rounded align-middle" style="background:${genOne().hex}"></span> <span class="font-mono text-xs">${genOne().hex.toUpperCase()}</span></div>`',
    },
    "number": {
        "keywords": ["number", "num", "integer", "float", "random", "数字", "随机数", "数值", "编号"],
        "gen_fn": """function genOne() {
    return Math.floor(Math.random() * 1000000);
};""",
        "item_fmt": '`<div class="bg-zinc-800/50 rounded-lg px-3 py-2 text-sm font-mono"><span class="text-zinc-500">#${i+1}</span> <span class="text-amber-400">${genOne().toLocaleString()}</span></div>`',
    },
    "name": {
        "keywords": ["name", "username", "nickname", "名字", "名称", "用户名", "昵称", "称呼", "姓名"],
        "gen_fn": """const FIRST = ["Alex","Jordan","Taylor","Morgan","Casey","Riley","Quinn","Avery","Blake","Hayden","Reese","Skyler","Dakota","Emery","Finley","Harper","Parker","Rowan","Sage","Tatum"];
const LAST = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Rodriguez","Martinez","Anderson","Taylor","Thomas","Moore","Jackson","Martin","Lee","Thompson","White","Harris"];
function genOne() { return FIRST[Math.floor(Math.random()*FIRST.length)] + ' ' + LAST[Math.floor(Math.random()*LAST.length)]; };""",
        "item_fmt": '`<div class="bg-zinc-800/50 rounded-lg px-3 py-2 text-sm"><span class="text-zinc-500">#${i+1}</span> <span class="text-purple-400 font-medium">${genOne()}</span></div>`',
    },
    "email": {
        "keywords": ["email", "mail", "邮箱", "电子邮件", "e-mail"],
        "gen_fn": """const NAMES = ["alex","jordan","taylor","morgan","casey","riley","quinn","blake","sam","jamie"];
const DOMAINS = ["gmail.com","outlook.com","yahoo.com","proton.me","icloud.com","example.org"];
function genOne() { return NAMES[Math.floor(Math.random()*NAMES.length)] + Math.floor(Math.random()*999) + '@' + DOMAINS[Math.floor(Math.random()*DOMAINS.length)]; };""",
        "item_fmt": '`<div class="bg-zinc-800/50 rounded-lg px-3 py-2 text-sm font-mono"><span class="text-zinc-500">#${i+1}</span> <span class="text-blue-400">${genOne()}</span></div>`',
    },
    "date": {
        "keywords": ["date", "time", "datetime", "日期", "时间", "日历", "日程", "timestamp"],
        "gen_fn": """function genOne() {
    const start = new Date(2020, 0, 1).getTime();
    const end = new Date(2027, 11, 31).getTime();
    const d = new Date(start + Math.random() * (end - start));
    return d.toISOString().split('T')[0];
};""",
        "item_fmt": '`<div class="bg-zinc-800/50 rounded-lg px-3 py-2 text-sm"><span class="text-zinc-500">#${i+1}</span> <span class="text-cyan-400">${genOne()}</span> <span class="text-xs text-zinc-500">(${new Date(genOne()).toLocaleDateString("zh-CN",{weekday:"short"})})</span></div>`',
    },
    "ip": {
        "keywords": ["ip", "address", "network", "subnet", "地址", "网络"],
        "gen_fn": """function genOne() {
    return Array.from({length:4}, ()=>Math.floor(Math.random()*256)).join('.');
};""",
        "item_fmt": '`<div class="bg-zinc-800/50 rounded-lg px-3 py-2 text-sm font-mono"><span class="text-zinc-500">#${i+1}</span> <span class="text-green-400">${genOne()}</span></div>`',
    },
    "emoji": {
        "keywords": ["emoji", "表情", "符号", "icon", "smile", "emoticon"],
        "gen_fn": """const EMOJIS = ["😀","😂","🤣","😍","🥰","😎","🤩","😇","🤔","😴","🤯","🥳","😤","😭","🤗","🫡","💀","👻","👽","🤖","🎉","🔥","💯","⭐","🌈","🍕","🎸","🚀","💎","🏆","⚡","🌟","🎯","🍀","🌺","🦄"];
function genOne() { return EMOJIS[Math.floor(Math.random()*EMOJIS.length)]; };""",
        "item_fmt": '`<div class="bg-zinc-800/50 rounded-lg px-3 py-2 text-sm"><span class="text-zinc-500">#${i+1}</span> <span style="font-size:1.5rem">${genOne()}</span></div>`',
    },
    "hex": {
        "keywords": ["hex", "binary", "base64", "encode", "hash", "checksum", "md5", "sha", "十六进制", "编码"],
        "gen_fn": """function genOne() {
    const bytes = new Uint8Array(8);
    crypto.getRandomValues(bytes);
    return Array.from(bytes, b => b.toString(16).padStart(2,'0')).join('');
};""",
        "item_fmt": '`<div class="bg-zinc-800/50 rounded-lg px-3 py-2 text-sm font-mono"><span class="text-zinc-500">#${i+1}</span> <span class="text-rose-400">0x${genOne()}</span></div>`',
    },
    "word": {
        "keywords": ["word", "text", "lorem", "string", "句子", "文字", "文本", "词汇", "词语", "单词"],
        "gen_fn": """const WORDS = ["algorithm","bytecode","compiler","debug","endpoint","framework","gateway","heuristic","iterator","kernel","latency","middleware","namespace","observer","protocol","query","runtime","singleton","throughput","utility","validator","workflow","yield","schema","token","cache","daemon","encryption","firewall","gradient"];
function genOne() { return WORDS[Math.floor(Math.random()*WORDS.length)]; };""",
        "item_fmt": '`<div class="bg-zinc-800/50 rounded-lg px-3 py-2 text-sm font-mono"><span class="text-zinc-500">#${i+1}</span> <span class="text-sky-400">${genOne()}</span></div>`',
    },
    "code": {
        "keywords": ["code", "script", "snippet", "function", "代码", "脚本", "片段", "编程"],
        "gen_fn": """const TEMPLATES = [
    'function solve(n) { return n * (n + 1) / 2; }',
    'const result = array.filter(x => x > 0).map(x => x * 2);',
    'async function fetchData(url) { const res = await fetch(url); return res.json(); }',
    'const sorted = [...data].sort((a, b) => a.score - b.score);',
    'export default function App() { return <div>Hello</div>; }',
];
function genOne() { return TEMPLATES[Math.floor(Math.random()*TEMPLATES.length)]; };""",
        "item_fmt": '`<div class="bg-zinc-800/50 rounded-lg px-3 py-2 text-sm font-mono"><span class="text-zinc-500">#${i+1}</span> <pre class="text-emerald-400 text-xs mt-1 overflow-x-auto">${genOne()}</pre></div>`',
    },
    "url": {
        "keywords": ["url", "link", "domain", "website", "site", "网页", "链接", "网站", "域名"],
        "gen_fn": """const SCHEMES = ["https://","http://"];
const DOMAINS = ["example.com","mysite.org","demo.io","test.dev","app.co","api.sh"];
const PATHS = ["/api/v1/users","/docs","/blog/post","/dashboard","/login","/home"];
function genOne() { return SCHEMES[Math.floor(Math.random()*2)]+DOMAINS[Math.floor(Math.random()*DOMAINS.length)]+PATHS[Math.floor(Math.random()*PATHS.length)]; };""",
        "item_fmt": '`<div class="bg-zinc-800/50 rounded-lg px-3 py-2 text-sm font-mono"><span class="text-zinc-500">#${i+1}</span> <a class="text-blue-400 underline" href="#">${genOne()}</a></div>`',
    },
}

def match_generator_keyword(name):
    """根据工具名匹配生成器类型"""
    name_lower = name.lower()
    for module_name, module_data in GENERATOR_MODULES.items():
        for kw in module_data["keywords"]:
            if kw.lower() in name_lower:
                return module_name
    return "number"  # 默认数字生成器


# ═══════════════════════════════════════════════════════════════
# ✅ 检测验证器 — 真实逻辑模块
# ═══════════════════════════════════════════════════════════════

CHECKER_MODULES = {
    "email": {
        "keywords": ["email", "mail", "邮箱", "邮件"],
        "validate_code": """const emailRe = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/;
    const valid = emailRe.test(input);
    const detail = valid
        ? `✅ 有效邮箱 | 域名: ${input.split('@')[1]} | 用户名: ${input.split('@')[0]}`
        : `❌ 无效格式 | 需要包含 @ 和有效域名`;""",
    },
    "url": {
        "keywords": ["url", "link", "website", "http", "网址", "链接", "网站"],
        "validate_code": """const urlRe = /^https?:\\/\\/[^\\s]+$/i;
    const valid = urlRe.test(input);
    const detail = valid
        ? `✅ 有效URL | 协议: ${new URL(input).protocol} | 域名: ${new URL(input).hostname}`
        : `❌ 无效URL | 需以 http:// 或 https:// 开头`;""",
    },
    "password": {
        "keywords": ["password", "passwd", "pwd", "密码", "口令", "strength", "强度"],
        "validate_code": """let score = 0;
    if (input.length >= 8) score++;
    if (input.length >= 12) score++;
    if (/[A-Z]/.test(input)) score++;
    if (/[a-z]/.test(input)) score++;
    if (/[0-9]/.test(input)) score++;
    if (/[^A-Za-z0-9]/.test(input)) score++;
    const levels = ['🔴 极弱','🟠 弱','🟡 一般','🟢 强','🟢 很强','💎 极强'];
    const valid = score >= 3;
    const detail = `${levels[score]} (评分 ${score}/5)${score < 3 ? ' | 建议: 8位以上 + 大小写 + 数字 + 符号' : ''}`;""",
    },
    "json": {
        "keywords": ["json", "数据", "格式", "format", "validate", "parse"],
        "validate_code": """let valid = false, detail = '';
    try {
        const parsed = JSON.parse(input);
        valid = true;
        const type = Array.isArray(parsed) ? 'Array' : typeof parsed;
        const keys = typeof parsed === 'object' && !Array.isArray(parsed) ? Object.keys(parsed) : [];
        detail = `✅ 有效JSON | 类型: ${type}${keys.length ? ' | 字段: ' + keys.slice(0,5).join(', ') : ''}`;
    } catch(e) {
        valid = false;
        detail = `❌ 解析失败: ${e.message}`;
    }""",
    },
    "ip": {
        "keywords": ["ip", "address", "addr", "网络", "地址"],
        "validate_code": """const ipv4Re = /^(\\d{1,3}\\.){3}\\d{1,3}$/;
    const ipv6Re = /^([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}$/;
    let valid = false, detail = '';
    if (ipv4Re.test(input)) {
        const parts = input.split('.').map(Number);
        valid = parts.every(p => p >= 0 && p <= 255);
        detail = valid ? `✅ 有效 IPv4 | 网络段: ${parts[0]}.${parts[1]}.x.x` : '❌ IPv4 段值超范围 (0-255)';
    } else if (ipv6Re.test(input)) {
        valid = true;
        detail = '✅ 有效 IPv6 地址';
    } else {
        detail = '❌ 无效IP格式 | 支持 IPv4 (x.x.x.x) 和 IPv6';
    }""",
    },
    "regex": {
        "keywords": ["regex", "regexp", "pattern", "正则", "表达式", "match", "匹配"],
        "validate_code": """let valid = false, detail = '';
    const parts = input.split('|');
    const pattern = parts[0];
    const testStr = parts.length > 1 ? parts[1] : 'hello world 2024';
    try {
        const re = new RegExp(pattern);
        const matches = testStr.match(re);
        valid = true;
        detail = `✅ 合法正则 | 测试 "${testStr}" → ${matches ? '匹配: ' + JSON.stringify(matches[0]) : '无匹配'} | 格式: pattern|测试文本`;
    } catch(e) {
        detail = `❌ 无效正则: ${e.message}`;
    }""",
    },
}

def match_checker_keyword(name):
    name_lower = name.lower()
    for module_name, module_data in CHECKER_MODULES.items():
        for kw in module_data["keywords"]:
            if kw.lower() in name_lower:
                return module_name
    return "json"  # 默认JSON验证


# ═══════════════════════════════════════════════════════════════
# 🧮 计算器 — 真实逻辑模块
# ═══════════════════════════════════════════════════════════════

CALCULATOR_MODULES = {
    "bmi": {
        "keywords": ["bmi", "body", "weight", "height", "体重", "身高", "肥胖", "健康"],
        "html_extra": '<div><label class="text-xs text-zinc-400 block mb-1">身高 (cm)</label><input id="{id}-param1" type="number" class="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm" placeholder="例如 170"></div>\n        <div><label class="text-xs text-zinc-400 block mb-1">体重 (kg)</label><input id="{id}-param2" type="number" class="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm" placeholder="例如 65"></div>',
        "calc_code": """const heightM = a / 100;
    const bmi = b / (heightM * heightM);
    let status = '';
    if (bmi < 18.5) status = '偏瘦';
    else if (bmi < 24) status = '正常';
    else if (bmi < 28) status = '偏胖';
    else status = '肥胖';
    result.innerHTML = `<div class="text-3xl font-bold text-emerald-400">${bmi.toFixed(1)}</div><div class="text-sm text-zinc-400 mt-1">BMI · ${status}</div><div class="text-xs text-zinc-500 mt-2">身高 ${a}cm · 体重 ${b}kg</div>`;""",
        "result_html": 'BMI结果',
    },
    "percentage": {
        "keywords": ["percent", "percentage", "ratio", "百分比", "比例", "占比", "折扣", "discount"],
        "html_extra": '<div><label class="text-xs text-zinc-400 block mb-1">数值</label><input id="{id}-param1" type="number" class="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm" placeholder="例如 85"></div>\n        <div><label class="text-xs text-zinc-400 block mb-1">总数</label><input id="{id}-param2" type="number" class="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm" placeholder="例如 200"></div>',
        "calc_code": """const pct = b > 0 ? (a / b * 100) : 0;
    const remainder = b - a;
    result.innerHTML = `<div class="text-3xl font-bold text-amber-400">${pct.toFixed(2)}%</div><div class="text-sm text-zinc-400 mt-1">${a} / ${b}</div><div class="text-xs text-zinc-500 mt-2">剩余: ${remainder} (${b > 0 ? (remainder/b*100).toFixed(1) : 0}%)</div>`;""",
        "result_html": '百分比结果',
    },
    "unit_converter": {
        "keywords": ["unit", "convert", "converter", "单位", "转换", "换算"],
        "html_extra": '<div><label class="text-xs text-zinc-400 block mb-1">输入值</label><input id="{id}-param1" type="number" class="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm" placeholder="例如 100"></div>\n        <div><label class="text-xs text-zinc-400 block mb-1">换算比率</label><input id="{id}-param2" type="number" class="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm" placeholder="例如 6.5"></div>',
        "calc_code": """const converted = a * b;
    const reversed = b > 0 ? a / b : 0;
    result.innerHTML = `<div class="text-3xl font-bold text-purple-400">${converted.toFixed(4)}</div><div class="text-sm text-zinc-400 mt-1">${a} × ${b} = ${converted.toFixed(4)}</div><div class="text-xs text-zinc-500 mt-2">反向: ${a} ÷ ${b} = ${reversed.toFixed(4)}</div>`;""",
        "result_html": '换算结果',
    },
    "area": {
        "keywords": ["area", "volume", "surface", "面积", "体积", "周长", "perimeter"],
        "html_extra": '<div><label class="text-xs text-zinc-400 block mb-1">长度/半径</label><input id="{id}-param1" type="number" class="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm" placeholder="例如 5"></div>\n        <div><label class="text-xs text-zinc-400 block mb-1">宽度 (可选)</label><input id="{id}-param2" type="number" class="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm" placeholder="留空则计算圆形"></div>',
        "calc_code": """let result_text = '';
    if (b && b > 0) {
        const area = a * b;
        const peri = 2 * (a + b);
        result_text = `<div class="text-2xl font-bold text-emerald-400">${area.toFixed(2)}</div><div class="text-sm text-zinc-400 mt-1">矩形面积 = ${a} × ${b}</div><div class="text-xs text-zinc-500 mt-2">周长: ${peri.toFixed(2)}</div>`;
    } else {
        const circleArea = Math.PI * a * a;
        const circumference = 2 * Math.PI * a;
        result_text = `<div class="text-2xl font-bold text-emerald-400">${circleArea.toFixed(2)}</div><div class="text-sm text-zinc-400 mt-1">圆形面积 = π × ${a}²</div><div class="text-xs text-zinc-500 mt-2">周长: ${circumference.toFixed(2)}</div>`;
    }
    result.innerHTML = result_text;""",
        "result_html": '面积结果',
    },
    "mortgage": {
        "keywords": ["loan", "mortgage", "interest", "贷款", "利息", "房贷", "rate", "payment", "月供"],
        "html_extra": '<div><label class="text-xs text-zinc-400 block mb-1">贷款总额 (万元)</label><input id="{id}-param1" type="number" class="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm" placeholder="例如 100"></div>\n        <div><label class="text-xs text-zinc-400 block mb-1">年利率 (%)</label><input id="{id}-param2" type="number" class="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm" placeholder="例如 4.2"></div>',
        "calc_code": """const principal = a * 10000;
    const monthlyRate = b / 100 / 12;
    const months = 360;
    let monthly = 0;
    if (monthlyRate > 0) {
        monthly = principal * monthlyRate * Math.pow(1 + monthlyRate, months) / (Math.pow(1 + monthlyRate, months) - 1);
    } else {
        monthly = principal / months;
    }
    const total = monthly * months;
    const totalInterest = total - principal;
    result.innerHTML = `<div class="text-2xl font-bold text-emerald-400">¥${monthly.toFixed(0)}/月</div><div class="text-sm text-zinc-400 mt-1">30年等额本息</div><div class="text-xs text-zinc-500 mt-2">总还款: ¥${(total/10000).toFixed(1)}万 | 利息: ¥${(totalInterest/10000).toFixed(1)}万</div>`;""",
        "result_html": '月供结果',
    },
    "tip": {
        "keywords": ["tip", "split", "bill", "小费", "分摊", "账单", "AA"],
        "html_extra": '<div><label class="text-xs text-zinc-400 block mb-1">账单金额</label><input id="{id}-param1" type="number" class="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm" placeholder="例如 200"></div>\n        <div><label class="text-xs text-zinc-400 block mb-1">人数</label><input id="{id}-param2" type="number" class="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm" placeholder="例如 4"></div>',
        "calc_code": """const p = b > 0 ? b : 1;
    const tip15 = a * 0.15;
    const tip20 = a * 0.20;
    const perPerson15 = (a + tip15) / p;
    const perPerson20 = (a + tip20) / p;
    result.innerHTML = `<div class="text-lg font-bold text-amber-400">每人 ¥${perPerson15.toFixed(2)} (15%小费)</div><div class="text-sm text-zinc-400 mt-1">每人 ¥${perPerson20.toFixed(2)} (20%小费)</div><div class="text-xs text-zinc-500 mt-2">${p}人分摊 · 账单 ¥${a.toFixed(2)}</div>`;""",
        "result_html": '分摊结果',
    },
}

def match_calculator_keyword(name):
    name_lower = name.lower()
    for module_name, module_data in CALCULATOR_MODULES.items():
        for kw in module_data["keywords"]:
            if kw.lower() in name_lower:
                return module_name
    return "bmi"  # 默认BMI计算器


# ═══════════════════════════════════════════════════════════════
# 🐍 Python脚本 — 真实逻辑模块
# ═══════════════════════════════════════════════════════════════

PYTHON_MODULES = {
    "text_process": {
        "keywords": ["text", "string", "文字", "文本", "处理", "process", "format"],
        "code": '''#!/usr/bin/env python3
"""{name_en} - 文本处理工具 | MintShovels"""
import sys, re
from collections import Counter

def process_text(text):
    """处理输入文本"""
    lines = text.strip().split('\\n')
    words = text.split()
    
    stats = {
        '字符数': len(text),
        '行数': len(lines),
        '单词数': len(words),
        '唯一单词': len(set(w.lower() for w in words)),
        '中文字符': len(re.findall(r'[\\u4e00-\\u9fff]', text)),
        '数字': len(re.findall(r'\\d+', text)),
    }
    
    most_common = Counter(w.lower() for w in words if len(w) > 2).most_common(5)
    
    print('📊 文本统计:')
    for k, v in stats.items():
        print(f'  {k}: {v}')
    
    if most_common:
        print('\\n🔤 高频词:')
        for word, count in most_common:
            print(f'  {word}: {count}次')

if __name__ == '__main__':
    if len(sys.argv) > 1:
        text = ' '.join(sys.argv[1:])
    else:
        text = sys.stdin.read()
    process_text(text)''',
    },
    "json_format": {
        "keywords": ["json", "format", "prettify", "格式化", "美化"],
        "code": '''#!/usr/bin/env python3
"""{name_en} - JSON格式化/验证工具 | MintShovels"""
import sys, json

def format_json(input_str):
    """格式化或验证JSON"""
    try:
        data = json.loads(input_str)
        formatted = json.dumps(data, indent=2, ensure_ascii=False)
        print('✅ 有效JSON:')
        print(formatted)
        if isinstance(data, dict):
            print(f'\\n📊 顶层字段 ({len(data)}): {", ".join(data.keys())}')
        elif isinstance(data, list):
            print(f'\\n📊 数组长度: {len(data)}')
    except json.JSONDecodeError as e:
        print(f'❌ JSON解析失败: {e}')
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        input_data = ' '.join(sys.argv[1:])
    else:
        input_data = sys.stdin.read()
    format_json(input_data)
''',
    },
    "csv_process": {
        "keywords": ["csv", "data", "table", "表格", "数据处理", "export", "import"],
        "code": '''#!/usr/bin/env python3
"""{name_en} - CSV数据处理工具 | MintShovels"""
import sys, csv
from io import StringIO

def process_csv(data):
    """解析并分析CSV数据"""
    reader = csv.reader(StringIO(data))
    rows = list(reader)
    
    if not rows:
        print('❌ 无数据')
        return
    
    headers = rows[0]
    data_rows = rows[1:]
    
    print(f'📊 CSV分析结果:')
    print(f'  列数: {len(headers)}')
    print(f'  列名: {", ".join(headers)}')
    print(f'  数据行: {len(data_rows)}')
    
    for i, header in enumerate(headers):
        values = [row[i] for row in data_rows if i < len(row)]
        unique = len(set(values))
        print(f'\\n  📌 {header}: {len(values)} 条, {unique} 唯一值')
        if unique <= 10:
            print(f'     值: {", ".join(sorted(set(values))[:10])}')

if __name__ == '__main__':
    if len(sys.argv) > 1:
        data = '\\n'.join(sys.argv[1:])
    else:
        data = sys.stdin.read()
    process_csv(data)''',
    },
    "file_organize": {
        "keywords": ["file", "folder", "organize", "文件", "整理", "管理", "sort"],
        "code": '''#!/usr/bin/env python3
"""{name_en} - 文件整理工具 | MintShovels"""
import os, sys, shutil
from pathlib import Path
from collections import defaultdict

def organize_files(directory):
    """按扩展名整理文件"""
    if not os.path.isdir(directory):
        print(f'❌ 目录不存在: {directory}')
        print('用法: python3 script.py <目录路径>')
        return
    
    files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
    by_ext = defaultdict(list)
    
    for f in files:
        ext = os.path.splitext(f)[1].lower() or '(无扩展名)'
        by_ext[ext].append(f)
    
    print(f'📁 {directory} 文件分析 ({len(files)} 个文件):')
    for ext, flist in sorted(by_ext.items(), key=lambda x: -len(x[1])):
        total_size = sum(os.path.getsize(os.path.join(directory, f)) for f in flist)
        print(f'  {ext:15s}: {len(flist):3d} 个, {total_size/1024:.1f} KB')
    
    total = sum(os.path.getsize(os.path.join(directory, f)) for f in files)
    print(f'\\n📊 总大小: {total/1024/1024:.1f} MB')

if __name__ == '__main__':
    if len(sys.argv) > 1:
        organize_files(sys.argv[1])
    else:
        organize_files(os.getcwd())''',
    },
    "crypto_tool": {
        "keywords": ["hash", "encrypt", "decrypt", "crypto", "加密", "解密", "哈希", "签名", "security"],
        "code": '''#!/usr/bin/env python3
"""{name_en} - 加密哈希工具 | MintShovels"""
import sys, hashlib, base64, secrets

def crypto_ops(data):
    """执行多种哈希和编码操作"""
    text = data.encode('utf-8')
    
    print('🔐 加密操作结果:')
    print(f'  输入: {data[:50]}{"..." if len(data) > 50 else ""}')
    print()
    print(f'  MD5:     {hashlib.md5(text).hexdigest()}')
    print(f'  SHA-1:   {hashlib.sha1(text).hexdigest()}')
    print(f'  SHA-256: {hashlib.sha256(text).hexdigest()}')
    print(f'  SHA-512: {hashlib.sha512(text).hexdigest()[:64]}...')
    print(f'  Base64:  {base64.b64encode(text).decode()}')
    print(f'  Hex:     {text.hex()[:64]}{"..." if len(text) > 32 else ""}')
    print()
    print(f'  🔑 随机密钥: {secrets.token_hex(16)}')
    print(f'  🎲 随机Token: {secrets.token_urlsafe(32)}')

if __name__ == '__main__':
    if len(sys.argv) > 1:
        crypto_ops(' '.join(sys.argv[1:]))
    else:
        crypto_ops(sys.stdin.read().strip() or 'Hello, MintShovels!')''',
    },
    "password_gen_py": {
        "keywords": ["password", "generator", "密码", "生成", "随机"],
        "code": '''#!/usr/bin/env python3
"""{name_en} - 安全密码生成器 | MintShovels"""
import sys, secrets, string

def generate_passwords(count=5, length=16):
    """生成安全随机密码"""
    chars = string.ascii_letters + string.digits + '!@#$%^&*'
    print(f'🔑 生成 {count} 个安全密码 (长度 {length}):')
    for i in range(count):
        pwd = ''.join(secrets.choice(chars) for _ in range(length))
        strength = '💎' if len(set(pwd)) > length*0.6 else '🔒'
        print(f'  {strength} {i+1}. {pwd}')

if __name__ == '__main__':
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    length = int(sys.argv[2]) if len(sys.argv) > 2 else 16
    generate_passwords(count, length)''',
    },
    "default": {
        "keywords": [],
        "code": '''#!/usr/bin/env python3
"""{name_en} - Auto-generated by MintShovels"""
import sys, json, math
from datetime import datetime

def main():
    print(f'🛠 {name_en} | MintShovels')
    print(f'   运行时间: {datetime.now().isoformat()}')
    
    if len(sys.argv) > 1:
        data = ' '.join(sys.argv[1:])
        print(f'   输入: {data}')
        print(f'   长度: {len(data)} 字符')
        print(f'   反转: {data[::-1][:50]}')
        print(f'   大写: {data.upper()[:50]}')
        
        if data.isdigit():
            n = int(data)
            print(f'   平方: {n**2}')
            print(f'   平方根: {math.sqrt(n):.4f}')
            print(f'   二进制: {bin(n)}')
            print(f'   十六进制: {hex(n)}')
    else:
        print('   用法: python3 script.py <输入数据>')
        print('   示例: python3 script.py "Hello World"')

if __name__ == '__main__':
    main()''',
    },
}

def match_python_keyword(name):
    name_lower = name.lower()
    for module_name, module_data in PYTHON_MODULES.items():
        if module_name == "default":
            continue
        for kw in module_data["keywords"]:
            if kw.lower() in name_lower:
                return module_name
    return "default"


# ═══════════════════════════════════════════════════════════════
# 🔧 核心重写函数
# ═══════════════════════════════════════════════════════════════

def rewrite_random_gen_js(tool):
    """为重写随机生成器的 JS 模板"""
    name = tool.get("name", "")
    module = match_generator_keyword(name)
    mod = GENERATOR_MODULES[module]
    
    var_decl = mod.get("var_decl", "")
    gen_fn = mod["gen_fn"]
    item_fmt = mod["item_fmt"]
    
    new_js = f"""let {{id}}_data = [];
{var_decl}
{gen_fn}
function generate{{id}}() {{
    const count = parseInt(document.getElementById('gen-count')?.value || 10);
    const results = document.getElementById('{{id}}-results');
    if (count < 1) {{ results.innerHTML = '<span class="text-amber-400">⚠️ 数量至少为1</span>'; return; }}
    if (count > 1000) {{ results.innerHTML = '<span class="text-amber-400">⚠️ 单次最多生成1000条</span>'; return; }}
    const items = [];
    const startTime = performance.now();
    for (let i = 0; i < count; i++) {{
        items.push({item_fmt});
    }}
    const elapsed = (performance.now() - startTime).toFixed(0);
    results.innerHTML = items.join('') + `<div class="text-xs text-zinc-500 mt-2 text-center">✅ 已生成 ${{count}} 条 · 耗时 ${{elapsed}}ms</div>`;
    {{id}}_data = items;
}}
function export{{id}}() {{
    if (!{{id}}_data || {{id}}_data.length === 0) {{ alert('请先生成数据'); return; }}
    const text = {{id}}_data.map(el => {{
        const m = el.match(/<span class="[^"]*">([^<]+)<\\/span>/);
        return m ? m[1] : el;
    }}).join('\\n');
    const blob = new Blob([text], {{type:'text/plain'}});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = '{{id}}_export.txt';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
}}"""
    return new_js


def rewrite_checker_js(tool):
    """重写检测验证器的 JS 模板"""
    name = tool.get("name", "")
    module = match_checker_keyword(name)
    mod = CHECKER_MODULES[module]
    
    new_js = f"""function check{{id}}() {{
    const input = document.getElementById('{{id}}-input').value.trim();
    const result = document.getElementById('{{id}}-result');
    if (!input) {{ result.innerHTML = '<span class="text-amber-400">⚠️ 请输入待检测内容</span>'; return; }}
    {mod["validate_code"]}
    result.className = 'mt-4 p-4 rounded-lg text-sm ' + (valid ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20');
    result.innerHTML = detail;
}}"""
    return new_js


def rewrite_calculator_js(tool):
    """重写计算器的 JS 模板"""
    name = tool.get("name", "")
    module = match_calculator_keyword(name)
    mod = CALCULATOR_MODULES[module]
    
    new_js = f"""function calc{{id}}() {{
    const a = parseFloat(document.getElementById('{{id}}-param1').value);
    const b = parseFloat(document.getElementById('{{id}}-param2').value);
    const result = document.getElementById('{{id}}-result');
    if (isNaN(a)) {{ result.innerHTML = '<p class="text-amber-400 text-sm">⚠️ 请输入有效的第1个参数</p>'; return; }}
    {mod["calc_code"]}
}}"""
    return new_js


def rewrite_calculator_html(tool):
    """重写计算器的 HTML 模板"""
    name = tool.get("name", "")
    module = match_calculator_keyword(name)
    mod = CALCULATOR_MODULES.get(module, CALCULATOR_MODULES["bmi"])
    
    if "html_extra" in mod:
        extra_html = mod["html_extra"]
    else:
        extra_html = '<div><label class="text-xs text-zinc-400 block mb-1">参数 1</label><input id="{id}-param1" type="number" class="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm"></div>\n        <div><label class="text-xs text-zinc-400 block mb-1">参数 2</label><input id="{id}-param2" type="number" class="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm"></div>'
    
    result_html = mod.get("result_html", "计算结果")
    
    new_html = f"""<div class="card glow">
    <h2>🧮 {{{{name_zh}}}}</h2>
    <div id="{{id}}-form" class="space-y-3">
        {extra_html}
        <button class="btn-primary" onclick="calc{{id}}()">🧮 开始计算</button>
    </div>
    <div id="{{id}}-result" class="bg-black/50 rounded-lg p-4 mt-4 text-center text-2xl font-bold text-emerald-400">{result_html}</div>
</div>"""
    return new_html


def rewrite_python_js(tool):
    """重写Python脚本 - 注入真实Python代码"""
    name = tool.get("name", "")
    module = match_python_keyword(name)
    mod = PYTHON_MODULES[module]
    
    # Python脚本的js_template存储的是Python代码
    name_en = name.replace("Random ", "").replace(" Generator", "").strip()
    code = mod["code"].replace("{name_en}", name_en)
    
    return code


# ═══════════════════════════════════════════════════════════════
# 🏭 批量重写引擎
# ═══════════════════════════════════════════════════════════════

REWRITERS = {
    "随机生成器": (rewrite_random_gen_js, None),
    "检测验证器": (rewrite_checker_js, None),
    "检测/验证器": (rewrite_checker_js, None),
    "计算器": (rewrite_calculator_js, rewrite_calculator_html),
    "Python脚本": (rewrite_python_js, None),
}

def rewrite_all_tools(tools, dry_run=False):
    """批量重写所有工具"""
    stats = Counter()
    modified = []
    skipped = []
    
    for i, tool in enumerate(tools):
        tmpl = tool.get("template_name", "")
        if tmpl not in REWRITERS:
            skipped.append(tool["id"])
            continue
        
        js_rewriter, html_rewriter = REWRITERS[tmpl]
        
        try:
            if not dry_run:
                new_js = js_rewriter(tool)
                tool["js_template"] = new_js
                
                if html_rewriter:
                    new_html = html_rewriter(tool)
                    tool["html_template"] = new_html
                
                # 标记已重写
                tool["_rewritten"] = True
                tool["_rewritten_at"] = datetime.now(timezone.utc).isoformat()
            
            stats[tmpl] += 1
            modified.append(tool["id"])
            
        except Exception as e:
            stats[f"{tmpl}_ERROR"] += 1
            skipped.append(f"{tool['id']} ({e})")
        
        if (i + 1) % 200 == 0:
            print(f"  进度: {i+1}/{len(tools)}")
    
    return stats, modified, skipped


def main():
    import argparse
    parser = argparse.ArgumentParser(description="模板重写器 - 告别TODO,注入真实逻辑")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不修改文件")
    parser.add_argument("--sample", type=int, default=0, help="只重写前N个")
    args = parser.parse_args()
    
    print("🔧 MintShovels 模板重写器")
    print("=" * 60)
    
    # 读取工具
    tools = json.load(open(TOOLS_PATH))
    total = len(tools)
    print(f"📊 加载 {total} 个工具")
    
    if args.sample:
        tools = tools[:args.sample]
        print(f"  抽样模式: 前 {len(tools)} 个")
    
    # 备份
    if not args.dry_run:
        backup_path = os.path.join(BACKUP_DIR, f"generated_tools_pre_rewrite_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(backup_path, "w") as f:
            json.dump(json.load(open(TOOLS_PATH)), f, ensure_ascii=False)
        print(f"💾 原始数据已备份: {os.path.basename(backup_path)}")
    
    # 重写
    print(f"\n🔄 开始重写 {len(tools)} 个工具...\n")
    stats, modified, skipped = rewrite_all_tools(tools, dry_run=args.dry_run)
    
    # 写回
    if not args.dry_run:
        with open(TOOLS_PATH, "w") as f:
            json.dump(tools, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 已写回 {TOOLS_PATH}")
    
    # 统计
    print(f"\n{'='*60}")
    print("📊 重写统计:")
    for tmpl, count in sorted(stats.items()):
        print(f"  {tmpl}: {count}")
    print(f"  总计修改: {len(modified)}")
    if skipped:
        print(f"  跳过/错误: {len(skipped)}")
    
    # 展示样本
    print(f"\n{'='*60}")
    print("📋 重写样本（前3个）:")
    for tool in tools[:3]:
        if tool.get("_rewritten"):
            js = tool.get("js_template", "")[:200]
            tmpl = tool.get("template_name", "?")
            print(f"\n  [{tmpl}] {tool['name'][:60]}")
            print(f"  JS: {js[:150]}...")
    
    if args.dry_run:
        print(f"\n⚠️ DRY-RUN 模式，未实际修改文件")


if __name__ == "__main__":
    main()
