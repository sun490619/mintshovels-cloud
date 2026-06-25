// 16个工具的深度功能测试 - 使用 Playwright 直接操作
import { chromium } from 'playwright';
import fs from 'fs';

const BASE = 'http://localhost:8765/tools';

const tests = [
  {
    id: 'fstring_converter', name: 'Python f-string 转换器',
    async test(page) {
      await page.fill('#input', "name = 'World'\nprint('Hello, %s!' % name)");
      await page.click('button:has-text("转换")');
      await page.waitForTimeout(300);
      const out = await page.textContent('#output');
      return out.includes('f"') ? 'PASS: f-string generated' : 'FAIL: no f-string';
    }
  },
  {
    id: 'json_schema_generator', name: 'JSON Schema 生成器',
    async test(page) {
      await page.fill('#input', '{"name":"Alice","age":25,"tags":["dev"]}');
      await page.click('button:has-text("生成 Schema")');
      await page.waitForTimeout(300);
      const out = await page.textContent('#output');
      return out.includes('properties') && out.includes('type') ? 'PASS: schema generated' : 'FAIL: ' + out.substring(0,60);
    }
  },
  {
    id: 'js_formatter', name: 'JS 格式化',
    async test(page) {
      await page.fill('#input', 'function f(){return 1;}const x=2;');
      await page.click('button:has-text("格式化")');
      await page.waitForTimeout(300);
      const out = await page.textContent('#output');
      // Output should retain function keyword and be readable
      return out.includes('function') && out.includes('return') ? 'PASS: formatted' : 'FAIL: ' + out.substring(0,60);
    }
  },
  {
    id: 'regexp_lookahead', name: '正则预查生成器',
    async test(page) {
      await page.fill('#matchWord', 'foo');
      await page.fill('#excludeWord', 'bar');
      await page.click('button:has-text("生成正则")');
      await page.waitForTimeout(300);
      const pattern = await page.textContent('#pattern');
      return pattern.includes('?!') ? 'PASS: regex built' : 'FAIL: ' + pattern;
    }
  },
  {
    id: 'csharp_getter_setter', name: 'C# Getter/Setter',
    async test(page) {
      await page.click('button:has-text("生成代码")');
      await page.waitForTimeout(300);
      const out = await page.textContent('#output');
      return out.includes('public class') && out.includes('get') ? 'PASS: C# code generated' : 'FAIL: ' + out.substring(0,60);
    }
  },
  {
    id: 'css_computed_analyzer', name: 'CSS 计算属性分析',
    async test(page) {
      const rows = await page.$$eval('#resultBody tr', rows => rows.length);
      return rows > 3 ? `PASS: ${rows} properties analyzed` : `FAIL: only ${rows} rows`;
    }
  },
  {
    id: 'python_tree_generator', name: 'Python 树结构生成',
    async test(page) {
      const out = await page.textContent('#output');
      return out.includes('class') && out.includes('def __init__') ? 'PASS: Python code generated' : 'FAIL: ' + out.substring(0,60);
    }
  },
  {
    id: 'jquery_events', name: 'jQuery 事件速查表',
    async test(page) {
      const rows = await page.$$eval('#tbody tr', rows => rows.length);
      return rows >= 40 ? `PASS: ${rows} events rendered` : `FAIL: ${rows} rows`;
    }
  },
  {
    id: 'svg_path_extractor', name: 'SVG Path 提取器',
    async test(page) {
      await page.click('button:has-text("示例")');
      await page.waitForTimeout(500);
      const items = await page.$$eval('.path-item', items => items.length);
      return items >= 3 ? `PASS: ${items} paths extracted` : `FAIL: ${items} paths`;
    }
  },
  {
    id: 'file_line_extractor', name: '文件行提取器',
    async test(page) {
      // loadSample auto-runs on load
      await page.click('button:has-text("提取")');
      await page.waitForTimeout(300);
      const out = await page.textContent('#output');
      return out.includes(':') && out.length > 20 ? 'PASS: lines extracted' : 'FAIL: ' + out.substring(0,60);
    }
  },
  {
    id: 'world_map_generator', name: '世界地图生成器',
    async test(page) {
      await page.waitForTimeout(500);
      const painted = await page.evaluate(() => {
        const c = document.getElementById('canvas');
        const ctx = c.getContext('2d');
        const d = ctx.getImageData(0, 0, c.width, c.height).data;
        let r0 = d[0];
        for (let i = 4; i < 500; i += 4) if (d[i] !== r0) return true;
        return false;
      });
      return painted ? 'PASS: map rendered' : 'FAIL: canvas blank';
    }
  },
  {
    id: 'typing_macro', name: '打字宏脚本生成',
    async test(page) {
      const out = await page.textContent('#output');
      const ok = out.includes('pyautogui') || out.includes('SendInput') || out.includes('typeHuman');
      return ok ? 'PASS: script generated' : 'FAIL: ' + out.substring(0,60);
    }
  },
  {
    id: 'sql_formatter', name: 'SQL 格式化',
    async test(page) {
      await page.fill('#input', 'select name,age from users where id=1');
      await page.click('button:has-text("格式化")');
      await page.waitForTimeout(300);
      const out = await page.textContent('#output');
      // Check output has SELECT and FROM keywords (uppercased)
      return out.includes('SELECT') && out.includes('FROM') ? 'PASS: SQL formatted' : 'FAIL: ' + out.substring(0,60);
    }
  },
  {
    id: 'dotnet_cli_parser', name: '.NET CLI 解析器',
    async test(page) {
      const out = await page.textContent('#output');
      return out.includes('public class') && out.includes('Parse') ? 'PASS: C# code generated' : 'FAIL: ' + out.substring(0,60);
    }
  },
  {
    id: 'java_object_mapper', name: 'Java 对象映射',
    async test(page) {
      const out = await page.textContent('#output');
      return out.includes('Mapper') || out.includes('public class') ? 'PASS: Java code generated' : 'FAIL: ' + out.substring(0,60);
    }
  },
  {
    id: 'code_generator_hub', name: '多合一代码工具箱',
    async test(page) {
      // Test CMake (default active tab)
      await page.click('button:has-text("生成")');
      await page.waitForTimeout(300);
      const cmake = await page.textContent('#cmakeOut');
      const cOk = cmake.includes('#!/bin/bash') || cmake.includes('@echo off');
      
      // Test tab 2 via evaluate
      await page.evaluate(() => switchTab('include'));
      await page.waitForTimeout(300);
      await page.fill('#cppInput', '#include <iostream>\n#include "myclass.h"\nint main(){}');
      await page.click('button:has-text("分析")');
      await page.waitForTimeout(300);
      const incl = await page.textContent('#includeOut');
      const iOk = incl.includes('标准库') || incl.includes('Include');
      
      // Test tab 3 via evaluate
      await page.evaluate(() => switchTab('diff'));
      await page.waitForTimeout(300);
      await page.fill('#dirA', 'a.txt\nb.txt');
      await page.fill('#dirB', 'a.txt\nc.txt');
      await page.click('button:has-text("对比")');
      await page.waitForTimeout(300);
      const diff = await page.textContent('#diffOut');
      const dOk = diff.includes('相同') || diff.includes('A');
      
      let r = [];
      if (cOk) r.push('CMake OK'); else r.push('CMake FAIL');
      if (iOk) r.push('Include OK'); else r.push('Include FAIL');
      if (dOk) r.push('Diff OK'); else r.push('Diff FAIL');
      return r.filter(x => x.includes('OK')).length >= 2 ? `PASS: ${r.join(', ')}` : `FAIL: ${r.join(', ')}`;
    }
  }
];

async function run() {
  const browser = await chromium.launch({ headless: true });
  const results = [];
  
  console.log('='.repeat(60));
  console.log('MintShovels 工具库 - 深度功能测试');
  console.log('='.repeat(60));
  
  for (let i = 0; i < tests.length; i++) {
    const t = tests[i];
    const page = await browser.newPage();
    try {
      process.stdout.write(`[${i+1}/${tests.length}] ${t.name} ... `);
      await page.goto(`${BASE}/${t.id}.html`, { waitUntil: 'networkidle', timeout: 10000 });
      await page.waitForTimeout(500);
      
      // Check for console errors
      const errors = [];
      page.on('pageerror', err => errors.push(err.message));
      
      const result = await t.test(page);
      const passed = result.startsWith('PASS');
      
      // Also check if there were JS errors
      if (errors.length > 0 && errors.some(e => !e.includes('favicon'))) {
        console.log(`🔴 FAIL | JS Error: ${errors[0].substring(0,60)}`);
        results.push({ id: t.id, name: t.name, passed: false, detail: 'JS Error: ' + errors[0] });
      } else {
        console.log(`${passed ? '🟢' : '🔴'} ${result}`);
        results.push({ id: t.id, name: t.name, passed, detail: result });
      }
    } catch (e) {
      console.log(`🔴 ERROR: ${e.message.substring(0,80)}`);
      results.push({ id: t.id, name: t.name, passed: false, detail: e.message.substring(0,100) });
    } finally {
      await page.close();
    }
  }
  
  await browser.close();
  
  // Summary
  const passed = results.filter(r => r.passed).length;
  console.log('\n' + '='.repeat(60));
  console.log(`测试结果: ${passed}/${results.length} 通过 (${Math.round(passed/results.length*100)}%)`);
  console.log('='.repeat(60));
  for (const r of results) {
    console.log(`  ${r.passed ? '🟢' : '🔴'} ${r.name}: ${r.detail}`);
  }
  
  // Save results
  const report = {
    timestamp: new Date().toISOString(),
    passed,
    total: results.length,
    rate: Math.round(passed / results.length * 100),
    results
  };
  fs.writeFileSync('test_results.json', JSON.stringify(report, null, 2));
  console.log('\n结果已保存到 test_results.json');
  
  process.exit(passed === results.length ? 0 : 1);
}

run().catch(e => { console.error(e); process.exit(1); });
