#!/usr/bin/env python3
"""
MintShovels 一键 ID 提取脚本 (全自动版)
→ 打开浏览器 → 你登录 → 自动抓取所有 ID → 自动保存配置
"""

import json, time, re, os, sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mintshovels_config.json')
CHROME_PROFILE = os.path.join(os.path.dirname(__file__), 'chrome_profile')
RESULTS_FILE = os.path.join(os.path.dirname(__file__), 'extracted_ids.json')

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def save_results(results):
    with open(RESULTS_FILE, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

def load_results():
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE) as f:
            return json.load(f)
    return {}

def is_logged_in(driver, url_keyword):
    """检测是否已登录"""
    try:
        body = driver.find_element(By.TAG_NAME, 'body').text.lower()
        # 排除登录页面
        has_signin = 'sign in' in body or 'sign up' in body or '登录' in body
        has_keyword = url_keyword.lower() in body
        return has_keyword and not has_signin
    except Exception:
        return False

def wait_page_ready(driver, timeout=15):
    """等待页面加载完成"""
    try:
        for _ in range(timeout * 2):
            state = driver.execute_script('return document.readyState')
            if state == 'complete':
                time.sleep(1)
                return True
            time.sleep(0.5)
    except Exception:
        pass
    return True

def extract_text(driver):
    """提取页面可见文本"""
    try:
        return driver.find_element(By.TAG_NAME, 'body').text
    except Exception:
        return ""

# ==================== GA4 提取 ====================
def step_ga4(driver, results):
    print("\n" + "="*60)
    print("📊 [1/4] Google Analytics GA4")
    print("="*60)
    
    print("  导航到 analytics.google.com...")
    driver.get('https://analytics.google.com/analytics/web/')
    wait_page_ready(driver)
    
    # 等待登录
    print("  ⏳ 等待登录（请在浏览器中完成）...")
    for i in range(120):  # 最多等 4 分钟
        time.sleep(2)
        try:
            # 检测是否到了 GA 主页
            js_check = driver.execute_script("""
                return document.title.includes('Analytics') && 
                       !document.querySelector('[data-authuser]') &&
                       document.querySelector('a[href*="property"]') !== null;
            """)
            if js_check:
                print("  ✅ GA 已加载！")
                time.sleep(3)
                break
            
            # 也检查是否在属性选择页面
            text = extract_text(driver).lower()
            if 'analytics' in text and 'account' in text and 'property' in text:
                print("  ✅ GA 仪表盘已加载！")
                time.sleep(3)
                break
        except Exception:
            pass
        
        if i % 15 == 0:
            print(f"    已等待 {i*2} 秒...")
    
    # 提取数据
    print("\n  🔍 提取 GA4 数据...")
    
    # 方法1: 从 localStorage
    try:
        ls_data = driver.execute_script("""
            var keys = Object.keys(localStorage);
            var data = {};
            keys.forEach(function(k) {
                try {
                    var v = localStorage.getItem(k);
                    if (v && v.length < 500 && (k.includes('property') || k.includes('account') || k.includes('analytics'))) {
                        data[k] = v;
                    }
                } catch(e) {}
            });
            return JSON.stringify(data);
        """)
        print(f"    相关 localStorage: {ls_data[:500]}")
    except Exception as e:
        print(f"    localStorage 读取失败: {e}")
    
    # 方法2: 从页面文本提取 G-XXXXXXXXXX
    try:
        text = extract_text(driver)
        gids = list(set(re.findall(r'G-[A-Z0-9]{8,12}', text)))
        pids = list(set(re.findall(r'properties/\d+', text)))
        
        if gids:
            print(f"\n    找到 GA4 Measurement IDs: {gids}")
            results['ga4_measurement_id'] = gids[0]
            print(f"    ✅ 默认选择: {gids[0]}")
        
        if pids:
            print(f"    找到 Property IDs: {pids}")
            results['ga4_property_id'] = pids[0]
    except Exception as e:
        print(f"    页面文本提取失败: {e}")
    
    # 方法3: 等待并获取整个页面 HTML 中的 ID
    if not results.get('ga4_measurement_id'):
        try:
            html = driver.page_source
            gids = list(set(re.findall(r'G-[A-Z0-9]{8,12}', html)))
            if gids:
                results['ga4_measurement_id'] = gids[0]
                print(f"    HTML中提取: {gids[0]}")
        except Exception:
            pass
    
    # 更新配置
    if results.get('ga4_measurement_id'):
        config = load_config()
        config['ga4']['measurement_id'] = results['ga4_measurement_id']
        if results.get('ga4_property_id'):
            config['ga4']['property_id'] = results['ga4_property_id']
        save_config(config)
        print(f"\n  ✅ GA4 已保存到配置!")
        return True
    else:
        print(f"\n  ⚠️ 未能自动提取 GA4 ID")
        print(f"  💡 提示: 在 GA 页面左侧 → 管理 → 数据流 → 找到 G- 开头的测量 ID")
        return False


# ==================== Clarity 提取 ====================
def step_clarity(driver, results):
    print("\n" + "="*60)
    print("🎯 [2/4] Microsoft Clarity")
    print("="*60)
    
    print("  导航到 clarity.microsoft.com...")
    driver.get('https://clarity.microsoft.com/projects')
    wait_page_ready(driver)
    
    print("  ⏳ 等待登录和项目列表加载...")
    for i in range(90):
        time.sleep(2)
        try:
            text = extract_text(driver)
            if 'project' in text.lower() and ('id' in text.lower() or 'mint' in text.lower()):
                print("  ✅ Clarity 已加载！")
                time.sleep(3)
                break
            if 'dashboard' in text.lower() and 'clarity' in text.lower():
                print("  ✅ Clarity 仪表盘已加载！")
                time.sleep(3)
                break
        except Exception:
            pass
        if i % 15 == 0:
            print(f"    已等待 {i*2} 秒...")
    
    # 尝试从 API 获取
    try:
        result = driver.execute_script("""
            return fetch('https://clarity.microsoft.com/api/projects', {
                credentials: 'include'
            }).then(r => r.text());
        """)
        if result:
            data = json.loads(result) if isinstance(result, str) else result
            projects = data if isinstance(data, list) else data.get('value', [])
            
            if projects:
                print(f"\n    找到 {len(projects)} 个项目:")
                for p in projects:
                    pid = p.get('id', '?')
                    pname = p.get('name', p.get('siteName', '?'))
                    print(f"      ID: {pid} | 名称: {pname}")
                    
                    if 'mint' in str(pname).lower() or 'shovel' in str(pname).lower():
                        results['clarity_project_id'] = pid
                        print(f"      ⭐ 匹配 MintShovels!")
                
                if not results.get('clarity_project_id') and projects:
                    results['clarity_project_id'] = projects[0].get('id', '')
                    print(f"      选择第一个: {results['clarity_project_id']}")
    except Exception as e:
        print(f"    API 调用失败: {e}")
    
    # 从页面文本提取
    if not results.get('clarity_project_id'):
        try:
            text = extract_text(driver)
            ids = list(set(re.findall(r'[a-z0-9]{20,30}', text)))
            if ids:
                print(f"    页面中找到候选 ID: {ids[:5]}")
                results['clarity_project_id'] = ids[0]
        except Exception:
            pass
    
    if results.get('clarity_project_id'):
        config = load_config()
        config['clarity']['project_id'] = results['clarity_project_id']
        save_config(config)
        print(f"\n  ✅ Clarity 已保存!")
        return True
    
    print(f"\n  ⚠️ 未能自动提取 Clarity 项目 ID")
    return False


# ==================== BING 提取 ====================
def step_bing(driver, results):
    print("\n" + "="*60)
    print("🔍 [3/4] Bing Webmaster Tools")
    print("="*60)
    
    print("  导航到 bing.com/webmasters...")
    driver.get('https://www.bing.com/webmasters/home/dashboard')
    wait_page_ready(driver)
    
    print("  ⏳ 等待登录...")
    for i in range(90):
        time.sleep(2)
        try:
            text = extract_text(driver).lower()
            if 'dashboard' in text and 'search performance' in text.lower():
                print("  ✅ Bing Webmaster 仪表盘已加载！")
                time.sleep(3)
                break
        except Exception:
            pass
        if i % 15 == 0:
            print(f"    已等待 {i*2} 秒...")
    
    # 导航到 API 页面
    print("  导航到 API 密钥页面...")
    driver.get('https://www.bing.com/webmasters/about/api')
    time.sleep(5)
    
    # 尝试生成或获取 API Key
    try:
        text = extract_text(driver)
        api_keys = list(set(re.findall(r'[a-f0-9]{32}', text)))
        if api_keys:
            print(f"\n    找到 API Key: {api_keys[0]}")
            results['bing_api_key'] = api_keys[0]
    except Exception:
        pass
    
    if results.get('bing_api_key'):
        config = load_config()
        config['bing']['api_key'] = results['bing_api_key']
        save_config(config)
        print(f"\n  ✅ Bing API Key 已保存!")
        return True
    
    print(f"\n  ⚠️ 未能自动提取 Bing API Key")
    print(f"  💡 提示: 在页面中点击 'Generate API Key' 按钮")
    return False


# ==================== Cloudflare Token ====================
def step_cloudflare(driver, results):
    print("\n" + "="*60)
    print("☁️  [4/4] Cloudflare API Token")
    print("="*60)
    
    print("  导航到 Cloudflare API Tokens 页面...")
    driver.get('https://dash.cloudflare.com/profile/api-tokens')
    wait_page_ready(driver)
    
    print("  ⏳ 等待登录...")
    for i in range(90):
        time.sleep(2)
        try:
            text = extract_text(driver)
            if 'api tokens' in text.lower() and 'create token' in text.lower():
                print("  ✅ Cloudflare API Tokens 页面已加载！")
                time.sleep(3)
                break
            if 'dashboard' in text.lower() and 'manage your account' in text.lower():
                print("  ✅ Cloudflare 已加载！")
                time.sleep(3)
                break
        except Exception:
            pass
        if i % 15 == 0:
            print(f"    已等待 {i*2} 秒...")
    
    print("\n  📋 请在浏览器中手动创建 API Token:")
    print("     1. 点击 Create Token → Custom Token")
    print("     2. 权限: Analytics → Read")
    print("     3. 资源: Include → Specific zone → mintshovels.com")
    print("     4. 创建后复制 Token 值")
    print()
    print("  ⏳ 等待 Token 被保存到剪贴板或页面...")
    
    # 尝试自动从页面复制
    for i in range(60):
        time.sleep(2)
        try:
            # 检查页面上是否显示了新 token
            elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'cfut_') or contains(text(), 'Bearer')]")
            for el in elements:
                text = el.text
                token_match = re.search(r'[A-Za-z0-9_-]{30,60}', text)
                if token_match and len(token_match.group()) > 30:
                    results['cloudflare_token'] = token_match.group()
                    print(f"  ✅ 自动检测到 Token: {results['cloudflare_token'][:20]}...")
                    break
            
            # 也尝试从 value 属性获取
            inputs = driver.find_elements(By.TAG_NAME, 'input')
            for inp in inputs:
                val = inp.get_attribute('value')
                if val and len(val) > 30 and 'cf' in val.lower():
                    results['cloudflare_token'] = val
                    print(f"  ✅ 从输入框获取 Token: {val[:20]}...")
                    break
        except Exception:
            pass
        
        if results.get('cloudflare_token'):
            break
        
        if i % 15 == 0 and i > 0:
            print(f"    已等待 {i*2} 秒，如果已创建 Token 请确认...")
    
    if results.get('cloudflare_token'):
        config = load_config()
        config['cloudflare']['api_token'] = results['cloudflare_token']
        save_config(config)
        print(f"\n  ✅ Cloudflare Token 已保存!")
        return True
    
    print(f"\n  ⚠️ 未能自动获取 Cloudflare Token")
    return False


# ==================== 主流程 ====================
def main():
    # 加载已保存的结果（支持断点续跑）
    results = load_results()
    
    print("""
╔══════════════════════════════════════════════════════╗
║     MintShovels 一键 ID 提取工具                      ║
║                                                      ║
║  浏览器将打开 4 个页面，你只需依次登录                ║
║  脚本会自动提取 GA4 / Clarity / Bing / CF ID         ║
║  支持断点续跑 - 已提取的 ID 会自动恢复               ║
╚══════════════════════════════════════════════════════╝
""")
    
    print(f"📋 已保存的结果: {json.dumps(results, indent=2)}")
    
    # 配置 Chrome
    options = Options()
    options.add_argument(f'--user-data-dir={CHROME_PROFILE}')
    options.add_argument('--no-first-run')
    options.add_argument('--no-default-browser-check')
    options.add_argument('--disable-popup-blocking')
    
    print("\n🚀 启动浏览器...")
    driver = webdriver.Chrome(options=options)
    
    try:
        steps = [
            ('ga4_measurement_id', step_ga4),
            ('clarity_project_id', step_clarity),
            ('bing_api_key', step_bing),
            ('cloudflare_token', step_cloudflare),
        ]
        
        all_done = True
        for key, step_func in steps:
            if results.get(key):
                print(f"\n  ⏭️  跳过 {key}（已获取: {results[key]})")
                continue
            
            success = step_func(driver, results)
            save_results(results)
            
            if not success:
                all_done = False
                print(f"\n  ⚠️ {key} 未能自动获取，将继续下一步")
        
        # 最终配置报告
        config = load_config()
        print("\n" + "="*60)
        print("📊 最终配置报告")
        print("="*60)
        print(f"  GA4 Measurement ID:  {config['ga4']['measurement_id']}")
        print(f"  GA4 Property ID:     {config['ga4']['property_id']}")
        print(f"  Clarity Project ID:  {config['clarity']['project_id']}")
        print(f"  Bing API Key:        {config['bing']['api_key'][:10] if config['bing']['api_key'] != 'YOUR_BING_API_KEY' else '待获取'}...")
        print(f"  Cloudflare Token:    {config['cloudflare']['api_token'][:20]}...")
        print(f"\n  ✅ 配置文件: {CONFIG_PATH}")
        
        missing = [k for k in ['ga4_measurement_id', 'clarity_project_id', 'bing_api_key', 'cloudflare_token'] 
                   if not results.get(k)]
        
        if missing:
            print(f"\n  ⚠️ 以下 ID 未能自动获取: {missing}")
            print(f"  💡 你可以重新运行本脚本，已获取的 ID 会自动恢复")
            print(f"     运行: python3 auto_extract_ids.py")
        else:
            print(f"\n  🎉 所有 ID 已获取！")
            print(f"  🚀 运行监控: python3 mintshovels_monitor.py")
        
        print("\n浏览器保持打开，按 Enter 键关闭...")
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            pass
        
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断")
    finally:
        save_results(results)
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == '__main__':
    main()
