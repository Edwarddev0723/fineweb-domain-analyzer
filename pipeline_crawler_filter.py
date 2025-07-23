#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整的爬取權限過濾流程
步驟1: 從資料集提取域名
步驟2: 檢查域名的robots.txt和爬取權限
步驟3: 根據爬取權限過濾原始數據

作者: AI助手
日期: 2025-07-18
"""

import json
import os
import sys
import time
import argparse
from datetime import datetime
from urllib.parse import urlparse
from collections import defaultdict, Counter

# 導入我們的模塊
from extract_domains import DomainExtractor, JSONOutputGenerator
from check_crawlability import RobotsChecker, CrawlabilityAnalyzer

def load_jsonl_data(file_path):
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
        print(f"文件未找到: {file_path}")
        return []
    except Exception as e:
        print(f"讀取文件時出錯: {e}")
        return []

class CrawlerFilterPipeline:
    """完整的爬取權限過濾流程"""
    
    def __init__(self, verbose=True, timeout=10, max_workers=10):
        self.verbose = verbose
        self.timeout = timeout
        self.max_workers = max_workers
        self.pipeline_results = {
            'step1_domains': {},
            'step2_crawlability': {},
            'step3_filtered': {},
            'pipeline_stats': {}
        }
    
    def log(self, message):
        """輸出日誌"""
        if self.verbose:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] {message}")
    
    def step1_extract_domains(self, input_files, output_dir="pipeline_output"):
        """
        步驟1: 從資料集提取域名
        """
        self.log("🚀 步驟1: 提取域名開始")
        
        # 創建輸出目錄
        os.makedirs(output_dir, exist_ok=True)
        
        # 加載所有數據文件
        all_data = []
        for file_path in input_files:
            if os.path.exists(file_path):
                self.log(f"📂 加載文件: {file_path}")
                file_data = load_jsonl_data(file_path)
                self.log(f"  └─ 成功加載 {len(file_data)} 條記錄")
                all_data.extend(file_data)
            else:
                self.log(f"⚠️ 文件不存在: {file_path}")
        
        if not all_data:
            raise ValueError("沒有找到有效的數據文件")
        
        self.log(f"✅ 總共加載了 {len(all_data)} 條記錄")
        
        # 提取域名
        extractor = DomainExtractor()
        domain_data = extractor.process_urls(all_data)
        
        # 生成域名列表
        generator = JSONOutputGenerator(domain_data)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存簡單域名列表用於下一步
        simple_domains = list(domain_data.keys())
        domain_file = os.path.join(output_dir, f"extracted_domains_{timestamp}.json")
        
        with open(domain_file, 'w', encoding='utf-8') as f:
            json.dump({
                'metadata': {
                    'generated_at': datetime.now().isoformat(),
                    'total_domains': len(simple_domains),
                    'total_urls_processed': len(all_data),
                    'format': 'simple_list',
                    'pipeline_step': 1
                },
                'domains': simple_domains
            }, f, ensure_ascii=False, indent=2)
        
        # 保存詳細統計
        detailed_file = os.path.join(output_dir, f"domain_stats_{timestamp}.json")
        detailed_data = generator.generate_detailed_stats()
        with open(detailed_file, 'w', encoding='utf-8') as f:
            json.dump(detailed_data, f, ensure_ascii=False, indent=2)
        
        # 更新pipeline結果
        self.pipeline_results['step1_domains'] = {
            'domain_file': domain_file,
            'detailed_file': detailed_file,
            'total_domains': len(simple_domains),
            'total_urls': len(all_data),
            'domain_list': simple_domains
        }
        
        self.log(f"✅ 步驟1完成: 提取出 {len(simple_domains)} 個唯一域名")
        self.log(f"📁 域名文件: {domain_file}")
        
        return domain_file, simple_domains
    
    def step2_check_crawlability(self, domain_file, output_dir="pipeline_output"):
        """
        步驟2: 檢查域名的robots.txt和爬取權限
        """
        self.log("🤖 步驟2: 檢查爬取權限開始")
        
        # 讀取域名文件
        with open(domain_file, 'r', encoding='utf-8') as f:
            domain_data = json.load(f)
        
        domains = domain_data.get('domains', [])
        self.log(f"🌐 準備檢查 {len(domains)} 個域名")
        
        # 初始化檢查器
        checker = RobotsChecker(
            user_agent="*",
            timeout=self.timeout,
            max_workers=self.max_workers
        )
        
        # 執行批量檢查
        results = checker.check_domains_batch(domains, verbose=self.verbose)
        
        # 分析結果
        analyzer = CrawlabilityAnalyzer(results)
        stats = analyzer.analyze_crawlability()
        recommendations = analyzer.generate_recommendations(stats)
        
        # 生成域名標籤 (1=可爬, 0=不可爬)
        domain_labels = {}
        crawlable_domains = set()
        non_crawlable_domains = set()
        
        for domain, result in results.items():
            if result.get('crawl_allowed', False) and not result.get('error'):
                domain_labels[domain] = 1
                crawlable_domains.add(domain)
            else:
                domain_labels[domain] = 0
                non_crawlable_domains.add(domain)
        
        # 保存結果
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 1. 詳細檢查結果
        results_file = os.path.join(output_dir, f"crawlability_results_{timestamp}.json")
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump({
                'metadata': {
                    'generated_at': datetime.now().isoformat(),
                    'total_domains': len(domains),
                    'pipeline_step': 2,
                    'user_agent': "*",
                    'timeout': self.timeout
                },
                'results': results,
                'statistics': stats,
                'recommendations': recommendations
            }, f, ensure_ascii=False, indent=2)
        
        # 2. 域名標籤文件 (關鍵輸出)
        labels_file = os.path.join(output_dir, f"domain_labels_{timestamp}.json")
        with open(labels_file, 'w', encoding='utf-8') as f:
            json.dump({
                'metadata': {
                    'generated_at': datetime.now().isoformat(),
                    'total_domains': len(domain_labels),
                    'crawlable_count': len(crawlable_domains),
                    'non_crawlable_count': len(non_crawlable_domains),
                    'crawlable_rate': len(crawlable_domains) / len(domain_labels) * 100,
                    'pipeline_step': 2,
                    'format': 'domain_labels'
                },
                'domain_labels': domain_labels,
                'crawlable_domains': list(crawlable_domains),
                'non_crawlable_domains': list(non_crawlable_domains)
            }, f, ensure_ascii=False, indent=2)
        
        # 更新pipeline結果
        self.pipeline_results['step2_crawlability'] = {
            'results_file': results_file,
            'labels_file': labels_file,
            'total_checked': len(domains),
            'crawlable_count': len(crawlable_domains),
            'non_crawlable_count': len(non_crawlable_domains),
            'crawlable_rate': len(crawlable_domains) / len(domain_labels) * 100,
            'domain_labels': domain_labels
        }
        
        self.log(f"✅ 步驟2完成: {len(crawlable_domains)} 個可爬取, {len(non_crawlable_domains)} 個不可爬取")
        self.log(f"📊 可爬取率: {len(crawlable_domains) / len(domain_labels) * 100:.1f}%")
        self.log(f"📁 標籤文件: {labels_file}")
        
        return labels_file, domain_labels
    
    def step3_filter_data(self, input_files, domain_labels, output_dir="pipeline_output"):
        """
        步驟3: 根據域名標籤過濾原始數據
        """
        self.log("🔍 步驟3: 過濾原始數據開始")
        
        # 統計信息
        total_records = 0
        filtered_records = 0
        crawlable_records = 0
        non_crawlable_records = 0
        unknown_domain_records = 0
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 為每個輸入文件創建過濾後的版本
        filtered_files = []
        
        for input_file in input_files:
            if not os.path.exists(input_file):
                self.log(f"⚠️ 跳過不存在的文件: {input_file}")
                continue
            
            self.log(f"📂 處理文件: {input_file}")
            
            # 生成輸出文件名
            base_name = os.path.splitext(os.path.basename(input_file))[0]
            output_file = os.path.join(output_dir, f"filtered_{base_name}_{timestamp}.jsonl")
            rejected_file = os.path.join(output_dir, f"rejected_{base_name}_{timestamp}.jsonl")
            
            file_total = 0
            file_kept = 0
            file_rejected = 0
            file_unknown = 0
            
            with open(input_file, 'r', encoding='utf-8') as infile, \
                 open(output_file, 'w', encoding='utf-8') as outfile, \
                 open(rejected_file, 'w', encoding='utf-8') as rejfile:
                
                for line_num, line in enumerate(infile, 1):
                    if not line.strip():
                        continue
                    
                    try:
                        record = json.loads(line)
                        url = record.get('url', '')
                        
                        if not url:
                            # 沒有URL的記錄直接拒絶
                            rejfile.write(line)
                            file_rejected += 1
                            continue
                        
                        # 提取域名
                        try:
                            parsed = urlparse(url)
                            domain = parsed.netloc.lower()
                            if ':' in domain:
                                domain = domain.split(':')[0]
                            if domain.startswith('www.'):
                                domain = domain[4:]
                        except:
                            # URL解析失敗
                            rejfile.write(line)
                            file_rejected += 1
                            continue
                        
                        # 檢查域名標籤
                        if domain in domain_labels:
                            if domain_labels[domain] == 1:  # 可爬取
                                outfile.write(line)
                                file_kept += 1
                                crawlable_records += 1
                            else:  # 不可爬取
                                rejfile.write(line)
                                file_rejected += 1
                                non_crawlable_records += 1
                        else:
                            # 未知域名 - 保守處理，拒絶
                            rejfile.write(line)
                            file_rejected += 1
                            file_unknown += 1
                            unknown_domain_records += 1
                        
                        file_total += 1
                        total_records += 1
                        
                        # 進度顯示
                        if line_num % 1000 == 0:
                            self.log(f"  處理進度: {line_num} 行")
                    
                    except json.JSONDecodeError as e:
                        self.log(f"  ⚠️ 第{line_num}行JSON解析錯誤: {e}")
                        rejfile.write(line)
                        file_rejected += 1
                        continue
            
            filtered_records += file_kept
            
            self.log(f"  ✅ {os.path.basename(input_file)}: {file_kept}/{file_total} 記錄保留 ({file_kept/file_total*100:.1f}%)")
            self.log(f"     保留: {output_file}")
            self.log(f"     拒絕: {rejected_file}")
            
            filtered_files.append({
                'input_file': input_file,
                'output_file': output_file,
                'rejected_file': rejected_file,
                'total_records': file_total,
                'kept_records': file_kept,
                'rejected_records': file_rejected,
                'unknown_domains': file_unknown
            })
        
        # 生成過濾報告
        report_file = os.path.join(output_dir, f"filtering_report_{timestamp}.json")
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump({
                'metadata': {
                    'generated_at': datetime.now().isoformat(),
                    'pipeline_step': 3,
                    'total_input_files': len(input_files),
                    'processed_files': len(filtered_files)
                },
                'summary': {
                    'total_records_processed': total_records,
                    'records_kept': filtered_records,
                    'records_rejected': total_records - filtered_records,
                    'retention_rate': filtered_records / total_records * 100 if total_records > 0 else 0,
                    'crawlable_records': crawlable_records,
                    'non_crawlable_records': non_crawlable_records,
                    'unknown_domain_records': unknown_domain_records
                },
                'file_details': filtered_files
            }, f, ensure_ascii=False, indent=2)
        
        # 更新pipeline結果
        self.pipeline_results['step3_filtered'] = {
            'report_file': report_file,
            'filtered_files': filtered_files,
            'total_processed': total_records,
            'total_kept': filtered_records,
            'retention_rate': filtered_records / total_records * 100 if total_records > 0 else 0
        }
        
        self.log(f"✅ 步驟3完成: {filtered_records}/{total_records} 記錄保留 ({filtered_records/total_records*100:.1f}%)")
        self.log(f"📁 過濾報告: {report_file}")
        
        return filtered_files, report_file
    
    def run_complete_pipeline(self, input_files, output_dir="pipeline_output"):
        """
        運行完整的三步驟流程
        """
        start_time = time.time()
        self.log("🚀 開始完整的爬取權限過濾流程")
        
        try:
            # 步驟1: 提取域名
            domain_file, domains = self.step1_extract_domains(input_files, output_dir)
            
            # 步驟2: 檢查爬取權限
            labels_file, domain_labels = self.step2_check_crawlability(domain_file, output_dir)
            
            # 步驟3: 過濾數據
            filtered_files, report_file = self.step3_filter_data(input_files, domain_labels, output_dir)
            
            # 生成最終摘要
            elapsed_time = time.time() - start_time
            
            self.pipeline_results['pipeline_stats'] = {
                'total_runtime': elapsed_time,
                'completed_at': datetime.now().isoformat(),
                'success': True
            }
            
            # 保存完整的pipeline結果
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            summary_file = os.path.join(output_dir, f"pipeline_summary_{timestamp}.json")
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(self.pipeline_results, f, ensure_ascii=False, indent=2)
            
            self.log("=" * 60)
            self.log("🎉 完整流程執行成功!")
            self.log(f"⏱️  總耗時: {elapsed_time:.1f} 秒")
            self.log(f"🌐 處理域名: {self.pipeline_results['step1_domains']['total_domains']}")
            self.log(f"✅ 可爬取域名: {self.pipeline_results['step2_crawlability']['crawlable_count']}")
            self.log(f"📊 可爬取率: {self.pipeline_results['step2_crawlability']['crawlable_rate']:.1f}%")
            self.log(f"📝 數據保留率: {self.pipeline_results['step3_filtered']['retention_rate']:.1f}%")
            self.log(f"📁 輸出目錄: {output_dir}")
            self.log(f"📋 完整摘要: {summary_file}")
            self.log("=" * 60)
            
            return True, summary_file
            
        except Exception as e:
            self.log(f"❌ 流程執行失敗: {e}")
            self.pipeline_results['pipeline_stats'] = {
                'total_runtime': time.time() - start_time,
                'completed_at': datetime.now().isoformat(),
                'success': False,
                'error': str(e)
            }
            return False, str(e)

def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='完整的爬取權限過濾流程')
    parser.add_argument('input_files', nargs='+', help='輸入的JSONL數據文件')
    parser.add_argument('-o', '--output', default='pipeline_output', help='輸出目錄 (默認: pipeline_output)')
    parser.add_argument('-t', '--timeout', type=int, default=10, help='請求超時時間 (默認: 10秒)')
    parser.add_argument('-w', '--workers', type=int, default=10, help='並發數量 (默認: 10)')
    parser.add_argument('-v', '--verbose', action='store_true', help='顯示詳細輸出')
    parser.add_argument('--step', type=int, choices=[1, 2, 3], help='只執行特定步驟 (默認: 執行全部)')
    
    args = parser.parse_args()
    
    # 檢查輸入文件
    valid_files = []
    for file_path in args.input_files:
        if os.path.exists(file_path):
            valid_files.append(file_path)
        else:
            print(f"⚠️ 文件不存在: {file_path}")
    
    if not valid_files:
        print("❌ 沒有找到有效的輸入文件")
        sys.exit(1)
    
    # 初始化pipeline
    pipeline = CrawlerFilterPipeline(
        verbose=args.verbose,
        timeout=args.timeout,
        max_workers=args.workers
    )
    
    try:
        if args.step:
            print(f"🎯 執行單一步驟: {args.step}")
            # 這裡可以添加單步驟執行的邏輯
            print("⚠️ 單步驟執行功能待實現，請使用完整流程")
        else:
            # 執行完整流程
            success, result = pipeline.run_complete_pipeline(valid_files, args.output)
            
            if success:
                print(f"✅ 流程執行成功，詳見: {result}")
                sys.exit(0)
            else:
                print(f"❌ 流程執行失敗: {result}")
                sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n⚠️ 用戶中斷操作")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 程序異常: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
