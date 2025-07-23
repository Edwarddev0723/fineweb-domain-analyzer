# 三步驟爬取權限過濾流程使用指南

## 🎯 功能概述

這個完整的流程包含三個步驟：

1. **步驟1**: 從資料集中提取所有唯一域名
2. **步驟2**: 檢查每個域名的robots.txt和爬取權限，生成域名標籤（1=可爬，0=不可爬）
3. **步驟3**: 根據域名標籤過濾原始數據，移除不可爬取網站的數據

## 🚀 快速開始

### 完整流程執行
```bash
# 基本用法
python pipeline_crawler_filter.py input_file.jsonl

# 多文件處理
python pipeline_crawler_filter.py file1.jsonl file2.jsonl file3.jsonl

# 自定義配置
python pipeline_crawler_filter.py input_file.jsonl -o output_folder -t 15 -w 5 -v

# 參數說明
# -o: 輸出目錄 (默認: pipeline_output)
# -t: 超時時間 (默認: 10秒)
# -w: 並發線程數 (默認: 10)
# -v: 詳細輸出
```

### 單獨步驟執行

#### 步驟1: 提取域名
```bash
python extract_domains.py input_file.jsonl -f simple -v
```

#### 步驟2: 檢查爬取權限
```bash
python check_crawlability.py domains.json -t 10 -w 5 -v
```

#### 步驟3: 使用完整流程的過濾功能
```bash
# 需要使用 pipeline_crawler_filter.py 的步驟3功能
```

## 📊 輸出文件說明

### 步驟1輸出
- `extracted_domains_TIMESTAMP.json`: 提取的域名列表
- `domain_stats_TIMESTAMP.json`: 域名統計詳情

### 步驟2輸出
- `crawlability_results_TIMESTAMP.json`: 詳細的robots.txt檢查結果
- `domain_labels_TIMESTAMP.json`: **關鍵文件** - 域名標籤（1=可爬，0=不可爬）

### 步驟3輸出
- `filtered_FILENAME_TIMESTAMP.jsonl`: 過濾後的數據（只保留可爬取網站）
- `rejected_FILENAME_TIMESTAMP.jsonl`: 被拒絕的數據（不可爬取網站）
- `filtering_report_TIMESTAMP.json`: 過濾統計報告

### 完整流程輸出
- `pipeline_summary_TIMESTAMP.json`: 整個流程的摘要報告

## 📋 流程詳細說明

### 步驟1: 域名提取
```
輸入: JSONL數據文件
處理: 從每條記錄的URL中提取域名
輸出: 唯一域名列表 + 統計信息
```

### 步驟2: 爬取權限檢查
```
輸入: 域名列表
處理: 
  - 檢查每個域名的robots.txt
  - 分析是否允許爬取
  - 處理超時和錯誤情況
輸出: 域名標籤文件 (domain_labels.json)
```

**域名標籤格式:**
```json
{
  "metadata": {
    "crawlable_count": 1500,
    "non_crawlable_count": 500,
    "crawlable_rate": 75.0
  },
  "domain_labels": {
    "example.com": 1,     // 可爬取
    "blocked-site.com": 0  // 不可爬取
  }
}
```

### 步驟3: 數據過濾
```
輸入: 原始JSONL數據 + 域名標籤
處理:
  - 對每條記錄提取URL域名
  - 查詢域名標籤
  - 根據標籤決定保留或拒絕
輸出: 
  - 過濾後的數據文件（只含可爬取網站）
  - 被拒絕的數據文件
  - 詳細統計報告
```

## 🔧 進階配置

### 調整檢查參數
```python
# 在 pipeline_crawler_filter.py 中修改
pipeline = CrawlerFilterPipeline(
    verbose=True,        # 詳細輸出
    timeout=15,          # 增加超時時間
    max_workers=5        # 減少並發數（適合網絡較慢環境）
)
```

### 自定義過濾邏輯
可以修改 `step3_filter_data` 方法中的過濾邏輯：
```python
# 當前邏輯: 
# - 域名標籤=1: 保留
# - 域名標籤=0: 拒絕  
# - 未知域名: 拒絕（保守策略）

# 可修改為更寬鬆的策略：
if domain in domain_labels:
    if domain_labels[domain] == 0:  # 只拒絕明確禁止的
        rejfile.write(line)
    else:
        outfile.write(line)  # 保留可爬取和未知的
else:
    outfile.write(line)  # 未知域名也保留
```

## 📈 性能優化建議

### 大規模數據處理
1. **分批處理**: 大文件可以先分割再處理
2. **調整並發數**: 根據網絡和系統性能調整 `-w` 參數
3. **增加超時**: 不穩定網絡環境下增加 `-t` 參數

### 網絡優化
```bash
# 保守設置（適合網絡不穩定）
python pipeline_crawler_filter.py input.jsonl -t 20 -w 3 -v

# 激進設置（適合高速網絡）
python pipeline_crawler_filter.py input.jsonl -t 5 -w 20 -v
```

## 📊 預期結果

### 典型的過濾率
- **域名可爬取率**: 60-80%（取決於數據來源）
- **數據保留率**: 70-85%（可爬取域名通常包含更多內容）
- **處理速度**: 10-50 域名/秒（取決於網絡狀況）

### 示例輸出
```
🎉 完整流程執行成功!
⏱️  總耗時: 245.3 秒
🌐 處理域名: 2946
✅ 可爬取域名: 2204
📊 可爬取率: 74.8%
📝 數據保留率: 81.2%
📁 輸出目錄: pipeline_output
```

## ⚠️ 注意事項

1. **網絡依賴**: 步驟2需要穩定的網絡連接
2. **時間消耗**: 大量域名檢查需要較長時間
3. **保守策略**: 未知或錯誤的域名會被標記為不可爬取
4. **robots.txt變化**: 檢查結果會隨時間變化，建議定期重新檢查

## 🆘 故障排除

### 常見問題

**Q: 在98%進度卡住？**
```
A: 新版本已優化，採用分批處理避免卡住
   如仍有問題，可以降低並發數: -w 3
```

**Q: 網絡超時過多？**
```
A: 增加超時時間: -t 20
   或減少並發數: -w 5
```

**Q: 內存不足？**
```
A: 將大文件分割後分別處理
   或使用流式處理功能
```

**Q: 過濾率太低？**
```
A: 檢查域名標籤文件，了解拒絕原因
   可能需要調整過濾策略
```

## 🔗 相關文件

- `extract_domains.py`: 域名提取腳本
- `check_crawlability.py`: 爬取權限檢查腳本  
- `pipeline_crawler_filter.py`: 完整流程腳本
- `README.md`: 項目總體說明
