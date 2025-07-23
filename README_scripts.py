#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用說明和示例

這兩個腳本的用途和使用方法
"""

# 腳本1: extract_domains.py - 域名提取腳本使用說明
"""
功能: 從JSONL數據集中提取唯一域名並生成JSON文件

基本用法:
python extract_domains.py input_file.jsonl

進階用法:
python extract_domains.py file1.jsonl file2.jsonl -o output_dir -f simple -v

參數說明:
- input_files: 一個或多個JSONL輸入文件
- -o, --output: 輸出目錄 (默認: domain_extracts)
- -f, --format: 輸出格式 (simple/detailed/ranked/all, 默認: all)
- -v, --verbose: 顯示詳細輸出
- --no-www: 移除www前綴

輸出文件格式:
1. domains_simple_YYYYMMDD_HHMMSS.json - 純域名列表
2. domains_detailed_YYYYMMDD_HHMMSS.json - 詳細統計信息
3. domains_ranked_YYYYMMDD_HHMMSS.json - 按頻率排序

示例:
python extract_domains.py output_all/extracted_content.jsonl -v
python extract_domains.py *.jsonl -f simple -o my_domains
"""

# 腳本2: check_crawlability.py - 爬取權限檢查腳本使用說明
"""
功能: 檢查域名的robots.txt和爬取權限

基本用法:
python check_crawlability.py domains.json

進階用法:
python check_crawlability.py domains.json -o results -u "MyBot/1.0" -w 5 -v

參數說明:
- domain_json: 包含域名的JSON文件 (由extract_domains.py生成)
- -o, --output: 輸出目錄 (默認: crawlability_check)
- -u, --user-agent: User-Agent字符串 (默認: *)
- -t, --timeout: 請求超時時間秒數 (默認: 10)
- -w, --workers: 並發線程數 (默認: 10)
- -v, --verbose: 顯示詳細輸出
- --limit: 限制檢查域名數量 (用於測試)

輸出文件:
1. robots_check_results_YYYYMMDD_HHMMSS.json - 詳細檢查結果
2. crawlability_stats_YYYYMMDD_HHMMSS.json - 統計分析和建議
3. crawlable_domains_YYYYMMDD_HHMMSS.json - 可安全爬取的域名列表

示例:
python check_crawlability.py domain_extracts/domains_simple_20250717_162329.json -v
python check_crawlability.py domains.json --limit 100 -u "TestBot/1.0"
"""

# 完整工作流程示例
"""
完整使用流程:

1. 從JSONL提取域名:
python extract_domains.py output_all/extracted_content.jsonl -v

2. 檢查爬取權限:
python check_crawlability.py domain_extracts/domains_simple_20250717_162329.json -v

3. 查看結果:
- 可爬取域名: crawlability_check/crawlable_domains_YYYYMMDD_HHMMSS.json
- 詳細分析: crawlability_check/crawlability_stats_YYYYMMDD_HHMMSS.json

4. 根據結果決定爬取策略
"""

# 安裝依賴
"""
安裝所需依賴包:
pip install requests

或使用requirements.txt:
echo "requests>=2.25.0" > requirements.txt
pip install -r requirements.txt
"""

# 輸出JSON格式說明
"""
domains_simple.json 格式:
{
  "metadata": {
    "generated_at": "2025-07-17T16:23:29",
    "total_domains": 2954,
    "format": "simple_list"
  },
  "domains": ["domain1.com", "domain2.org", ...]
}

robots_check_results.json 格式:
{
  "metadata": {...},
  "results": {
    "example.com": {
      "robots_exists": true,
      "crawl_allowed": true,
      "crawl_delay": 1.0,
      "disallowed_paths": ["/admin/"],
      "sitemap_urls": ["https://example.com/sitemap.xml"]
    }
  }
}

crawlable_domains.json 格式:
{
  "metadata": {
    "total_crawlable": 2500,
    "source_file": "domains.json"
  },
  "crawlable_domains": ["safe1.com", "safe2.org", ...]
}
"""
