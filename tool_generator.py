#!/usr/bin/env python3
"""
MintShovels 自动工具生成器 v1.0
===============================
读取需求雷达 PASS 结果 → 智能匹配模板 → 自动生成 HTML 工具 → 部署到 Cloudflare Pages

用法:
  python3 tool_generator.py                    # 读取 demand_report.json，生成新工具
  python3 tool_generator.py --text "JSON diff checker"  # 从单条需求生成
  python3 tool_generator.py --dry-run          # 只预览不生成文件
  python3 tool_generator.py --list             # 列出已有工具
"""

import json
import os
import re
import sys
import hashlib
import argparse
from datetime import datetime
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(SCRIPT_DIR, "tools")
REPORT_PATH = os.path.join(SCRIPT_DIR, "demand_report.json")
GENERATED_LOG = os.path.join(SCRIPT_DIR, "generated_tools_log.json")

# ═══════════════════════════════════════════════════════
# 工具模板库（每个模板是完整的独立 HTML 工具）
# ═══════════════════════════════════════════════════════

CSS_COMMON = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0d1117;color:#c9d1d9;display:flex;justify-content:center;padding:40px 20px;min-height:100vh}
.container{max-width:900px;width:100%}
h1{font-size:22px;color:#58a6ff;margin-bottom:6px}
.sub{font-size:13px;color:#8b949e;margin-bottom:24px}
.box{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;margin-bottom:16px}
.box h3{font-size:14px;color:#8b949e;margin-bottom:10px}
textarea{width:100%;min-height:180px;background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:12px;color:#c9d1d9;font-family:'SF Mono',Monaco,monospace;font-size:13px;resize:vertical;outline:none}
textarea:focus{border-color:#58a6ff}
pre{background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:14px;font-size:13px;overflow:auto;max-height:350px;white-space:pre-wrap;font-family:'SF Mono',Monaco,monospace;line-height:1.5}
.btn{background:#238636;color:#fff;border:none;padding:10px 20px;border-radius:6px;cursor:pointer;font-size:14px;font-weight:500;margin-right:8px;margin-top:12px;transition:background .2s}
.btn:hover{background:#2ea043}
.btn.copy{background:#21262d;border:1px solid #30363d;color:#c9d1d9}
.btn.copy:hover{background:#30363d}
.btn.sample{background:#1f2937;border:1px solid #374151;color:#9ca3af;font-size:12px;padding:6px 12px}
.btn.sample:hover{background:#374151}
.result-box{background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:14px;min-height:60px;font-family:'SF Mono',Monaco,monospace;font-size:13px}
.toast{position:fixed;top:20px;right:20px;background:#238636;color:#fff;padding:10px 18px;border-radius:6px;font-size:13px;opacity:0;transition:opacity .3s;z-index:999}
.toast.show{opacity:1}
.toast.error{background:#da3633}
.flex-row{display:flex;gap:12px;flex-wrap:wrap;align-items:center}
.flex-row input{padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#c9d1d9;font-size:14px;outline:none}
.flex-row input:focus{border-color:#58a6ff}
.badge{display:inline-block;padding:3px 8px;border-radius:12px;font-size:11px;font-weight:500}
.badge-auto{background:#1f2937;color:#9ca3af;border:1px solid #374151}
@media(max-width:700px){.flex-row{flex-direction:column;align-items:stretch}}
</style>"""

TOAST_JS = """<script>
function showToast(msg,isErr){var t=document.getElementById('toast');t.textContent=msg;t.className='toast'+(isErr?' error':'')+' show';setTimeout(function(){t.className='toast'},2000)}
function copyText(elId){var el=document.getElementById(elId);var txt=el.tagName==='TEXTAREA'||el.tagName==='INPUT'?el.value:el.textContent;navigator.clipboard.writeText(txt).then(function(){showToast('✅ 已复制')}).catch(function(){showToast('复制失败',true)})}
</script>"""

TOAST_HTML = '<div class="toast" id="toast"></div>'

# ─── 模板1: JSON 格式化/压缩器 ───
TEMPLATE_JSON_FORMATTER = {
    "name": "JSON Formatter",
    "keywords": ["json", "format", "beautify", "prettify", "minify", "compress", "pretty print"],
    "html": """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title}</title>
{CSS}
</head>
<body>
<div class="container">
<h1>📋 {title}</h1>
<p class="sub">{desc} <span class="badge badge-auto">Auto Generated</span></p>
<div class="box">
<h3>📥 JSON Input</h3>
<textarea id="input" placeholder='Paste JSON here...'></textarea>
<button class="btn sample" onclick="loadSample()">📎 Sample</button>
<button class="btn" onclick="format()" style="float:right">✨ Beautify</button>
<button class="btn" onclick="minify()" style="float:right">🗜️ Minify</button>
</div>
<div class="box">
<h3>📤 Output</h3>
<pre id="output"></pre>
<button class="btn copy" onclick="copyText('output')">📋 Copy</button>
</div>
</div>
{TOAST}
<script>
var sample='{{"name":"Alice","age":25,"skills":["js","python"],"address":{{"city":"NYC"}}}}';
function loadSample(){{document.getElementById("input").value=sample}}
function format(){{try{{var j=JSON.parse(document.getElementById("input").value);document.getElementById("output").textContent=JSON.stringify(j,null,2)}}catch(e){{showToast("Invalid JSON: "+e.message,true)}}}}
function minify(){{try{{var j=JSON.parse(document.getElementById("input").value);document.getElementById("output").textContent=JSON.stringify(j)}}catch(e){{showToast("Invalid JSON: "+e.message,true)}}}}
{TOAST_JS}
</script>
</body>
</html>"""
}

# ─── 模板2: Base64 编解码器 ───
TEMPLATE_BASE64 = {
    "name": "Base64 Encoder/Decoder",
    "keywords": ["base64", "encode", "decode", "encoding", "decoding", "b64"],
    "html": """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title}</title>
{CSS}
</head>
<body>
<div class="container">
<h1>🔐 {title}</h1>
<p class="sub">{desc} <span class="badge badge-auto">Auto Generated</span></p>
<div class="flex-row">
<button class="btn" onclick="encode64()">🔒 Encode</button>
<button class="btn" onclick="decode64()">🔓 Decode</button>
<button class="btn sample" onclick="swap()">🔄 Swap</button>
</div>
<div class="box" style="margin-top:16px">
<h3>📥 Input</h3>
<textarea id="input" placeholder="Enter text to encode or Base64 to decode..."></textarea>
</div>
<div class="box">
<h3>📤 Output</h3>
<pre id="output"></pre>
<button class="btn copy" onclick="copyText('output')">📋 Copy</button>
</div>
</div>
{TOAST}
<script>
function encode64(){{var t=document.getElementById("input").value;try{{document.getElementById("output").textContent=btoa(unescape(encodeURIComponent(t)))}}catch(e){{document.getElementById("output").textContent=btoa(t)}}}}
function decode64(){{var t=document.getElementById("input").value.trim();try{{document.getElementById("output").textContent=decodeURIComponent(escape(atob(t)))}}catch(e){{try{{document.getElementById("output").textContent=atob(t)}}catch(e2){{showToast("Invalid Base64: "+e2.message,true)}}}}}}
function swap(){{var inp=document.getElementById("input");var out=document.getElementById("output");var tmp=inp.value;inp.value=out.textContent;out.textContent=tmp}}
{TOAST_JS}
</script>
</body>
</html>"""
}

# ─── 模板3: 文本差异对比器 ───
TEMPLATE_DIFF = {
    "name": "Text Diff Checker",
    "keywords": ["diff", "compare", "difference", "comparison", "text compare", "text diff"],
    "html": """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title}</title>
{CSS}
</head>
<body>
<div class="container">
<h1>🔍 {title}</h1>
<p class="sub">{desc} <span class="badge badge-auto">Auto Generated</span></p>
<div class="box" style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
<div><h3>📝 Text A</h3>
<textarea id="inputA" placeholder="Paste original text..."></textarea></div>
<div><h3>📝 Text B</h3>
<textarea id="inputB" placeholder="Paste modified text..."></textarea></div>
</div>
<button class="btn" onclick="compare()">🔍 Compare</button>
<button class="btn sample" onclick="loadSample()">📎 Sample</button>
<div class="box" style="margin-top:16px">
<h3>📊 Result</h3>
<div class="result-box" id="output"></div>
<button class="btn copy" onclick="copyText('output')">📋 Copy</button>
</div>
</div>
{TOAST}
<script>
function loadSample(){{document.getElementById("inputA").value="The quick brown fox\\njumps over the lazy dog\\nHello World";document.getElementById("inputB").value="The quick brown cat\\njumps over the lazy dog\\nHello Universe"}}
function compare(){{var a=document.getElementById("inputA").value.split("\\n");var b=document.getElementById("inputB").value.split("\\n");var max=Math.max(a.length,b.length);var r=[];for(var i=0;i<max;i++){{var la=a[i]||"(empty)";var lb=b[i]||"(empty)";if(la===lb){{r.push('<span style="color:#7ee787">  '+la+'</span>')}}else{{r.push('<span style="color:#ff7b72">- '+la+'</span>');r.push('<span style="color:#79c0ff">+ '+lb+'</span>')}}}}document.getElementById("output").innerHTML=r.join("<br>")||"No differences found"}}
{TOAST_JS}
</script>
</body>
</html>"""
}

# ─── 模板4: 密码/随机值生成器 ───
TEMPLATE_GENERATOR = {
    "name": "Random Generator",
    "keywords": ["generate", "generator", "random", "password", "uuid", "guid", "token", "string generator", "lorem", "ipsum"],
    "html": """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title}</title>
{CSS}
</head>
<body>
<div class="container">
<h1>🎲 {title}</h1>
<p class="sub">{desc} <span class="badge badge-auto">Auto Generated</span></p>
<div class="box">
<h3>⚙️ Options</h3>
<div class="flex-row">
<label style="color:#8b949e;font-size:13px">Length: <input type="number" id="len" value="16" min="4" max="256" style="width:70px"></label>
<label style="color:#8b949e;font-size:13px">Count: <input type="number" id="cnt" value="5" min="1" max="100" style="width:70px"></label>
<label style="color:#8b949e;font-size:13px"><input type="checkbox" id="upper" checked> A-Z</label>
<label style="color:#8b949e;font-size:13px"><input type="checkbox" id="lower" checked> a-z</label>
<label style="color:#8b949e;font-size:13px"><input type="checkbox" id="digits" checked> 0-9</label>
<label style="color:#8b949e;font-size:13px"><input type="checkbox" id="symbols"> !@#$</label>
</div>
<button class="btn" onclick="generate()">🎲 Generate</button>
<button class="btn" onclick="generateUUID()">🆔 UUID</button>
</div>
<div class="box">
<h3>📤 Output</h3>
<pre id="output"></pre>
<button class="btn copy" onclick="copyText('output')">📋 Copy All</button>
</div>
</div>
{TOAST}
<script>
function getCharset(){{var c="";if(document.getElementById("upper").checked)c+="ABCDEFGHIJKLMNOPQRSTUVWXYZ";if(document.getElementById("lower").checked)c+="abcdefghijklmnopqrstuvwxyz";if(document.getElementById("digits").checked)c+="0123456789";if(document.getElementById("symbols").checked)c+="!@#$%^&*()-_=+[]{{}}|;:,.<>?";return c||"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"}}
function generate(){{var chars=getCharset();var len=parseInt(document.getElementById("len").value)||16;var cnt=parseInt(document.getElementById("cnt").value)||5;var r=[];for(var i=0;i<cnt;i++){{var s="";for(var j=0;j<len;j++)s+=chars[Math.floor(Math.random()*chars.length)];r.push(s)}}document.getElementById("output").textContent=r.join("\\n")}}
function generateUUID(){{var r=[];var cnt=parseInt(document.getElementById("cnt").value)||5;for(var i=0;i<cnt;i++)r.push("xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g,function(c){{var v=c==="x"?Math.random()*16|0:(Math.random()*16|0)&3|8;return v.toString(16)}}));document.getElementById("output").textContent=r.join("\\n")}}
{TOAST_JS}
</script>
</body>
</html>"""
}

# ─── 模板5: 文本大小写转换器 ───
TEMPLATE_TEXT_TOOL = {
    "name": "Text Transformer",
    "keywords": ["text", "case", "uppercase", "lowercase", "capitalize", "title case", "reverse", "count", "word count", "character count", "line", "sort", "deduplicate"],
    "html": """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title}</title>
{CSS}
</head>
<body>
<div class="container">
<h1>📝 {title}</h1>
<p class="sub">{desc} <span class="badge badge-auto">Auto Generated</span></p>
<div class="box">
<h3>📥 Input</h3>
<textarea id="input" placeholder="Enter your text here..."></textarea>
<div class="flex-row">
<button class="btn sample" onclick="toUpper()">AA UPPER</button>
<button class="btn sample" onclick="toLower()">aa lower</button>
<button class="btn sample" onclick="toTitle()">Aa Title</button>
<button class="btn sample" onclick="toSentence()">Sentence case</button>
<button class="btn sample" onclick="reverse()">↔ Reverse</button>
<button class="btn sample" onclick="sortLines()">⇅ Sort Lines</button>
<button class="btn sample" onclick="dedup()">⊘ Deduplicate</button>
</div>
</div>
<div class="box">
<h3>📤 Output</h3>
<pre id="output"></pre>
<button class="btn copy" onclick="copyText('output')">📋 Copy</button>
<span style="font-size:12px;color:#8b949e;margin-left:12px" id="stats"></span>
</div>
</div>
{TOAST}
<script>
var inp=function(){{return document.getElementById("input").value}};var out=function(t){{document.getElementById("output").textContent=t}};
function stats(){{var t=inp();document.getElementById("stats").textContent="Chars: "+t.length+" | Words: "+(t.trim()?t.trim().split(/\\s+/).length:0)+" | Lines: "+(t?t.split("\\n").length:0)}}
function toUpper(){{out(inp().toUpperCase());stats()}}
function toLower(){{out(inp().toLowerCase());stats()}}
function toTitle(){{out(inp().replace(/\\w\\S*/g,function(t){{return t.charAt(0).toUpperCase()+t.substr(1).toLowerCase()}}));stats()}}
function toSentence(){{out(inp().toLowerCase().replace(/(^\\s*\\w|[.!?]\\s+\\w)/g,function(t){{return t.toUpperCase()}}));stats()}}
function reverse(){{out(inp().split("").reverse().join(""));stats()}}
function sortLines(){{out(inp().split("\\n").sort().join("\\n"));stats()}}
function dedup(){{var lines=inp().split("\\n");var seen=new Set();out(lines.filter(function(l){{if(seen.has(l))return false;seen.add(l);return true}}).join("\\n"));stats()}}
{TOAST_JS}
</script>
</body>
</html>"""
}

# ─── 模板6: URL 编解码器 ───
TEMPLATE_URL = {
    "name": "URL Encoder/Decoder",
    "keywords": ["url", "encode", "decode", "uri", "query", "parameter", "percent encoding"],
    "html": """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title}</title>
{CSS}
</head>
<body>
<div class="container">
<h1>🔗 {title}</h1>
<p class="sub">{desc} <span class="badge badge-auto">Auto Generated</span></p>
<div class="flex-row">
<button class="btn" onclick="urlEncode()">🔒 Encode URL</button>
<button class="btn" onclick="urlDecode()">🔓 Decode URL</button>
<button class="btn sample" onclick="parseParams()">📊 Parse Query</button>
<button class="btn sample" onclick="swap()">🔄 Swap</button>
</div>
<div class="box" style="margin-top:16px">
<h3>📥 Input</h3>
<textarea id="input" placeholder="Enter URL or text to encode/decode..."></textarea>
</div>
<div class="box">
<h3>📤 Output</h3>
<pre id="output"></pre>
<button class="btn copy" onclick="copyText('output')">📋 Copy</button>
</div>
</div>
{TOAST}
<script>
function urlEncode(){{document.getElementById("output").textContent=encodeURIComponent(document.getElementById("input").value)}}
function urlDecode(){{try{{document.getElementById("output").textContent=decodeURIComponent(document.getElementById("input").value)}}catch(e){{showToast("Invalid URL encoding: "+e.message,true)}}}}
function parseParams(){{var t=document.getElementById("input").value;var q=t.indexOf("?");if(q===-1){{showToast("No query string found",true);return}}var params=new URLSearchParams(t.substring(q+1));var r=[];params.forEach(function(v,k){{r.push(k+" = "+v)}});document.getElementById("output").textContent=r.join("\\n")||"(no params)"}}
function swap(){{var i=document.getElementById("input");var o=document.getElementById("output");var tmp=i.value;i.value=o.textContent;o.textContent=tmp}}
{TOAST_JS}
</script>
</body>
</html>"""
}

# ─── 模板7: 正则表达式测试器 ───
TEMPLATE_REGEX = {
    "name": "Regex Tester",
    "keywords": ["regex", "regexp", "regular expression", "pattern", "match", "grep", "find", "search"],
    "html": """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title}</title>
{CSS}
</head>
<body>
<div class="container">
<h1>🔎 {title}</h1>
<p class="sub">{desc} <span class="badge badge-auto">Auto Generated</span></p>
<div class="box">
<h3>📝 Regex Pattern</h3>
<div class="flex-row">
<input type="text" id="pattern" placeholder="e.g. \\d{{3}}-\\d{{4}}" style="flex:1;font-family:'SF Mono',monospace">
<label style="color:#8b949e;font-size:13px"><input type="checkbox" id="flagG" checked> g</label>
<label style="color:#8b949e;font-size:13px"><input type="checkbox" id="flagI"> i</label>
<label style="color:#8b949e;font-size:13px"><input type="checkbox" id="flagM"> m</label>
</div>
</div>
<div class="box">
<h3>📥 Test Text</h3>
<textarea id="input" placeholder="Enter text to test regex against..."></textarea>
<button class="btn" onclick="testRegex()">🔍 Test</button>
<button class="btn copy" onclick="copyText('output')">📋 Copy</button>
</div>
<div class="box">
<h3>📤 Matches</h3>
<pre id="output"></pre>
</div>
</div>
{TOAST}
<script>
function testRegex(){{var p=document.getElementById("pattern").value;var t=document.getElementById("input").value;if(!p){{showToast("Enter a regex pattern",true);return}}try{{var flags="";if(document.getElementById("flagG").checked)flags+="g";if(document.getElementById("flagI").checked)flags+="i";if(document.getElementById("flagM").checked)flags+="m";var re=new RegExp(p,flags);var matches=t.match(re);if(matches){{document.getElementById("output").textContent=matches.length+" match(es) found:\\n"+matches.map(function(m,i){{return "  ["+i+"] "+m}}).join("\\n")}}else{{document.getElementById("output").textContent="No matches found"}}}}catch(e){{showToast("Invalid regex: "+e.message,true)}}}}
{TOAST_JS}
</script>
</body>
</html>"""
}

# ─── 模板8: 颜色转换器 ───
TEMPLATE_COLOR = {
    "name": "Color Converter",
    "keywords": ["color", "colour", "hex", "rgb", "hsl", "convert", "picker"],
    "html": """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title}</title>
{CSS}
</head>
<body>
<div class="container">
<h1>🎨 {title}</h1>
<p class="sub">{desc} <span class="badge badge-auto">Auto Generated</span></p>
<div class="box">
<h3>🎯 Pick or Enter Color</h3>
<div class="flex-row">
<input type="color" id="picker" value="#58a6ff" onchange="fromPicker()" style="width:50px;height:40px;padding:2px">
<input type="text" id="hexInput" placeholder="#58a6ff" style="flex:1;font-family:'SF Mono',monospace" oninput="fromHex()">
<button class="btn sample" onclick="randomColor()">🎲 Random</button>
</div>
</div>
<div class="box">
<h3>📊 Conversions</h3>
<div class="result-box" id="output">
<div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">
<div id="swatch" style="width:60px;height:60px;border-radius:8px;background:#58a6ff;border:1px solid #30363d"></div>
<div><strong>HEX:</strong> <span id="hexVal">#58a6ff</span><br>
<strong>RGB:</strong> <span id="rgbVal">rgb(88, 166, 255)</span><br>
<strong>HSL:</strong> <span id="hslVal">hsl(212, 100%, 67%)</span></div>
</div>
</div>
<button class="btn copy" onclick="copyAll()">📋 Copy All</button>
</div>
</div>
{TOAST}
<script>
function hexToRgb(h){{h=h.replace("#","");if(h.length===3)h=h.split("").map(function(c){{return c+c}}).join("");var r=parseInt(h.substring(0,2),16);var g=parseInt(h.substring(2,4),16);var b=parseInt(h.substring(4,6),16);return[r,g,b]}}
function rgbToHsl(r,g,b){{r/=255;g/=255;b/=255;var max=Math.max(r,g,b),min=Math.min(r,g,b);var h,s,l=(max+min)/2;if(max===min){{h=s=0}}else{{var d=max-min;s=l>0.5?d/(2-max-min):d/(max+min);switch(max){{case r:h=((g-b)/d+(g<b?6:0))/6;break;case g:h=((b-r)/d+2)/6;break;case b:h=((r-g)/d+4)/6;break}}h=Math.round(h*360)}}s=Math.round(s*100);l=Math.round(l*100);return[h,s,l]}}
function updateDisplay(hex){{var rgb=hexToRgb(hex);var hsl=rgbToHsl(rgb[0],rgb[1],rgb[2]);document.getElementById("swatch").style.background=hex;document.getElementById("hexVal").textContent=hex;document.getElementById("rgbVal").textContent="rgb("+rgb.join(", ")+")";document.getElementById("hslVal").textContent="hsl("+hsl.join(", ")+"%)";document.getElementById("hexInput").value=hex;document.getElementById("picker").value=hex}}
function fromPicker(){{updateDisplay(document.getElementById("picker").value)}}
function fromHex(){{var v=document.getElementById("hexInput").value.trim();if(/^#[0-9a-fA-F]{{3,6}}$/.test(v)){{updateDisplay(v)}}}}
function randomColor(){{var c="#"+Math.floor(Math.random()*16777215).toString(16).padStart(6,"0");updateDisplay(c)}}
function copyAll(){{var h=document.getElementById("hexVal").textContent;var r=document.getElementById("rgbVal").textContent;var s=document.getElementById("hslVal").textContent;navigator.clipboard.writeText(h+"\\n"+r+"\\n"+s).then(function(){{showToast("✅ Copied!")}})}}
{TOAST_JS}
</script>
</body>
</html>"""
}

# ─── 模板9: Markdown 预览器 ───
TEMPLATE_MARKDOWN = {
    "name": "Markdown Previewer",
    "keywords": ["markdown", "md", "preview", "render", "html convert"],
    "html": """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title}</title>
{CSS}
<style>.preview{{background:#fff;color:#24292f;padding:20px;border-radius:6px;line-height:1.6;min-height:100px}}
.preview h1,.preview h2,.preview h3{{margin-top:16px;margin-bottom:8px}}
.preview code{{background:#f6f8fa;padding:2px 6px;border-radius:3px;font-size:13px}}
.preview pre{{background:#f6f8fa;padding:14px;border-radius:6px;overflow:auto;font-size:13px}}
.preview blockquote{{border-left:3px solid #d0d7de;padding-left:12px;color:#656d76;margin:8px 0}}
.preview a{{color:#0969da}}
.preview table{{border-collapse:collapse;width:100%}}
.preview th,.preview td{{border:1px solid #d0d7de;padding:8px 12px;text-align:left}}
.panels{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
@media(max-width:700px){{.panels{{grid-template-columns:1fr}}}}</style>
</head>
<body>
<div class="container">
<h1>📝 {title}</h1>
<p class="sub">{desc} <span class="badge badge-auto">Auto Generated</span></p>
<div class="panels">
<div class="box">
<h3>📥 Markdown</h3>
<textarea id="input" placeholder="# Hello World&#10;&#10;This is **bold** and *italic*&#10;&#10;- List item 1&#10;- List item 2&#10;&#10;`inline code`&#10;&#10;> Blockquote"></textarea>
<button class="btn sample" onclick="loadSample()">📎 Sample</button>
</div>
<div class="box">
<h3>📤 Preview</h3>
<div class="preview" id="output"></div>
<button class="btn copy" onclick="copyHTML()" style="margin-top:12px">📋 Copy HTML</button>
</div>
</div>
</div>
{TOAST}
<script>
function loadSample(){{document.getElementById("input").value="# Hello World\\n\\nThis is **bold** and *italic* text.\\n\\n## Features\\n\\n- Fast rendering\\n- Simple syntax\\n- `inline code`\\n\\n> A wise quote\\n\\n| Col A | Col B |\\n|-------|-------|\\n| 1     | 2     |"}}
function simpleMD(md){{return md.replace(/^### (.+)$/gm,"<h3>$1</h3>").replace(/^## (.+)$/gm,"<h2>$1</h2>").replace(/^# (.+)$/gm,"<h1>$1</h1>").replace(/\\*\\*(.+?)\\*\\*/g,"<strong>$1</strong>").replace(/\\*(.+?)\\*/g,"<em>$1</em>").replace(/`(.+?)`/g,"<code>$1</code>").replace(/^> (.+)$/gm,"<blockquote>$1</blockquote>").replace(/^- (.+)$/gm,"<li>$1</li>").replace(/(<li>.*<\\/li>\\n?)+/g,"<ul>$&</ul>").replace(/\\n/g,"<br>")}}
document.getElementById("input").addEventListener("input",function(){{document.getElementById("output").innerHTML=simpleMD(this.value)}})
function copyHTML(){{var h=document.getElementById("output").innerHTML;navigator.clipboard.writeText(h).then(function(){{showToast("✅ HTML copied!")}})}}
loadSample()
{TOAST_JS}
</script>
</body>
</html>"""
}

# ─── 模板10: 通用数据转换器（CSV↔JSON↔YAML等） ───
TEMPLATE_DATA_CONVERTER = {
    "name": "Data Converter",
    "keywords": ["csv", "json", "yaml", "xml", "convert", "transform", "data", "table"],
    "html": """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title}</title>
{CSS}
</head>
<body>
<div class="container">
<h1>🔄 {title}</h1>
<p class="sub">{desc} <span class="badge badge-auto">Auto Generated</span></p>
<div class="box">
<h3>📥 Input</h3>
<textarea id="input" placeholder="Paste CSV, JSON, or tabular data..."></textarea>
<div class="flex-row">
<button class="btn" onclick="csvToJSON()">CSV → JSON</button>
<button class="btn" onclick="jsonToCSV()">JSON → CSV</button>
<button class="btn sample" onclick="csvToTable()">CSV → Table</button>
<button class="btn sample" onclick="loadSample()">📎 Sample CSV</button>
</div>
</div>
<div class="box">
<h3>📤 Output</h3>
<pre id="output"></pre>
<button class="btn copy" onclick="copyText('output')">📋 Copy</button>
</div>
</div>
{TOAST}
<script>
function loadSample(){{document.getElementById("input").value="name,age,city\\nAlice,25,NYC\\nBob,30,LA\\nCharlie,35,Chicago"}}
function csvToJSON(){{var lines=document.getElementById("input").value.trim().split("\\n");if(lines.length<2){{showToast("Need at least header+1 row",true);return}}var headers=lines[0].split(",").map(function(h){{return h.trim()}});var result=[];for(var i=1;i<lines.length;i++){{var vals=lines[i].split(",");var obj={{}};headers.forEach(function(h,j){{obj[h]=vals[j]?vals[j].trim():""}});result.push(obj)}}document.getElementById("output").textContent=JSON.stringify(result,null,2)}}
function jsonToCSV(){{try{{var data=JSON.parse(document.getElementById("input").value);if(!Array.isArray(data))data=[data];if(data.length===0){{showToast("Empty data",true);return}}var keys=Object.keys(data[0]);var lines=[keys.join(",")];data.forEach(function(row){{lines.push(keys.map(function(k){{var v=row[k];if(typeof v==="string"&&(v.indexOf(",")!==-1||v.indexOf('"')!==-1))return '"'+v.replace(/"/g,'""')+'"';return v}}).join(","))}});document.getElementById("output").textContent=lines.join("\\n")}}catch(e){{showToast("Invalid JSON: "+e.message,true)}}}}
function csvToTable(){{var lines=document.getElementById("input").value.trim().split("\\n");if(lines.length===0)return;var headers=lines[0].split(",");var h="<tr>"+headers.map(function(h){{return"<th>"+h.trim()+"</th>"}}).join("")+"</tr>";var rows="";for(var i=1;i<lines.length;i++){{rows+="<tr>"+lines[i].split(",").map(function(c){{return"<td>"+c.trim()+"</td>"}}).join("")+"</tr>"}}document.getElementById("output").innerHTML="<table style='border-collapse:collapse;width:100%'><thead>"+h+"</thead><tbody>"+rows+"</tbody></table>"}}
{TOAST_JS}
</script>
</body>
</html>"""
}

# ═══════════════════════════════════════════════════════
# 模板匹配逻辑
# ═══════════════════════════════════════════════════════

TEMPLATES = [
    TEMPLATE_JSON_FORMATTER,
    TEMPLATE_BASE64,
    TEMPLATE_DIFF,
    TEMPLATE_GENERATOR,
    TEMPLATE_TEXT_TOOL,
    TEMPLATE_URL,
    TEMPLATE_REGEX,
    TEMPLATE_COLOR,
    TEMPLATE_MARKDOWN,
    TEMPLATE_DATA_CONVERTER,
]


def score_template(template: dict, text: str) -> int:
    """计算模板与需求文本的匹配分数"""
    text_lower = text.lower()
    score = 0
    for kw in template["keywords"]:
        if kw.lower() in text_lower:
            score += 10  # 精确匹配高分
        # 部分匹配
        parts = kw.split()
        for part in parts:
            if len(part) >= 3 and part.lower() in text_lower:
                score += 3
    return score


def find_best_template(text: str):
    """找到最佳匹配的模板"""
    best = None
    best_score = 0
    for tmpl in TEMPLATES:
        s = score_template(tmpl, text)
        if s > best_score:
            best_score = s
            best = tmpl
    return best, best_score


def sanitize_filename(name: str) -> str:
    """将工具名转为安全的文件名"""
    name = name.lower().strip()
    name = re.sub(r'[^a-z0-9]+', '_', name)
    name = name.strip('_')
    if len(name) > 50:
        name = name[:50]
    if not name:
        name = f"tool_{hashlib.md5(name.encode()).hexdigest()[:8]}"
    return name


def extract_tool_title(text: str) -> str:
    """从需求文本中提取工具标题"""
    # 去掉常见的需求前缀
    text = re.sub(r'^(is there|looking for|anyone know|does anyone|wish there was|need a|want a|i need|i want)\s+a?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^(a|an|the)\s+', '', text, flags=re.IGNORECASE)
    # 取前8个词
    words = text.split()[:8]
    title = ' '.join(words)
    # 首字母大写
    title = ' '.join(w.capitalize() if i == 0 or w.lower() not in ('a', 'an', 'the', 'to', 'for', 'of', 'in', 'on', 'at', 'and', 'or', 'but', 'with') else w.lower() for i, w in enumerate(title.split()))
    if len(title) > 60:
        title = title[:57] + '...'
    return title


def generate_tool_html(text: str, template: dict, title: str, desc: str) -> str:
    """根据模板生成完整 HTML"""
    html = template["html"]
    html = html.replace("{title}", title)
    html = html.replace("{desc}", desc or f"Online {title.lower()}. Fast, free, no signup required.")
    html = html.replace("{CSS}", CSS_COMMON)
    html = html.replace("{TOAST}", TOAST_HTML)
    html = html.replace("{TOAST_JS}", TOAST_JS)
    return html


def load_existing_tools() -> dict:
    """加载已有工具列表（避免重复生成）"""
    tools = {}
    if not os.path.isdir(TOOLS_DIR):
        return tools
    for fname in os.listdir(TOOLS_DIR):
        if fname.endswith('.html') and fname.startswith('auto_'):
            fpath = os.path.join(TOOLS_DIR, fname)
            # 读取 title 标签
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    content = f.read(5000)
                    m = re.search(r'<title>(.+?)</title>', content)
                    if m:
                        tools[fname] = {
                            "file": fname,
                            "title": m.group(1),
                            "path": fpath,
                        }
            except Exception:
                pass
    return tools


def load_generated_log() -> list:
    """加载已生成记录"""
    if os.path.exists(GENERATED_LOG):
        try:
            with open(GENERATED_LOG, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_generated_log(log: list):
    with open(GENERATED_LOG, 'w', encoding='utf-8') as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def load_demand_report() -> list:
    """从 demand_report.json 加载 PASS 的需求"""
    if not os.path.exists(REPORT_PATH):
        print("⚠️  demand_report.json 不存在")
        return []

    with open(REPORT_PATH, 'r', encoding='utf-8') as f:
        report = json.load(f)

    results = report.get("results", [])
    passed = []
    for r in results:
        cls = r.get("classification", {})
        if cls.get("verdict") == "PASS" or cls.get("pass"):
            passed.append(r)
    return passed


def generate_from_demand(demand_text: str, dry_run: bool = False) -> Optional[str]:
    """从单条需求生成工具"""
    template, score = find_best_template(demand_text)
    if not template or score < 5:
        print(f"  ⏭️  无匹配模板 (score={score}): {demand_text[:60]}")
        return None

    title = extract_tool_title(demand_text)
    filename = "auto_" + sanitize_filename(title) + ".html"

    # 检查是否已存在
    existing = load_existing_tools()
    generated_log = load_generated_log()
    generated_texts = {item.get("text", "") for item in generated_log}

    if demand_text in generated_texts:
        print(f"  ⏭️  已生成过: {title}")
        return None

    if filename in existing:
        print(f"  ⏭️  文件已存在: {filename}")
        return None

    desc = demand_text[:120]
    html = generate_tool_html(demand_text, template, title, desc)

    if dry_run:
        print(f"  🔍 [DRY-RUN] 将生成: {filename} | 标题: {title} | 模板: {template['name']} (score={score})")
        return filename

    # 写入文件
    filepath = os.path.join(TOOLS_DIR, filename)
    os.makedirs(TOOLS_DIR, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)

    # 记录日志
    generated_log.append({
        "text": demand_text,
        "title": title,
        "file": filename,
        "template": template["name"],
        "score": score,
        "generated_at": datetime.now().isoformat(),
    })
    save_generated_log(generated_log)

    print(f"  ✅ 生成: {filename} | {title} | 模板: {template['name']} (score={score})")
    return filename


def generate_from_report(dry_run: bool = False) -> list:
    """从 demand_report.json 批量生成工具"""
    passed = load_demand_report()
    if not passed:
        print("📭 没有 PASS 的需求可生成")
        return []

    print(f"\n🔧 自动工具生成器")
    print(f"{'='*50}")
    print(f"📊 PASS 需求数: {len(passed)}")
    print(f"{'='*50}\n")

    generated = []
    for item in passed:
        text = item.get("text", "")
        canonical = item.get("classification", {}).get("canonical_name", "")
        demand = canonical or text
        result = generate_from_demand(demand, dry_run=dry_run)
        if result:
            generated.append(result)
        if not dry_run:
            # 生成间短暂延迟，避免过快
            import time
            time.sleep(0.1)

    print(f"\n{'='*50}")
    if dry_run:
        print(f"🔍 预览: 将生成 {len(generated)} 个工具")
    else:
        print(f"✅ 生成完成: {len(generated)} 个新工具")
    print(f"{'='*50}")
    return generated


def main():
    parser = argparse.ArgumentParser(description="MintShovels 自动工具生成器")
    parser.add_argument("--text", type=str, help="从单条文本生成工具")
    parser.add_argument("--dry-run", action="store_true", help="只预览不生成")
    parser.add_argument("--list", action="store_true", help="列出已生成的工具")
    args = parser.parse_args()

    if args.list:
        tools = load_existing_tools()
        auto_tools = {k: v for k, v in tools.items() if k.startswith('auto_')}
        print(f"\n🤖 自动生成工具 ({len(auto_tools)} / {len(tools)} total):")
        for fname, info in sorted(auto_tools.items()):
            print(f"  {fname} → {info['title']}")
        if not auto_tools:
            print("  (暂无自动生成工具)")
        return

    if args.text:
        generate_from_demand(args.text, dry_run=args.dry_run)
        return

    # 默认：从报告生成
    generate_from_report(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
