#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
域名提取腳本 - 從JSONL數據集中提取唯一域名並生成JSON
作者: AI助手
日期: 2025-07-17
"""

import json
import argparse
import os
from urllib.parse import urlparse
from collections import defaultdict, Counter
from datetime import datetime
import sys

class DomainExtractor:
    """智能域名提取器"""
    
    def __init__(self):
        self.domain_stats = defaultdict(lambda: {
            'count': 0,
            'urls': [],
            'tld': '',
            'subdomain_count': 0,
            'first_seen': None,
            'last_seen': None
        })
        self.processed_count = 0
        self.total_count = 0
    
    def extract_domain(self, url):
        """從URL提取域名"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # 移除端口號
            if ':' in domain:
                domain = domain.split(':')[0]
            
            # 移除www前綴（可選）
            if domain.startswith('www.'):
                domain = domain[4:]
            
            return domain if domain else None
        except Exception as e:
            print(f"URL解析錯誤 {url}: {e}")
            return None
    
    def extract_tld(self, domain):
        """提取頂級域名"""
        if not domain or '.' not in domain:
            return ''
        return domain.split('.')[-1]
    
    def count_subdomains(self, domain):
        """計算子域名數量"""
        if not domain:
            return 0
        return domain.count('.')
    
    def load_jsonl_data(self, file_path):
        """從JSONL文件加載數據"""
        data = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    if line.strip():
                        try:
                            data.append(json.loads(line))
                        except json.JSONDecodeError as e:
                            print(f"第{line_num}行JSON解析錯誤: {e}")
            return data
        except FileNotFoundError:
            print(f"❌ 文件未找到: {file_path}")
            return []
        except Exception as e:
            print(f"❌ 讀取文件時出錯: {e}")
            return []
    
    def process_urls(self, data, verbose=True):
        """處理所有URL並提取域名信息"""
        if verbose:
            print(f"🔄 開始處理 {len(data)} 條記錄...")
        
        self.total_count = len(data)
        self.processed_count = 0
        
        for i, record in enumerate(data):
            if verbose and i % 1000 == 0:
                print(f"  處理進度: {i}/{len(data)} ({i/len(data)*100:.1f}%)")
            
            url = record.get('url', '')
            if not url:
                continue
            
            domain = self.extract_domain(url)
            if not domain:
                continue
            
            # 更新域名統計
            stats = self.domain_stats[domain]
            stats['count'] += 1
            stats['tld'] = self.extract_tld(domain)
            stats['subdomain_count'] = self.count_subdomains(domain)
            
            # 記錄URL示例（最多保存5個）
            if len(stats['urls']) < 5:
                stats['urls'].append(url)
            
            # 記錄時間戳
            timestamp = record.get('timestamp') or record.get('date') or datetime.now().isoformat()
            if stats['first_seen'] is None:
                stats['first_seen'] = timestamp
            stats['last_seen'] = timestamp
            
            self.processed_count += 1
        
        if verbose:
            print(f"✅ 處理完成！共處理 {self.processed_count} 個URL")
            print(f"📊 發現 {len(self.domain_stats)} 個唯一域名")
        
        return self.domain_stats

class JSONOutputGenerator:
    """JSON輸出生成器"""
    
    def __init__(self, domain_data):
        self.domain_data = domain_data
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def generate_simple_list(self):
        """生成簡單的域名列表"""
        domains = list(self.domain_data.keys())
        domains.sort()
        return {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_domains": len(domains),
                "format": "simple_list",
                "script_version": "1.0"
            },
            "domains": domains
        }
    
    def generate_detailed_stats(self):
        """生成詳細的域名統計信息"""
        detailed_data = {}
        
        for domain, stats in self.domain_data.items():
            detailed_data[domain] = {
                "count": stats['count'],
                "tld": stats['tld'],
                "subdomain_count": stats['subdomain_count'],
                "sample_urls": stats['urls'],
                "first_seen": stats['first_seen'],
                "last_seen": stats['last_seen']
            }
        
        return {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_domains": len(detailed_data),
                "total_urls_processed": sum(stats['count'] for stats in self.domain_data.values()),
                "format": "detailed_stats",
                "script_version": "1.0"
            },
            "domains": detailed_data
        }
    
    def generate_frequency_ranked(self):
        """生成按頻率排序的域名列表"""
        sorted_domains = sorted(
            self.domain_data.items(), 
            key=lambda x: x[1]['count'], 
            reverse=True
        )
        
        total_urls = sum(s['count'] for s in self.domain_data.values())
        ranked_list = []
        
        for rank, (domain, stats) in enumerate(sorted_domains, 1):
            ranked_list.append({
                "rank": rank,
                "domain": domain,
                "count": stats['count'],
                "percentage": round(stats['count'] / total_urls * 100, 2),
                "tld": stats['tld']
            })
        
        return {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_domains": len(ranked_list),
                "ranking_criteria": "url_frequency",
                "format": "frequency_ranked",
                "script_version": "1.0"
            },
            "domains": ranked_list
        }
    
    def save_json(self, data, filename, output_dir):
        """保存單個JSON文件"""
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return filepath

def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='從JSONL數據集中提取域名並生成JSON')
    parser.add_argument('input_files', nargs='+', help='輸入的JSONL文件路徑')
    parser.add_argument('-o', '--output', default='domain_extracts', help='輸出目錄 (默認: domain_extracts)')
    parser.add_argument('-f', '--format', choices=['simple', 'detailed', 'ranked', 'all'], 
                       default='all', help='輸出格式 (默認: all)')
    parser.add_argument('-v', '--verbose', action='store_true', help='顯示詳細輸出')
    parser.add_argument('--no-www', action='store_true', help='移除www前綴')
    
    args = parser.parse_args()
    
    # 初始化提取器
    extractor = DomainExtractor()
    
    # 加載所有數據文件
    all_data = []
    for file_path in args.input_files:
        if os.path.exists(file_path):
            if args.verbose:
                print(f"📂 加載文件: {file_path}")
            
            file_data = extractor.load_jsonl_data(file_path)
            if args.verbose:
                print(f"  └─ 成功加載 {len(file_data)} 條記錄")
            all_data.extend(file_data)
        else:
            print(f"⚠️  文件不存在: {file_path}")
    
    if not all_data:
        print("❌ 沒有找到任何有效數據")
        sys.exit(1)
    
    if args.verbose:
        print(f"\n✅ 總共加載了 {len(all_data)} 條記錄")
    
    # 處理數據
    domain_data = extractor.process_urls(all_data, args.verbose)
    
    if not domain_data:
        print("❌ 沒有提取到任何域名")
        sys.exit(1)
    
    # 生成輸出
    generator = JSONOutputGenerator(domain_data)
    
    # 顯示統計摘要
    if args.verbose:
        print(f"\n📊 域名統計摘要:")
        print(f"  唯一域名總數: {len(domain_data):,}")
        
        # 顯示前5個最頻繁域名
        top_domains = sorted(domain_data.items(), key=lambda x: x[1]['count'], reverse=True)[:5]
        print(f"\n🏆 前5個最頻繁域名:")
        for i, (domain, stats) in enumerate(top_domains, 1):
            print(f"  {i}. {domain}: {stats['count']} 次")
        
        # TLD統計
        tld_counter = Counter(stats['tld'] for stats in domain_data.values())
        print(f"\n🌐 頂級域名分布 (前3):")
        for tld, count in tld_counter.most_common(3):
            print(f"  .{tld}: {count} 個域名")
    
    # 保存文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved_files = []
    
    if args.format in ['simple', 'all']:
        data = generator.generate_simple_list()
        filename = f"domains_simple_{timestamp}.json"
        filepath = generator.save_json(data, filename, args.output)
        saved_files.append(filepath)
        if args.verbose:
            print(f"💾 已保存簡單列表: {filepath}")
    
    if args.format in ['detailed', 'all']:
        data = generator.generate_detailed_stats()
        filename = f"domains_detailed_{timestamp}.json"
        filepath = generator.save_json(data, filename, args.output)
        saved_files.append(filepath)
        if args.verbose:
            print(f"💾 已保存詳細統計: {filepath}")
    
    if args.format in ['ranked', 'all']:
        data = generator.generate_frequency_ranked()
        filename = f"domains_ranked_{timestamp}.json"
        filepath = generator.save_json(data, filename, args.output)
        saved_files.append(filepath)
        if args.verbose:
            print(f"💾 已保存頻率排序: {filepath}")
    
    # 輸出結果摘要
    print(f"\n✅ 完成！")
    print(f"📊 處理了 {len(all_data)} 條記錄")
    print(f"🌐 發現 {len(domain_data)} 個唯一域名")
    print(f"📁 生成了 {len(saved_files)} 個JSON文件")
    print(f"📂 輸出目錄: {args.output}")

if __name__ == "__main__":
    main()
