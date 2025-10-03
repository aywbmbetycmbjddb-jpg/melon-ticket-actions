from playwright.sync_api import sync_playwright
import requests
import os
import time
from datetime import datetime

SLACK_WEBHOOK = os.environ.get('SLACK_WEBHOOK')
URL = 'https://tkglobal.melon.com/performance/index.htm?langCd=EN&prodId=211992'

# 優先檢查的區域（根據你的偏好排序）
PRIORITY_ZONES = ['F1', 'F2', 'E', 'D', 'C', 'A', 'B']

def send_slack(message):
    """發送 Slack 通知"""
    if SLACK_WEBHOOK:
        try:
            response = requests.post(
                SLACK_WEBHOOK, 
                json={
                    'text': message,
                    'username': 'TWICE Ticket Bot',
                    'icon_emoji': ':ticket:'
                },
                timeout=10
            )
            print(f"✅ Slack 通知已發送")
            return True
        except Exception as e:
            print(f"❌ Slack 失敗: {e}")
            return False
    return False

def check_tickets():
    """檢查票務 - 點擊每個區域檢查座位狀態"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"\n{'='*70}")
            print(f"🎫 TWICE Ticket Monitor - {timestamp}")
            print(f"{'='*70}\n")
            
            # 1. 訪問主頁面
            print("📍 Loading main page...")
            page.goto(URL, wait_until='networkidle', timeout=30000)
            time.sleep(2)
            
            # 2. 點擊 Get Tickets
            print("🖱️  Clicking 'Get Tickets'...")
            button = page.locator('.reservationBtn[data-prodid="211992"]')
            
            if button.count() == 0 or not button.is_enabled():
                print("❌ Button not available")
                return False
            
            button.click()
            
            # 3. 等待 popup
            print("⏳ Waiting for seat selection popup...")
            time.sleep(4)
            
            # 如果開新視窗，切換過去
            if len(context.pages) > 1:
                page = context.pages[-1]
                print("✅ Switched to popup window")
            
            page.wait_for_load_state('networkidle', timeout=15000)
            print(f"📍 Popup URL: {page.url}")
            
            # 4. 獲取所有可用的區域列表
            print("\n🔍 Finding all zone entries...")
            time.sleep(2)
            
            # 尋找座位區域項目的多種可能選擇器
            zone_selectors = [
                'text=/Floor.*Sec [A-Z0-9]+/i',  # 匹配 "Floor X, Sec Y"
                '.seat-list li',
                '.available-seats li',
                '[class*="seat-grade"]',
                '[class*="zone"]'
            ]
            
            zone_elements = None
            for selector in zone_selectors:
                elements = page.locator(selector)
                if elements.count() > 0:
                    zone_elements = elements
                    print(f"✅ Found {elements.count()} zones using: {selector}")
                    break
            
            if not zone_elements or zone_elements.count() == 0:
                print("❌ No zone entries found")
                page.screenshot(path='no_zones.png', full_page=True)
                return False
            
            # 5. 提取所有區域名稱和元素
            zones_to_check = []
            zone_count = zone_elements.count()
            
            print(f"\n📋 Extracting zone names from {zone_count} elements...")
            
            for i in range(zone_count):
                try:
                    element = zone_elements.nth(i)
                    text = element.text_content().strip()
                    
                    # 只保留包含 "Sec" 的項目
                    if 'Sec' in text:
                        # 提取區域代碼（如 F1, F2, A, B 等）
                        import re
                        match = re.search(r'Sec ([A-Z0-9]+)', text, re.IGNORECASE)
                        if match:
                            zone_code = match.group(1)
                            zones_to_check.append({
                                'name': text,
                                'code': zone_code,
                                'element': element,
                                'index': i
                            })
                            print(f"  • {text} (Code: {zone_code})")
                except:
                    continue
            
            if not zones_to_check:
                print("❌ No valid zones extracted")
                return False
            
            print(f"\n✅ Total zones to check: {len(zones_to_check)}")
            
            # 6. 按優先順序排序
            def zone_priority(zone):
                code = zone['code'].upper()
                if code in PRIORITY_ZONES:
                    return PRIORITY_ZONES.index(code)
                return 999
            
            zones_to_check.sort(key=zone_priority)
            
            # 7. 逐個點擊區域檢查座位
            print(f"\n{'='*70}")
            print("🔍 Checking each zone for available seats...")
            print(f"{'='*70}\n")
            
            available_zones = []
            
            for idx, zone in enumerate(zones_to_check, 1):
                zone_name = zone['name']
                zone_code = zone['code']
                
                print(f"[{idx}/{len(zones_to_check)}] Checking: {zone_name}")
                
                try:
                    # 重新定位元素（避免 stale element）
                    zone_element = page.locator(f'text="{zone_name}"').first
                    
                    if not zone_element.is_visible():
                        print(f"  ⚠️  Element not visible, skipping")
                        continue
                    
                    # 點擊區域
                    zone_element.click()
                    time.sleep(1.5)  # 等待座位圖載入
                    
                    # 檢查是否有可點擊的座位
                    # 座位通常是可點擊的元素，灰色座位會有 disabled 或特定 class
                    
                    # 方法 A: 檢查是否有可點擊的座位元素
                    clickable_seats = page.locator(
                        'svg rect:not([class*="disabled"]):not([class*="sold"]):not([fill="gray"]):not([fill="grey"])'
                    )
                    
                    # 方法 B: 或者檢查特定的座位選擇器
                    if clickable_seats.count() == 0:
                        clickable_seats = page.locator(
                            '.seat:not(.disabled):not(.sold), '
                            '[class*="seat"]:not([class*="disabled"]):not([class*="sold"]), '
                            'rect[class*="available"], '
                            'path[class*="available"]'
                        )
                    
                    seat_count = clickable_seats.count()
                    
                    # 方法 C: 檢查是否有 "soldout" 或類似的文字/標記
                    has_soldout_text = (
                        page.locator('text=/sold out/i').count() > 0 or
                        page.locator('text=/no seats/i').count() > 0 or
                        page.locator('.soldout').count() > 0
                    )
                    
                    # 判斷是否有票
                    has_tickets = seat_count > 0 and not has_soldout_text
                    
                    if has_tickets:
                        print(f"  ✅ AVAILABLE! (Found ~{seat_count} clickable seats)")
                        available_zones.append({
                            'name': zone_name,
                            'code': zone_code,
                            'seats': seat_count
                        })
                    else:
                        print(f"  ❌ Sold out")
                    
                    # 返回區域列表（點擊其他地方或按返回）
                    # 嘗試點擊返回按鈕或關閉座位圖
                    back_selectors = [
                        'text=Back',
                        'text=Close', 
                        '.btn-close',
                        '.back-button',
                        '[class*="back"]'
                    ]
                    
                    for back_sel in back_selectors:
                        back_btn = page.locator(back_sel).first
                        if back_btn.count() > 0 and back_btn.is_visible():
                            back_btn.click()
                            time.sleep(0.5)
                            break
                    
                except Exception as e:
                    print(f"  ⚠️  Error checking this zone: {e}")
                    continue
                
                # 每檢查幾個區域就稍微休息，避免太快
                if idx % 3 == 0:
                    time.sleep(1)
            
            # 8. 分析結果
            print(f"\n{'='*70}")
            
            if not available_zones:
                print("❌ No available seats in any zone")
                print(f"{'='*70}\n")
                
                page.screenshot(path='all_sold_out.png', full_page=True)
                print("📸 Screenshot saved: all_sold_out.png")
                
                return False
            
            # 🎉 找到有票的區域！
            print(f"🎉 FOUND TICKETS IN {len(available_zones)} ZONE(S)!")
            
            # 區分優先和其他區域
            priority_zones = [z for z in available_zones if z['code'] in PRIORITY_ZONES]
            other_zones = [z for z in available_zones if z['code'] not in PRIORITY_ZONES]
            
            # 構建通知訊息
            message = f"""
🎉🎉🎉 TWICE FANMEETING TICKETS AVAILABLE! 🎉🎉🎉

📅 2025.10.18 17:00
🎪 2025 TWICE FANMEETING [10VE UNIVERSE]

"""
            
            if priority_zones:
                message += f"⭐⭐⭐ PRIORITY ZONES AVAILABLE ({len(priority_zones)}) ⭐⭐⭐\n"
                for z in priority_zones:
                    message += f"  🎯 {z['name']} (~{z['seats']} seats)\n"
                message += "\n"
            
            if other_zones:
                message += f"🪑 Other Available Zones ({len(other_zones)}):\n"
                for z in other_zones[:10]:
                    message += f"  • {z['name']} (~{z['seats']} seats)\n"
                if len(other_zones) > 10:
                    message += f"  ... and {len(other_zones)-10} more\n"
                message += "\n"
            
            message += f"""🔗 BOOK NOW: {URL}

⏰ Detected at: {timestamp}

💜 快去搶！
"""
            
            print(message)
            print(f"{'='*70}\n")
            
            # 發送通知
            send_slack(message)
            
            # 保存成功截圖
            page.screenshot(path='tickets_available.png', full_page=True)
            print("📸 Success screenshot saved")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            
            try:
                page.screenshot(path='error.png', full_page=True)
                print("📸 Error screenshot saved")
            except:
                pass
            
            return False
            
        finally:
            browser.close()

if __name__ == '__main__':
    result = check_tickets()
    exit(0 if result else 1)
