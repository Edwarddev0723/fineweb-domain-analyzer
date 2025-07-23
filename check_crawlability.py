#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
網站爬取權限檢查腳本 - 檢查domains JSON中的網站robots.txt和爬取權限
作者: AI助手
日期: 2025-07-17
"""

import json
import requests
import argparse
import os
import time
import sys
import signal
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import threading

class RobotsChecker:
    """robots.txt檢查器"""
    
    def __init__(self, user_agent="*", timeout=10, max_workers=10):
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_workers = max_workers
        
        # 配置session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; WebCrawler/1.0; +https://example.com/bot)',
            'Accept': 'text/plain,text/html,*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache'
        })
        
        # 嘗試設置重試策略（可選）
        try:
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            retry_strategy = Retry(
                total=2,  # 總重試次數
                backoff_factor=0.5,  # 重試間隔
                status_forcelist=[429, 500, 502, 503, 504],  # 需要重試的狀態碼
                allowed_methods=["GET"]  # 只對GET請求重試
            )
            
            adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=20, pool_maxsize=20)
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)
        except ImportError:
            # 如果導入失敗，使用基本配置
            pass
        
        self.results = {}
        self.lock = threading.Lock()
        self.processed_count = 0
        self.total_count = 0
    
    def check_robots_txt(self, domain):
        """檢查單個域名的robots.txt"""
        result = {
            'domain': domain,
            'robots_url': f"https://{domain}/robots.txt",
            'robots_exists': False,
            'robots_content': None,
            'crawl_allowed': True,
            'crawl_delay': None,
            'disallowed_paths': [],
            'allowed_paths': [],
            'sitemap_urls': [],
            'status_code': None,
            'error': None,
            'response_time': None,
            'last_checked': datetime.now().isoformat()
        }
        
        try:
            # 首先嘗試HTTPS，然後HTTP
            start_time = time.time()
            
            for protocol in ['https', 'http']:
                robots_url = f"{protocol}://{domain}/robots.txt"
                result['robots_url'] = robots_url
                
                try:
                    # 使用更短的連接超時和讀取超時
                    response = self.session.get(
                        robots_url, 
                        timeout=(5, self.timeout),  # (連接超時, 讀取超時)
                        allow_redirects=True,
                        stream=False
                    )
                    
                    result['status_code'] = response.status_code
                    result['response_time'] = round(time.time() - start_time, 2)
                    
                    if response.status_code == 200:
                        result['robots_exists'] = True
                        # 限制內容大小，避免處理過大的robots.txt
                        content = response.text[:50000]  # 最多50KB
                        result['robots_content'] = content
                        
                        # 解析robots.txt
                        self._parse_robots_content(result, robots_url, content)
                        break
                        
                    elif response.status_code == 404:
                        # 404表示沒有robots.txt，默認允許爬取
                        result['crawl_allowed'] = True
                        break
                    elif response.status_code in [403, 401]:
                        # 權限問題，保守處理
                        result['error'] = f"權限被拒: {response.status_code}"
                        result['crawl_allowed'] = False
                        break
                    
                except requests.exceptions.Timeout:
                    if protocol == 'http':  # 如果HTTP也超時
                        result['error'] = f"連接超時 (>{self.timeout}秒)"
                        result['crawl_allowed'] = False
                    continue
                    
                except requests.exceptions.ConnectionError as e:
                    if protocol == 'http':  # 如果HTTP也連接失敗
                        result['error'] = f"連接失敗: {str(e)[:100]}"
                        result['crawl_allowed'] = False
                    continue
                    
                except requests.exceptions.RequestException as e:
                    if protocol == 'http':  # 如果HTTP也失敗
                        result['error'] = f"請求失敗: {str(e)[:100]}"
                        result['crawl_allowed'] = False
                    continue
        
        except Exception as e:
            result['error'] = f"未知錯誤: {str(e)[:100]}"
            result['crawl_allowed'] = False
        
        return result
    
    def _parse_robots_content(self, result, robots_url, content):
        """解析robots.txt內容"""
        try:
            rp = RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            
            # 檢查是否允許爬取根路徑
            result['crawl_allowed'] = rp.can_fetch(self.user_agent, "/")
            
            # 解析內容以獲取更多信息
            lines = content.strip().split('\n')
            current_user_agent = None
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if line.lower().startswith('user-agent:'):
                    current_user_agent = line.split(':', 1)[1].strip()
                
                elif line.lower().startswith('disallow:') and (
                    current_user_agent == '*' or 
                    current_user_agent == self.user_agent
                ):
                    path = line.split(':', 1)[1].strip()
                    if path:
                        result['disallowed_paths'].append(path)
                
                elif line.lower().startswith('allow:') and (
                    current_user_agent == '*' or 
                    current_user_agent == self.user_agent
                ):
                    path = line.split(':', 1)[1].strip()
                    if path:
                        result['allowed_paths'].append(path)
                
                elif line.lower().startswith('crawl-delay:') and (
                    current_user_agent == '*' or 
                    current_user_agent == self.user_agent
                ):
                    try:
                        delay = float(line.split(':', 1)[1].strip())
                        result['crawl_delay'] = delay
                    except ValueError:
                        pass
                
                elif line.lower().startswith('sitemap:'):
                    sitemap_url = line.split(':', 1)[1].strip()
                    if sitemap_url:
                        result['sitemap_urls'].append(sitemap_url)
        
        except Exception as e:
            result['error'] = f"robots.txt解析錯誤: {str(e)}"
    
    def check_domains_batch(self, domains, verbose=True):
        """批量檢查域名列表 - 改進版本，防止卡住"""
        self.total_count = len(domains)
        self.processed_count = 0
        start_time = time.time()
        
        if verbose:
            print(f"🤖 開始檢查 {len(domains)} 個域名的robots.txt...")
        
        # 分批處理，每批最多100個域名
        batch_size = min(100, max(10, len(domains) // 10))
        
        for batch_start in range(0, len(domains), batch_size):
            batch_end = min(batch_start + batch_size, len(domains))
            batch_domains = domains[batch_start:batch_end]
            
            if verbose:
                print(f"📦 處理批次: {batch_start//batch_size + 1}/{(len(domains)-1)//batch_size + 1} "
                      f"({len(batch_domains)} 個域名)")
            
            self._process_batch(batch_domains, verbose, start_time)
        
        elapsed_total = time.time() - start_time
        if verbose:
            print(f"✅ 檢查完成！耗時: {elapsed_total:.1f}秒")
            print(f"📊 成功處理: {len([r for r in self.results.values() if not r.get('error')])}")
            print(f"❌ 處理失敗: {len([r for r in self.results.values() if r.get('error')])}")
        
        return self.results
    
    def _process_batch(self, batch_domains, verbose, start_time):
        """處理單個批次"""
        batch_timeout = len(batch_domains) * (self.timeout + 2)  # 每個域名額外2秒緩衝
        
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(batch_domains))) as executor:
            # 提交批次任務
            future_to_domain = {
                executor.submit(self.check_robots_txt, domain): domain 
                for domain in batch_domains
            }
            
            completed_in_batch = 0
            
            try:
                # 使用as_completed處理結果，添加批次超時
                for future in as_completed(future_to_domain, timeout=batch_timeout):
                    domain = future_to_domain[future]
                    
                    try:
                        # 獲取結果，添加個別超時
                        result = future.result(timeout=2)  # 快速獲取已完成的結果
                        
                        with self.lock:
                            self.results[domain] = result
                            self.processed_count += 1
                            completed_in_batch += 1
                            
                            if verbose:
                                progress = (self.processed_count / self.total_count) * 100
                                elapsed = time.time() - start_time
                                rate = self.processed_count / elapsed if elapsed > 0 else 0
                                eta = (self.total_count - self.processed_count) / rate if rate > 0 else 0
                                
                                # 實時進度顯示
                                if self.processed_count % 5 == 0 or progress >= 98:
                                    print(f"  📊 進度: {self.processed_count}/{self.total_count} "
                                          f"({progress:.1f}%) - 速度: {rate:.1f}/秒 - ETA: {eta:.0f}秒")
                    
                    except Exception as e:
                        with self.lock:
                            self.results[domain] = {
                                'domain': domain,
                                'error': str(e),
                                'crawl_allowed': False,
                                'last_checked': datetime.now().isoformat()
                            }
                            self.processed_count += 1
                            completed_in_batch += 1
                            
                            if verbose:
                                print(f"  ❌ {domain}: {str(e)[:50]}")
            
            except Exception as batch_error:
                if verbose:
                    print(f"⚠️ 批次處理異常: {batch_error}")
                
                # 處理未完成的任務
                for future in future_to_domain:
                    if not future.done():
                        future.cancel()
                        domain = future_to_domain[future]
                        with self.lock:
                            if domain not in self.results:
                                self.results[domain] = {
                                    'domain': domain,
                                    'error': '批次處理超時或被取消',
                                    'crawl_allowed': False,
                                    'last_checked': datetime.now().isoformat()
                                }
                                self.processed_count += 1

class CrawlabilityAnalyzer:
    """爬取能力分析器"""
    
    def __init__(self, robots_results):
        self.robots_results = robots_results
    
    def analyze_crawlability(self):
        """分析爬取能力統計"""
        stats = {
            'total_domains': len(self.robots_results),
            'crawlable_domains': 0,
            'non_crawlable_domains': 0,
            'robots_exists_count': 0,
            'avg_crawl_delay': 0,
            'domains_with_sitemap': 0,
            'error_count': 0,
            'tld_analysis': {},
            'crawl_delay_distribution': {},
            'status_code_distribution': {}
        }
        
        crawl_delays = []
        
        for domain, result in self.robots_results.items():
            # 基本統計
            if result.get('crawl_allowed', False):
                stats['crawlable_domains'] += 1
            else:
                stats['non_crawlable_domains'] += 1
            
            if result.get('robots_exists', False):
                stats['robots_exists_count'] += 1
            
            if result.get('sitemap_urls'):
                stats['domains_with_sitemap'] += 1
            
            if result.get('error'):
                stats['error_count'] += 1
            
            # 爬取延遲分析
            if result.get('crawl_delay'):
                crawl_delays.append(result['crawl_delay'])
                
                delay_range = self._get_delay_range(result['crawl_delay'])
                stats['crawl_delay_distribution'][delay_range] = \
                    stats['crawl_delay_distribution'].get(delay_range, 0) + 1
            
            # TLD分析
            tld = domain.split('.')[-1] if '.' in domain else 'unknown'
            if tld not in stats['tld_analysis']:
                stats['tld_analysis'][tld] = {
                    'total': 0,
                    'crawlable': 0,
                    'robots_exists': 0
                }
            
            stats['tld_analysis'][tld]['total'] += 1
            if result.get('crawl_allowed', False):
                stats['tld_analysis'][tld]['crawlable'] += 1
            if result.get('robots_exists', False):
                stats['tld_analysis'][tld]['robots_exists'] += 1
            
            # 狀態碼分析
            status_code = result.get('status_code', 'unknown')
            stats['status_code_distribution'][str(status_code)] = \
                stats['status_code_distribution'].get(str(status_code), 0) + 1
        
        # 計算平均爬取延遲
        if crawl_delays:
            stats['avg_crawl_delay'] = round(sum(crawl_delays) / len(crawl_delays), 2)
        
        return stats
    
    def _get_delay_range(self, delay):
        """獲取延遲範圍標籤"""
        if delay <= 1:
            return "0-1秒"
        elif delay <= 5:
            return "1-5秒"
        elif delay <= 10:
            return "5-10秒"
        else:
            return "10秒以上"
    
    def generate_recommendations(self, stats):
        """生成爬取建議"""
        recommendations = {
            'safe_to_crawl': [],
            'crawl_with_caution': [],
            'do_not_crawl': [],
            'general_advice': []
        }
        
        for domain, result in self.robots_results.items():
            if result.get('error'):
                recommendations['do_not_crawl'].append({
                    'domain': domain,
                    'reason': f"檢查失敗: {result['error']}"
                })
            elif not result.get('crawl_allowed', True):
                recommendations['do_not_crawl'].append({
                    'domain': domain,
                    'reason': "robots.txt明確禁止爬取"
                })
            elif result.get('crawl_delay', 0) > 10:
                recommendations['crawl_with_caution'].append({
                    'domain': domain,
                    'reason': f"要求延遲 {result['crawl_delay']} 秒"
                })
            else:
                recommendations['safe_to_crawl'].append({
                    'domain': domain,
                    'crawl_delay': result.get('crawl_delay', 0)
                })
        
        # 生成一般建議
        crawlable_rate = (stats['crawlable_domains'] / stats['total_domains']) * 100
        
        if crawlable_rate > 80:
            recommendations['general_advice'].append("大部分網站允許爬取，整體風險較低")
        elif crawlable_rate > 50:
            recommendations['general_advice'].append("約半數網站允許爬取，建議仔細檢查robots.txt")
        else:
            recommendations['general_advice'].append("多數網站限制爬取，建議謹慎處理")
        
        if stats['avg_crawl_delay'] > 5:
            recommendations['general_advice'].append(f"平均爬取延遲 {stats['avg_crawl_delay']} 秒，需要考慮爬取效率")
        
        return recommendations

def load_domain_json(file_path):
    """加載域名JSON文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 根據不同格式提取域名列表
        if 'domains' in data:
            if isinstance(data['domains'], list):
                # simple_list格式
                return data['domains']
            elif isinstance(data['domains'], dict):
                # detailed_stats格式
                return list(data['domains'].keys())
            elif isinstance(data['domains'], list) and data['domains'] and 'domain' in data['domains'][0]:
                # frequency_ranked格式
                return [item['domain'] for item in data['domains']]
        
        return []
    
    except Exception as e:
        print(f"❌ 載入JSON文件失敗: {e}")
        return []

def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='檢查域名的robots.txt和爬取權限')
    parser.add_argument('domain_json', help='包含域名的JSON文件')
    parser.add_argument('-o', '--output', default='crawlability_check', help='輸出目錄 (默認: crawlability_check)')
    parser.add_argument('-u', '--user-agent', default='*', help='User-Agent (默認: *)')
    parser.add_argument('-t', '--timeout', type=int, default=10, help='請求超時時間 (默認: 10秒)')
    parser.add_argument('-w', '--workers', type=int, default=10, help='並發數量 (默認: 10)')
    parser.add_argument('-v', '--verbose', action='store_true', help='顯示詳細輸出')
    parser.add_argument('--limit', type=int, help='限制檢查的域名數量（用於測試）')
    
    args = parser.parse_args()
    
    # 設置信號處理器，允許優雅中斷
    interrupted = threading.Event()
    results = {}
    
    def signal_handler(signum, frame):
        print(f"\n⚠️ 收到中斷信號，正在保存已處理的結果...")
        interrupted.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
    
    # 載入域名列表
    domains = load_domain_json(args.domain_json)
    
    if not domains:
        print("❌ 沒有找到有效的域名列表")
        sys.exit(1)
    
    if args.limit:
        domains = domains[:args.limit]
        print(f"⚠️  限制檢查前 {args.limit} 個域名")
    
    if args.verbose:
        print(f"📂 載入域名文件: {args.domain_json}")
        print(f"🌐 發現 {len(domains)} 個域名")
        print(f"⚙️ 並發數: {args.workers}, 超時: {args.timeout}秒")
        print(f"💡 提示: 按 Ctrl+C 可以隨時中斷並保存已處理的結果")
    
    try:
        # 初始化檢查器
        checker = RobotsChecker(
            user_agent=args.user_agent,
            timeout=args.timeout,
            max_workers=args.workers
        )
        
        # 執行檢查
        results = checker.check_domains_batch(domains, args.verbose)
        
    except KeyboardInterrupt:
        print(f"\n⚠️ 用戶中斷操作")
        results = getattr(checker, 'results', {})
    
    except Exception as e:
        print(f"\n❌ 處理過程中出現錯誤: {e}")
        results = getattr(checker, 'results', {})
    
    # 確保有結果可以分析
    if not results:
        print("❌ 沒有任何處理結果")
        sys.exit(1)
    
    print(f"\n📊 準備分析 {len(results)} 個結果...")
    
    # 分析結果
    analyzer = CrawlabilityAnalyzer(results)
    stats = analyzer.analyze_crawlability()
    recommendations = analyzer.generate_recommendations(stats)
    
    # 輸出結果
    os.makedirs(args.output, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 1. 詳細結果
    results_file = os.path.join(args.output, f"robots_check_results_{timestamp}.json")
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump({
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'total_domains': len(domains),
                'user_agent': args.user_agent,
                'timeout': args.timeout,
                'script_version': '1.0'
            },
            'results': results
        }, f, ensure_ascii=False, indent=2)
    
    # 2. 統計分析
    stats_file = os.path.join(args.output, f"crawlability_stats_{timestamp}.json")
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump({
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'analysis_version': '1.0'
            },
            'statistics': stats,
            'recommendations': recommendations
        }, f, ensure_ascii=False, indent=2)
    
    # 3. 可爬取域名列表
    crawlable_domains = [
        domain for domain, result in results.items() 
        if result.get('crawl_allowed', False) and not result.get('error')
    ]
    
    crawlable_file = os.path.join(args.output, f"crawlable_domains_{timestamp}.json")
    with open(crawlable_file, 'w', encoding='utf-8') as f:
        json.dump({
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'total_crawlable': len(crawlable_domains),
                'source_file': args.domain_json
            },
            'crawlable_domains': crawlable_domains
        }, f, ensure_ascii=False, indent=2)
    
    # 顯示摘要
    print(f"\n📊 檢查結果摘要:")
    print(f"  總域名數: {stats['total_domains']}")
    print(f"  可爬取: {stats['crawlable_domains']} ({stats['crawlable_domains']/stats['total_domains']*100:.1f}%)")
    print(f"  不可爬取: {stats['non_crawlable_domains']} ({stats['non_crawlable_domains']/stats['total_domains']*100:.1f}%)")
    print(f"  有robots.txt: {stats['robots_exists_count']} ({stats['robots_exists_count']/stats['total_domains']*100:.1f}%)")
    print(f"  檢查錯誤: {stats['error_count']}")
    
    if stats['avg_crawl_delay'] > 0:
        print(f"  平均爬取延遲: {stats['avg_crawl_delay']} 秒")
    
    print(f"\n📁 輸出文件:")
    print(f"  📋 詳細結果: {results_file}")
    print(f"  📊 統計分析: {stats_file}")
    print(f"  ✅ 可爬取列表: {crawlable_file}")
    
    print(f"\n✅ 檢查完成！")

if __name__ == "__main__":
    main()
