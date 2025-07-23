import json
import opencc
import re

# 分析已有数据并创建更好的过滤器
converter_s2t = opencc.OpenCC('s2t')
converter_t2s = opencc.OpenCC('t2s')

def analyze_existing_data():
    """分析已有的 improved 数据，找出问题并改进过滤"""
    print("分析已有数据中的质量问题...")
    
    good_samples = []
    bad_samples = []
    
    with open('fineweb-zhtw/data/output_improved/traditional_chinese_CC-MAIN-20240612140424-20240612170424-00001.warc.jsonl', 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= 50:  # 分析前50条
                break
                
            data = json.loads(line)
            text = data['text']
            
            # 检测问题
            issues = []
            
            # 检查是否主要是简体中文
            simplified = converter_t2s.convert(text)
            traditional = converter_s2t.convert(text)
            
            diff_simplified = sum(1 for a, b in zip(text, simplified) if a != b)
            diff_traditional = sum(1 for a, b in zip(text, traditional) if a != b)
            
            if diff_traditional > diff_simplified:
                issues.append("主要是简体中文")
            
            # 检查日语
            if re.search(r'[\u3040-\u309f\u30a0-\u30ff]', text):
                issues.append("包含日语")
            
            # 检查成人内容
            adult_keywords = ['AV', '做爱', '操逼', '色情', '无码', '有码', '成人', '三级']
            if any(keyword in text for keyword in adult_keywords):
                issues.append("成人内容")
            
            # 检查导航内容
            nav_keywords = ['首页', '联系我们', '关于我们', '版权所有', '产品大全', '友情链接']
            nav_count = sum(1 for keyword in nav_keywords if keyword in text)
            if nav_count >= 3:
                issues.append("导航内容")
            
            # 计算中文比例
            chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
            chinese_ratio = chinese_chars / len(text) if text else 0
            
            if issues:
                bad_samples.append({
                    'id': data['id'],
                    'url': data['url'],
                    'text_sample': text[:200],
                    'issues': issues,
                    'chinese_ratio': chinese_ratio,
                    'traditional_ratio': data['traditional_ratio']
                })
            else:
                good_samples.append({
                    'id': data['id'],
                    'url': data['url'],
                    'text_sample': text[:200],
                    'chinese_ratio': chinese_ratio,
                    'traditional_ratio': data['traditional_ratio']
                })
    
    print(f"\n分析结果:")
    print(f"好的样本: {len(good_samples)}")
    print(f"有问题的样本: {len(bad_samples)}")
    
    print(f"\n问题分布:")
    issue_counts = {}
    for sample in bad_samples:
        for issue in sample['issues']:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
    for issue, count in issue_counts.items():
        print(f"  {issue}: {count}")
    
    print(f"\n好的样本示例:")
    for i, sample in enumerate(good_samples[:3]):
        print(f"  {i+1}. ID: {sample['id']}")
        print(f"     URL: {sample['url']}")
        print(f"     繁体比例: {sample['traditional_ratio']:.3f}")
        print(f"     中文比例: {sample['chinese_ratio']:.3f}")
        print(f"     内容: {sample['text_sample'][:100]}...")
        print()
    
    return good_samples, bad_samples

def create_clean_dataset():
    """创建清理后的数据集"""
    good_samples, bad_samples = analyze_existing_data()
    
    print("创建清理后的数据集...")
    
    # 定义过滤条件
    def is_clean_traditional_chinese(text, min_ratio=0.02):
        # 检查成人内容
        adult_keywords = ['AV', '做爱', '操逼', '色情', '无码', '有码', '成人', '三级', 'porn', 'sex']
        if any(keyword.lower() in text.lower() for keyword in adult_keywords):
            return False
        
        # 检查日语干扰
        japanese_chars = len(re.findall(r'[\u3040-\u309f\u30a0-\u30ff]', text))
        if japanese_chars > len(text) * 0.05:  # 日语字符超过5%
            return False
        
        # 检查是否主要是导航内容
        nav_keywords = ['首页', '联系我们', '关于我们', '版权所有', '产品大全', '友情链接', '更多', '下一页', '上一页']
        nav_count = sum(1 for keyword in nav_keywords if keyword in text)
        if nav_count >= 3 and len(text) < 500:
            return False
        
        # 检查中文字符比例
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        chinese_ratio = chinese_chars / len(text) if text else 0
        if chinese_ratio < 0.3:
            return False
        
        # 检查是否真的是繁体中文
        simplified = converter_t2s.convert(text)
        diff_simplified = sum(1 for a, b in zip(text, simplified) if a != b)
        traditional_ratio = diff_simplified / len(text) if text else 0
        
        return traditional_ratio >= min_ratio
    
    clean_count = 0
    output_file = 'fineweb-zhtw/data/output_high_quality/cleaned_traditional_chinese.jsonl'
    
    with open('fineweb-zhtw/data/output_improved/traditional_chinese_CC-MAIN-20240612140424-20240612170424-00001.warc.jsonl', 'r', encoding='utf-8') as f:
        with open(output_file, 'w', encoding='utf-8') as out_f:
            for line in f:
                data = json.loads(line)
                text = data['text']
                
                if is_clean_traditional_chinese(text):
                    # 重新计算繁体比例
                    simplified = converter_t2s.convert(text)
                    diff_simplified = sum(1 for a, b in zip(text, simplified) if a != b)
                    traditional_ratio = diff_simplified / len(text) if text else 0
                    
                    # 计算中文比例
                    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
                    chinese_ratio = chinese_chars / len(text) if text else 0
                    
                    clean_record = {
                        'id': data['id'],
                        'url': data['url'],
                        'text': text,
                        'text_length': len(text),
                        'traditional_ratio': traditional_ratio,
                        'chinese_ratio': chinese_ratio,
                        'is_traditional_chinese': True,
                        'source_file': data['source_file']
                    }
                    
                    out_f.write(json.dumps(clean_record, ensure_ascii=False) + '\n')
                    clean_count += 1
    
    print(f"✅ 清理完成，保存了 {clean_count} 条清洁的繁体中文记录")
    print(f"📁 输出文件: {output_file}")
    
    return clean_count

if __name__ == "__main__":
    create_clean_dataset()
