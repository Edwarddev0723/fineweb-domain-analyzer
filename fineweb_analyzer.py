#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FineWeb Domain Analyzer - 完整的網域分析和內容清洗工具

功能:
1. WARC 轉 JSON
2. 域名分析和提取
3. Robots.txt 可爬性檢查
4. 基於 robots.txt 的內容過濾

作者: FineWeb Domain Analyzer Team
版本: 1.0.0
許可: MIT License
"""

import json
import os
import argparse
import sys
from datetime import datetime
from pathlib import Path
import gzip
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict, Counter
from urllib.parse import urlparse
import logging

# 可選依賴項目檢查
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    print("警告: requests 未安裝，robots.txt檢查功能將不可用")

try:
    import warcio
    from warcio.archiveiterator import ArchiveIterator
    HAS_WARCIO = True
except ImportError:
    HAS_WARCIO = False
    print("警告: warcio 未安裝，WARC轉換功能將不可用")

# 設置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WARCToJSONConverter:
    """WARC 到 JSON 轉換器"""
    
    def __init__(self, output_dir="output", verbose=False):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.verbose = verbose
        
        if not HAS_WARCIO:
            raise ImportError("需要安裝 warcio: pip install warcio")
    
    def convert_warc_to_json(self, warc_path, max_records=None):
        """將 WARC 文件轉換為 JSON"""
        warc_path = Path(warc_path)
        if not warc_path.exists():
            raise FileNotFoundError(f"WARC 文件不存在: {warc_path}")
        
        output_file = self.output_dir / f"{warc_path.stem}.jsonl"
        
        if self.verbose:
            print(f"🔄 開始轉換: {warc_path}")
            print(f"📁 輸出文件: {output_file}")
        
        records_processed = 0
        
        # 處理壓縮和非壓縮文件
        if warc_path.suffix == '.gz':
            file_obj = gzip.open(warc_path, 'rb')
        else:
            file_obj = open(warc_path, 'rb')
        
        try:
            with open(output_file, 'w', encoding='utf-8') as out_f:
                for record in ArchiveIterator(file_obj):
                    if record.rec_type == 'response':
                        # 提取記錄信息
                        json_record = {
                            'url': record.rec_headers.get_header('WARC-Target-URI'),
                            'timestamp': record.rec_headers.get_header('WARC-Date'),
                            'content_type': record.http_headers.get_header('Content-Type') if record.http_headers else None,
                            'content_length': record.rec_headers.get_header('Content-Length'),
                            'status_code': record.http_headers.get_statuscode() if record.http_headers else None,
                            'content': record.content_stream().read().decode('utf-8', errors='ignore')
                        }
                        
                        out_f.write(json.dumps(json_record, ensure_ascii=False) + '\n')
                        records_processed += 1
                        
                        if max_records and records_processed >= max_records:
                            break
                        
                        if self.verbose and records_processed % 1000 == 0:
                            print(f"  已處理 {records_processed} 條記錄")
        
        finally:
            file_obj.close()
        
        if self.verbose:
            print(f"✅ 轉換完成！共處理 {records_processed} 條記錄")
        
        return output_file, records_processed

class DomainExtractor:
    """域名提取和分析器"""
    
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.domain_stats = defaultdict(lambda: {
            'count': 0,
            'urls': [],
            'tld': '',
            'first_seen': None,
            'last_seen': None
        })
    
    def extract_domain(self, url):
        """從URL提取域名"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # 移除端口號
            if ':' in domain and not domain.endswith(':8080'):
                domain = domain.split(':')[0]
            
            # 可選: 移除www前綴
            if domain.startswith('www.'):
                domain = domain[4:]
            
            return domain
        except Exception as e:
            if self.verbose:
                logger.warning(f"URL解析錯誤 {url}: {e}")
            return None
    
    def extract_tld(self, domain):
        """提取頂級域名"""
        if not domain or '.' not in domain:
            return ''
        return domain.split('.')[-1]
    
    def analyze_jsonl_file(self, jsonl_path):
        """分析JSONL文件中的域名"""
        jsonl_path = Path(jsonl_path)
        if not jsonl_path.exists():
            raise FileNotFoundError(f"JSONL 文件不存在: {jsonl_path}")
        
        if self.verbose:
            print(f"🔍 分析文件: {jsonl_path}")
        
        processed_count = 0
        
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                if line.strip():
                    try:
                        record = json.loads(line)
                        url = record.get('url', '')
                        
                        if url:
                            domain = self.extract_domain(url)
                            if domain:
                                stats = self.domain_stats[domain]
                                stats['count'] += 1
                                stats['tld'] = self.extract_tld(domain)
                                
                                # 記錄URL示例（最多5個）
                                if len(stats['urls']) < 5:
                                    stats['urls'].append(url)
                                
                                # 記錄時間戳
                                timestamp = record.get('timestamp') or datetime.now().isoformat()
                                if stats['first_seen'] is None:
                                    stats['first_seen'] = timestamp
                                stats['last_seen'] = timestamp
                                
                                processed_count += 1
                                
                                if self.verbose and processed_count % 1000 == 0:
                                    print(f"  已處理 {processed_count} 個URL")
                    
                    except json.JSONDecodeError as e:
                        if self.verbose:
                            logger.warning(f"第{line_num}行JSON解析錯誤: {e}")
        
        if self.verbose:
            print(f"✅ 分析完成！發現 {len(self.domain_stats)} 個唯一域名")
        
        return dict(self.domain_stats)
    
    def save_domain_analysis(self, output_dir="output"):
        """保存域名分析結果"""
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 簡單域名列表
        domains_list = sorted(self.domain_stats.keys())
        simple_output = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_domains": len(domains_list),
                "format": "simple_list"
            },
            "domains": domains_list
        }
        
        simple_file = output_dir / f"domains_simple_{timestamp}.json"
        with open(simple_file, 'w', encoding='utf-8') as f:
            json.dump(simple_output, f, ensure_ascii=False, indent=2)
        
        # 詳細統計
        detailed_output = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_domains": len(self.domain_stats),
                "format": "detailed_stats"
            },
            "domains": dict(self.domain_stats)
        }
        
        detailed_file = output_dir / f"domains_detailed_{timestamp}.json"
        with open(detailed_file, 'w', encoding='utf-8') as f:
            json.dump(detailed_output, f, ensure_ascii=False, indent=2)
        
        if self.verbose:
            print(f"💾 域名分析已保存:")
            print(f"  簡單列表: {simple_file}")
            print(f"  詳細統計: {detailed_file}")
        
        return simple_file, detailed_file

class RobotsChecker:
    """Robots.txt 檢查器"""
    
    def __init__(self, user_agent="*", timeout=10, max_workers=10, verbose=False):
        if not HAS_REQUESTS:
            raise ImportError("需要安裝 requests: pip install requests")
        
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_workers = max_workers
        self.verbose = verbose
        self.results = {}
        
        # 設置會話
        self.session = requests.Session()
        
        # 設置重試策略
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # 設置請求頭
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; FineWebAnalyzer/1.0)',
            'Accept': 'text/plain,text/html,*/*',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
    
    def check_robots_txt(self, domain):
        """檢查單個域名的robots.txt"""
        result = {
            'domain': domain,
            'robots_exists': False,
            'crawl_allowed': True,
            'crawl_delay': None,
            'disallowed_paths': [],
            'error': None,
            'last_checked': datetime.now().isoformat()
        }
        
        try:
            for protocol in ['https', 'http']:
                robots_url = f"{protocol}://{domain}/robots.txt"
                
                try:
                    response = self.session.get(robots_url, timeout=self.timeout)
                    
                    if response.status_code == 200:
                        result['robots_exists'] = True
                        result['robots_content'] = response.text
                        self._parse_robots_content(result, response.text)
                        break
                    elif response.status_code == 404:
                        result['crawl_allowed'] = True
                        break
                
                except requests.exceptions.RequestException as e:
                    if protocol == 'http':  # 最後一次嘗試失敗
                        result['error'] = f"連接失敗: {str(e)[:100]}"
                        result['crawl_allowed'] = False
                    continue
        
        except Exception as e:
            result['error'] = f"檢查錯誤: {str(e)}"
            result['crawl_allowed'] = False
        
        return result
    
    def _parse_robots_content(self, result, robots_content):
        """解析robots.txt內容"""
        lines = robots_content.strip().split('\n')
        current_user_agent = None
        applies_to_us = False
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if line.lower().startswith('user-agent:'):
                current_user_agent = line.split(':', 1)[1].strip()
                applies_to_us = (current_user_agent == '*' or 
                               current_user_agent.lower() == self.user_agent.lower())
            
            elif applies_to_us:
                if line.lower().startswith('disallow:'):
                    path = line.split(':', 1)[1].strip()
                    if path == '/':
                        result['crawl_allowed'] = False
                    elif path:
                        result['disallowed_paths'].append(path)
                
                elif line.lower().startswith('crawl-delay:'):
                    try:
                        delay = float(line.split(':', 1)[1].strip())
                        result['crawl_delay'] = delay
                    except ValueError:
                        pass
    
    def check_domains_batch(self, domains, output_dir="output"):
        """批量檢查域名"""
        if not domains:
            return {}
        
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        
        if self.verbose:
            print(f"🤖 開始檢查 {len(domains)} 個域名的robots.txt...")
        
        # 並發檢查
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_domain = {
                executor.submit(self.check_robots_txt, domain): domain 
                for domain in domains
            }
            
            for future in as_completed(future_to_domain):
                domain = future_to_domain[future]
                try:
                    result = future.result(timeout=self.timeout + 5)
                    self.results[domain] = result
                    
                    if self.verbose:
                        status = "✅" if result['crawl_allowed'] else "❌"
                        print(f"  {status} {domain}: {'可爬' if result['crawl_allowed'] else '禁止'}")
                
                except Exception as e:
                    self.results[domain] = {
                        'domain': domain,
                        'error': str(e),
                        'crawl_allowed': False,
                        'last_checked': datetime.now().isoformat()
                    }
                    if self.verbose:
                        print(f"  ❌ {domain}: {str(e)[:50]}")
        
        # 保存結果
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = output_dir / f"robots_check_{timestamp}.json"
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump({
                'metadata': {
                    'generated_at': datetime.now().isoformat(),
                    'total_domains': len(domains),
                    'user_agent': self.user_agent,
                    'timeout': self.timeout
                },
                'results': self.results
            }, f, ensure_ascii=False, indent=2)
        
        if self.verbose:
            crawlable_count = sum(1 for r in self.results.values() if r.get('crawl_allowed', False))
            print(f"✅ 檢查完成！{crawlable_count}/{len(domains)} 個域名可爬取")
            print(f"💾 結果已保存: {results_file}")
        
        return self.results, results_file

class ContentFilter:
    """基於robots.txt的內容過濾器"""
    
    def __init__(self, verbose=False):
        self.verbose = verbose
    
    def filter_jsonl_by_robots(self, jsonl_path, robots_results, output_dir="output"):
        """根據robots.txt結果過濾JSONL內容"""
        jsonl_path = Path(jsonl_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        
        if not jsonl_path.exists():
            raise FileNotFoundError(f"JSONL 文件不存在: {jsonl_path}")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filtered_file = output_dir / f"filtered_{jsonl_path.stem}_{timestamp}.jsonl"
        excluded_file = output_dir / f"excluded_{jsonl_path.stem}_{timestamp}.jsonl"
        
        if self.verbose:
            print(f"🔄 開始過濾: {jsonl_path}")
            print(f"📁 過濾後文件: {filtered_file}")
            print(f"📁 排除內容文件: {excluded_file}")
        
        # 建立域名到可爬性的映射
        domain_crawlable = {}
        for domain, result in robots_results.items():
            domain_crawlable[domain] = result.get('crawl_allowed', False)
        
        processed_count = 0
        filtered_count = 0
        excluded_count = 0
        
        with open(jsonl_path, 'r', encoding='utf-8') as input_f, \
             open(filtered_file, 'w', encoding='utf-8') as filtered_f, \
             open(excluded_file, 'w', encoding='utf-8') as excluded_f:
            
            for line_num, line in enumerate(input_f, 1):
                if line.strip():
                    try:
                        record = json.loads(line)
                        url = record.get('url', '')
                        
                        if url:
                            # 提取域名
                            domain = self._extract_domain(url)
                            
                            # 檢查是否可爬
                            if domain and domain_crawlable.get(domain, True):  # 默認允許
                                filtered_f.write(line)
                                filtered_count += 1
                            else:
                                excluded_f.write(line)
                                excluded_count += 1
                        else:
                            # 沒有URL的記錄保留
                            filtered_f.write(line)
                            filtered_count += 1
                        
                        processed_count += 1
                        
                        if self.verbose and processed_count % 1000 == 0:
                            print(f"  已處理 {processed_count} 條記錄")
                    
                    except json.JSONDecodeError as e:
                        if self.verbose:
                            logger.warning(f"第{line_num}行JSON解析錯誤: {e}")
        
        # 生成統計報告
        stats = {
            'total_processed': processed_count,
            'filtered_kept': filtered_count,
            'excluded_count': excluded_count,
            'keep_ratio': round(filtered_count / processed_count * 100, 2) if processed_count > 0 else 0
        }
        
        stats_file = output_dir / f"filter_stats_{timestamp}.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump({
                'metadata': {
                    'generated_at': datetime.now().isoformat(),
                    'source_file': str(jsonl_path),
                    'filtered_file': str(filtered_file),
                    'excluded_file': str(excluded_file)
                },
                'statistics': stats
            }, f, ensure_ascii=False, indent=2)
        
        if self.verbose:
            print(f"✅ 過濾完成！")
            print(f"  📊 保留: {filtered_count} 條 ({stats['keep_ratio']}%)")
            print(f"  🗑️ 排除: {excluded_count} 條")
            print(f"  📈 統計: {stats_file}")
        
        return filtered_file, excluded_file, stats
    
    def _extract_domain(self, url):
        """從URL提取域名"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if ':' in domain and not domain.endswith(':8080'):
                domain = domain.split(':')[0]
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            return None

def main():
    parser = argparse.ArgumentParser(
        description="FineWeb Domain Analyzer - 完整的網域分析和內容清洗工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 完整流程
  python fineweb_analyzer.py --input data.warc.gz --all-steps

  # 單步操作
  python fineweb_analyzer.py --input data.warc.gz --warc-to-json
  python fineweb_analyzer.py --input data.jsonl --extract-domains
  python fineweb_analyzer.py --domains domains.json --check-robots
  python fineweb_analyzer.py --input data.jsonl --robots robots_check.json --filter-content
        """
    )
    
    # 基本參數
    parser.add_argument('--input', '-i', help='輸入文件路径')
    parser.add_argument('--output', '-o', default='output', help='輸出目錄 (默認: output)')
    parser.add_argument('--verbose', '-v', action='store_true', help='詳細輸出')
    
    # 功能選擇
    parser.add_argument('--all-steps', action='store_true', help='執行完整流程 (1-4步)')
    parser.add_argument('--warc-to-json', action='store_true', help='步驟1: WARC轉JSON')
    parser.add_argument('--extract-domains', action='store_true', help='步驟2: 提取域名')
    parser.add_argument('--check-robots', action='store_true', help='步驟3: 檢查robots.txt')
    parser.add_argument('--filter-content', action='store_true', help='步驟4: 過濾內容')
    
    # 額外參數
    parser.add_argument('--domains', help='域名文件路径 (用於步驟3)')
    parser.add_argument('--robots', help='robots檢查結果文件 (用於步驟4)')
    parser.add_argument('--max-records', type=int, help='最大處理記錄數')
    parser.add_argument('--timeout', type=int, default=10, help='請求超時時間 (默認: 10秒)')
    parser.add_argument('--max-workers', type=int, default=10, help='最大併發數 (默認: 10)')
    
    args = parser.parse_args()
    
    # 參數驗證
    if args.all_steps or args.warc_to_json or args.extract_domains or args.filter_content:
        if not args.input:
            parser.error("這些操作需要 --input 參數")
    
    if args.check_robots and not args.domains:
        parser.error("--check-robots 需要 --domains 參數")
    
    if args.filter_content and not args.robots:
        parser.error("--filter-content 需要 --robots 參數")
    
    # 創建輸出目錄
    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True)
    
    try:
        if args.all_steps:
            print("🚀 開始執行完整流程...")
            
            # 步驟1: WARC轉JSON
            if Path(args.input).suffix in ['.warc', '.gz']:
                print("\n📋 步驟1: WARC轉JSON")
                converter = WARCToJSONConverter(args.output, args.verbose)
                jsonl_file, _ = converter.convert_warc_to_json(args.input, args.max_records)
            else:
                jsonl_file = Path(args.input)
            
            # 步驟2: 提取域名
            print("\n📋 步驟2: 域名分析")
            extractor = DomainExtractor(args.verbose)
            domain_stats = extractor.analyze_jsonl_file(jsonl_file)
            simple_file, _ = extractor.save_domain_analysis(args.output)
            
            # 步驟3: 檢查robots.txt
            print("\n📋 步驟3: Robots.txt檢查")
            checker = RobotsChecker(timeout=args.timeout, max_workers=args.max_workers, verbose=args.verbose)
            domains = list(domain_stats.keys())
            robots_results, robots_file = checker.check_domains_batch(domains, args.output)
            
            # 步驟4: 過濾內容
            print("\n📋 步驟4: 內容過濾")
            filter_tool = ContentFilter(args.verbose)
            filtered_file, excluded_file, stats = filter_tool.filter_jsonl_by_robots(
                jsonl_file, robots_results, args.output
            )
            
            print(f"\n🎉 完整流程執行完成！")
            print(f"📁 輸出目錄: {args.output}")
            
        else:
            # 單步執行
            if args.warc_to_json:
                converter = WARCToJSONConverter(args.output, args.verbose)
                converter.convert_warc_to_json(args.input, args.max_records)
            
            elif args.extract_domains:
                extractor = DomainExtractor(args.verbose)
                extractor.analyze_jsonl_file(args.input)
                extractor.save_domain_analysis(args.output)
            
            elif args.check_robots:
                with open(args.domains, 'r', encoding='utf-8') as f:
                    domain_data = json.load(f)
                    domains = domain_data.get('domains', [])
                
                checker = RobotsChecker(timeout=args.timeout, max_workers=args.max_workers, verbose=args.verbose)
                checker.check_domains_batch(domains, args.output)
            
            elif args.filter_content:
                with open(args.robots, 'r', encoding='utf-8') as f:
                    robots_data = json.load(f)
                    robots_results = robots_data.get('results', {})
                
                filter_tool = ContentFilter(args.verbose)
                filter_tool.filter_jsonl_by_robots(args.input, robots_results, args.output)
            
            else:
                parser.print_help()
                sys.exit(1)
    
    except Exception as e:
        logger.error(f"執行錯誤: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
