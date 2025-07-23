#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速測試腳本 - 測試改進後的robots檢查功能
"""

import json
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

def test_domain_check(domain, timeout=5):
    """測試單個域名檢查"""
    print(f"🔍 檢查: {domain}")
    
    result = {
        'domain': domain,
        'crawl_allowed': True,
        'error': None,
        'status_code': None,
        'response_time': None
    }
    
    start_time = time.time()
    
    try:
        for protocol in ['https', 'http']:
            robots_url = f"{protocol}://{domain}/robots.txt"
            
            try:
                response = requests.get(
                    robots_url, 
                    timeout=(3, timeout),  # 連接和讀取超時
                    headers={'User-Agent': 'TestBot/1.0'}
                )
                
                result['status_code'] = response.status_code
                result['response_time'] = round(time.time() - start_time, 2)
                
                if response.status_code in [200, 404]:
                    result['crawl_allowed'] = True
                    print(f"  ✅ {domain} - {response.status_code} - {result['response_time']}秒")
                    break
                    
            except requests.exceptions.Timeout:
                print(f"  ⏰ {domain} - 超時 ({protocol})")
                continue
            except requests.exceptions.RequestException as e:
                print(f"  ❌ {domain} - 錯誤: {str(e)[:50]}")
                if protocol == 'http':
                    result['error'] = str(e)[:100]
                continue
    
    except Exception as e:
        result['error'] = str(e)[:100]
        print(f"  💥 {domain} - 未知錯誤: {str(e)[:50]}")
    
    return result

def test_batch_check():
    """測試批量檢查"""
    test_domains = [
        "google.com",
        "github.com", 
        "stackoverflow.com",
        "wikipedia.org",
        "example.com"
    ]
    
    print(f"🧪 開始測試 {len(test_domains)} 個域名...")
    start_time = time.time()
    
    results = {}
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_domain = {
            executor.submit(test_domain_check, domain): domain 
            for domain in test_domains
        }
        
        try:
            for future in as_completed(future_to_domain, timeout=30):
                domain = future_to_domain[future]
                
                try:
                    result = future.result(timeout=10)
                    results[domain] = result
                    
                except Exception as e:
                    print(f"  ❌ {domain} - Future錯誤: {e}")
                    results[domain] = {
                        'domain': domain,
                        'error': str(e),
                        'crawl_allowed': False
                    }
        
        except Exception as e:
            print(f"⚠️ 批量檢查錯誤: {e}")
    
    elapsed = time.time() - start_time
    print(f"\n📊 測試完成 - 耗時: {elapsed:.1f}秒")
    print(f"成功: {len([r for r in results.values() if not r.get('error')])}/{len(test_domains)}")
    
    return results

if __name__ == "__main__":
    results = test_batch_check()
    
    # 保存結果
    with open('test_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print("✅ 測試結果已保存到 test_results.json")
