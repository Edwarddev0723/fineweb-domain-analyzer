# 腳本使用說明和測試結果

## 腳本概覽

已成功創建兩個獨立的Python腳本：

### 1. extract_domains.py - 域名提取腳本
- **功能**: 從JSONL數據集中提取唯一域名
- **輸入**: JSONL文件（如FineWeb數據）
- **輸出**: JSON格式的域名列表

### 2. check_crawlability.py - 可爬取性檢查腳本  
- **功能**: 檢查域名的robots.txt和爬取權限
- **輸入**: 域名JSON文件
- **輸出**: 包含爬取分析結果的JSON文件

## 測試結果

### ✅ extract_domains.py 測試成功
**測試命令**:
```bash
python extract_domains.py "output_all\extracted_content_CC-MAIN-20240612140424-20240612170424-00000.warc.jsonl" -f simple -v
```

**測試結果**:
- 成功處理 3,184 條記錄
- 發現 2,946 個唯一域名
- 生成文件: `domain_extracts\domains_simple_20250717_222545.json`

**域名分佈統計**:
- .com域名: 1,416個 (48.1%)
- .ru域名: 185個 (6.3%)  
- .org域名: 138個 (4.7%)

**高頻域名前5**:
1. cujasweb.univ-paris1.fr: 5次
2. licitacoeseb.9rm.eb.mil.br: 4次
3. luna.library.cmu.edu: 4次
4. siganus.php.xdomain.jp: 4次
5. imagemagick.org: 4次

### ⚠️ check_crawlability.py 功能驗證
**腳本特點**:
- 支援並發處理（可調整線程數）
- 自動超時處理
- 詳細的robots.txt分析
- 生成統計報告

**建議使用**:
```bash
# 小規模測試（推薦）
python check_crawlability.py test_domains.json -t 3 -v

# 大規模處理（需要較長時間）
python check_crawlability.py domains_simple_20250717_222545.json -t 10
```

## 完整工作流程

1. **提取域名**:
   ```bash
   python extract_domains.py input.jsonl -f simple -v
   ```

2. **檢查可爬取性**:
   ```bash
   python check_crawlability.py domains.json -t 5 -o crawl_results.json
   ```

3. **查看結果**:
   - 域名列表: `domain_extracts/`目錄
   - 爬取分析: 指定的輸出文件

## 文件結構

```
Fine_Web_anal/
├── extract_domains.py      # 域名提取腳本
├── check_crawlability.py   # 可爬取性檢查腳本
├── README_scripts.py       # 詳細使用說明
├── requirements.txt        # 依賴包列表
├── domain_extracts/        # 域名提取結果目錄
└── output_all/            # 原始數據目錄
```

## 依賴安裝

```bash
pip install -r requirements.txt
```

## 注意事項

1. **大規模處理**: 2946個域名的robots.txt檢查需要較長時間
2. **網絡依賴**: check_crawlability.py需要穩定的網絡連接
3. **並發設置**: 根據網絡狀況調整線程數（-t參數）
4. **輸出管理**: 結果文件包含時間戳，避免覆蓋

## 成功指標

✅ extract_domains.py: 完全測試通過  
✅ 域名提取: 2,946個唯一域名  
✅ JSON輸出: 格式正確，包含元數據  
✅ 統計分析: TLD分佈和頻率排序  
🔄 check_crawlability.py: 腳本就緒，建議小規模測試
