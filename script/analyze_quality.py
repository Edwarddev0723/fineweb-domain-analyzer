import json
import opencc
import re

# 分析当前数据的质量
converter_s2t = opencc.OpenCC('s2t')
converter_t2s = opencc.OpenCC('t2s')

def analyze_text_quality(text):
    # 转换为简体和繁体
    simplified = converter_t2s.convert(text)
    traditional = converter_s2t.convert(text)
    
    # 检查原文与转换后的差异
    original_vs_simplified = sum(1 for a, b in zip(text, simplified) if a != b)
    original_vs_traditional = sum(1 for a, b in zip(text, traditional) if a != b)
    
    # 计算中文字符比例
    chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
    chinese_ratio = chinese_chars / len(text) if text else 0
    
    # 检查是否包含日语假名
    has_hiragana = bool(re.search(r'[\u3040-\u309f]', text))
    has_katakana = bool(re.search(r'[\u30a0-\u30ff]', text))
    has_japanese = has_hiragana or has_katakana
    
    # 检查韩语
    has_korean = bool(re.search(r'[\uac00-\ud7af]', text))
    
    return {
        'chinese_ratio': chinese_ratio,
        'diff_from_simplified': original_vs_simplified / len(text) if text else 0,
        'diff_from_traditional': original_vs_traditional / len(text) if text else 0,
        'is_likely_traditional': original_vs_simplified > original_vs_traditional and chinese_ratio > 0.1,
        'has_japanese': has_japanese,
        'has_korean': has_korean,
        'has_hiragana': has_hiragana,
        'has_katakana': has_katakana
    }

def detect_content_issues(text):
    """检测内容问题"""
    issues = []
    
    # 检查是否主要是简体中文
    simplified = converter_t2s.convert(text)
    traditional = converter_s2t.convert(text)
    
    original_vs_simplified = sum(1 for a, b in zip(text, simplified) if a != b)
    original_vs_traditional = sum(1 for a, b in zip(text, traditional) if a != b)
    
    if original_vs_traditional > original_vs_simplified:
        issues.append("主要是简体中文")
    
    # 检查日语内容
    if re.search(r'[\u3040-\u309f]', text):
        issues.append("包含日语平假名")
    if re.search(r'[\u30a0-\u30ff]', text):
        issues.append("包含日语片假名")
    
    # 检查韩语
    if re.search(r'[\uac00-\ud7af]', text):
        issues.append("包含韩语")
        
    # 检查越南语特殊字符
    if re.search(r'[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]', text):
        issues.append("包含越南语")
        
    # 检查是否主要是导航/垃圾内容
    nav_indicators = ['首页', '联系我们', '关于我们', '版权所有', 'Copyright', '网站地图', 'sitemap', 
                     '产品大全', '友情链接', '更多', 'More', '下一页', '上一页', '菜单', 'menu']
    nav_count = sum(1 for indicator in nav_indicators if indicator in text)
    if nav_count >= 3:
        issues.append("疑似导航/垃圾内容")
    
    return issues

# 读取并分析前10条数据
print("分析当前提取的繁体中文数据质量...")
print("=" * 60)

with open('fineweb-zhtw/data/output_improved/traditional_chinese_CC-MAIN-20240612140424-20240612170424-00001.warc.jsonl', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i >= 10:
            break
        data = json.loads(line)
        text_sample = data['text'][:300]  # 分析前300字符
        analysis = analyze_text_quality(text_sample)
        issues = detect_content_issues(data['text'])
        
        print(f"记录 {i+1}:")
        print(f"ID: {data['id']}")
        print(f"URL: {data['url']}")
        print(f"文本长度: {data['text_length']}")
        print(f"繁体比例: {data['traditional_ratio']:.3f}")
        print(f"中文字符比例: {analysis['chinese_ratio']:.3f}")
        print(f"与简体差异: {analysis['diff_from_simplified']:.3f}")
        print(f"与繁体差异: {analysis['diff_from_traditional']:.3f}")
        print(f"可能是繁体: {analysis['is_likely_traditional']}")
        print(f"包含日语: {analysis['has_japanese']}")
        print(f"包含韩语: {analysis['has_korean']}")
        print(f"内容问题: {', '.join(issues) if issues else '无明显问题'}")
        print(f"文本样本: {text_sample[:100]}...")
        print("-" * 60)
