import gzip
import json
import re
import html
import opencc
from urllib.parse import urlparse
import os

class AdvancedTraditionalChineseProcessor:
    def __init__(self):
        # 初始化转换器
        self.converter_s2t = opencc.OpenCC('s2t')
        self.converter_t2s = opencc.OpenCC('t2s') 
        
        # 严格的不当内容过滤
        self.inappropriate_keywords = [
            # 成人内容
            'AV', '做爱', '操逼', '色情', '裸体', '性爱', '三级', 'porn', 'sex',
            '无码', '有码', '成人', '情色', '激情', '淫', '骚', '爽', 'JAV',
            '嫩妹', '闺蜜', '巨乳', '制服', '丝袜', '人妻', '熟女', 'www',
            # 赌博博彩
            '赌', '博彩', '赌场', '投注', '下注', 'casino', 'bet',
            # 其他垃圾内容
            '免费下载', '种子', 'torrent', '破解', '盗版'
        ]
        
        # 导航垃圾内容关键词
        self.navigation_keywords = [
            '首页', '联系我们', '关于我们', '版权所有', 'Copyright', '网站地图',
            '产品大全', '友情链接', '更多', 'More', '下一页', '上一页', '菜单',
            '登录', '注册', '购物车', '搜索结果', '全部分类', '热门推荐',
            '最新更新', '相关推荐', '点击查看', '立即购买', '免费试用',
            '马上注册', '二手车', '车源', '商家', '价格', '万以内'
        ]
        
        # 日语常见词汇（用于检测日语内容）
        self.japanese_keywords = [
            'スタッフ', 'サイト', 'ガイド', 'ポリシー', 'アプリ', 'システム',
            'プレイ', 'ユーザー', 'サービス', 'コンテンツ', 'ページ', 'フォーム'
        ]
        
    def clean_text(self, text):
        """深度清理文本"""
        # HTML实体解码
        text = html.unescape(text)
        
        # 移除HTML标签残留
        text = re.sub(r'<[^>]+>', '', text)
        
        # 移除URL和邮箱
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', text)
        
        # 移除多余的空白字符和换行
        text = re.sub(r'\s+', ' ', text)
        
        # 移除特殊字符垃圾
        text = re.sub(r'[^\u4e00-\u9fff\u3000-\u303f\uFF00-\uFFEF\w\s.,;:!?(){}[\]"""''—\-]', '', text)
        
        # 移除过多的重复字符
        text = re.sub(r'(.)\1{3,}', r'\1\1', text)
        
        return text.strip()
    
    def detect_content_issues(self, text):
        """检测内容问题"""
        issues = []
        
        # 检查不当内容
        text_lower = text.lower()
        inappropriate_count = sum(1 for keyword in self.inappropriate_keywords if keyword in text_lower)
        if inappropriate_count >= 1:
            issues.append("不当内容")
        
        # 检查日语干扰
        japanese_chars = len(re.findall(r'[\u3040-\u309f\u30a0-\u30ff]', text))
        japanese_ratio = japanese_chars / len(text) if text else 0
        japanese_keyword_count = sum(1 for keyword in self.japanese_keywords if keyword in text)
        
        if japanese_ratio > 0.02 or japanese_keyword_count >= 2:
            issues.append("日语内容")
        
        # 检查韩语
        korean_chars = len(re.findall(r'[\uac00-\ud7af]', text))
        korean_ratio = korean_chars / len(text) if text else 0
        if korean_ratio > 0.02:
            issues.append("韩语内容")
        
        # 检查导航垃圾内容
        nav_count = sum(1 for keyword in self.navigation_keywords if keyword in text)
        if nav_count >= 5 or (nav_count >= 3 and len(text) < 300):
            issues.append("导航垃圾")
        
        # 检查是否主要是简体中文
        simplified = self.converter_t2s.convert(text)
        traditional = self.converter_s2t.convert(text)
        
        diff_from_simplified = sum(1 for a, b in zip(text, simplified) if a != b)
        diff_from_traditional = sum(1 for a, b in zip(text, traditional) if a != b)
        
        if diff_from_traditional > diff_from_simplified:
            issues.append("简体中文")
        
        # 检查中文字符比例
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        chinese_ratio = chinese_chars / len(text) if text else 0
        if chinese_ratio < 0.4:
            issues.append("中文比例低")
        
        return issues, {
            'chinese_ratio': chinese_ratio,
            'japanese_ratio': japanese_ratio,
            'korean_ratio': korean_ratio,
            'nav_count': nav_count,
            'inappropriate_count': inappropriate_count
        }
    
    def is_high_quality_traditional_chinese(self, text, min_ratio=0.05):
        """判断是否为高质量繁体中文"""
        if not text or len(text) < 100:
            return False, 0, {'reason': '文本太短'}
        
        # 清理文本
        cleaned_text = self.clean_text(text)
        if len(cleaned_text) < 50:
            return False, 0, {'reason': '清理后文本太短'}
        
        # 检测内容问题
        issues, stats = self.detect_content_issues(cleaned_text)
        if issues:
            return False, 0, {'reason': f"质量问题: {', '.join(issues)}", **stats}
        
        # 计算繁体字比例
        simplified = self.converter_t2s.convert(cleaned_text)
        diff_from_simplified = sum(1 for a, b in zip(cleaned_text, simplified) if a != b)
        traditional_ratio = diff_from_simplified / len(cleaned_text) if cleaned_text else 0
        
        # 判断是否达到繁体中文标准
        if traditional_ratio < min_ratio:
            return False, traditional_ratio, {'reason': f'繁体字比例太低: {traditional_ratio:.3f}', **stats}
        
        # 计算置信度
        confidence_score = min(1.0, traditional_ratio * 3 + stats['chinese_ratio'] * 0.5)
        
        return True, traditional_ratio, {
            'confidence_score': confidence_score,
            'quality': 'high',
            **stats
        }

    def process_warc_file(self, input_file, output_file, min_ratio=0.05, target_count=100):
        """处理WARC文件，提取高质量繁体中文内容"""
        print(f"开始处理文件: {input_file}")
        print(f"最小繁体字比例: {min_ratio}")
        print(f"目标数量: {target_count}")
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        processed_count = 0
        saved_count = 0
        rejection_reasons = {}
        
        with gzip.open(input_file, 'rt', encoding='utf-8', errors='ignore') as f:
            with open(output_file, 'w', encoding='utf-8') as out_f:
                current_record = {}
                in_content = False
                content_lines = []
                
                for line in f:
                    line = line.strip()
                    
                    # 新记录开始
                    if line.startswith('WARC-Type:'):
                        # 处理前一个记录
                        if current_record and in_content and content_lines:
                            processed_count += 1
                            
                            # 合并内容
                            content = '\n'.join(content_lines)
                            
                            # 检查是否为高质量繁体中文
                            is_quality, trad_ratio, analysis = self.is_high_quality_traditional_chinese(content, min_ratio)
                            
                            if is_quality:
                                saved_count += 1
                                
                                # 构建输出记录
                                output_record = {
                                    'id': current_record.get('id', f'record_{processed_count}'),
                                    'url': current_record.get('url', ''),
                                    'text': content,
                                    'text_length': len(content),
                                    'traditional_ratio': trad_ratio,
                                    'confidence_score': analysis.get('confidence_score', 0),
                                    'chinese_ratio': analysis.get('chinese_ratio', 0),
                                    'is_traditional_chinese': True,
                                    'quality_grade': 'high',
                                    'source_file': os.path.basename(input_file)
                                }
                                
                                out_f.write(json.dumps(output_record, ensure_ascii=False) + '\n')
                                out_f.flush()
                                
                                if saved_count % 5 == 0:
                                    print(f"已保存 {saved_count} 条高质量繁体中文记录")
                                
                                # 达到目标数量则停止
                                if saved_count >= target_count:
                                    print(f"已达到目标数量 {target_count}，停止处理")
                                    break
                            else:
                                # 记录拒绝原因
                                reason = analysis.get('reason', '未知原因')
                                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
                        
                        # 重置状态
                        current_record = {}
                        in_content = False
                        content_lines = []
                        
                        if processed_count % 3000 == 0:
                            print(f"已处理 {processed_count} 条记录，已保存 {saved_count} 条高质量记录")
                    
                    # 记录URL
                    elif line.startswith('WARC-Target-URI:'):
                        current_record['url'] = line.split(':', 1)[1].strip()
                    
                    # 记录ID
                    elif line.startswith('WARC-Record-ID:'):
                        warc_id = line.split(':', 1)[1].strip()
                        current_record['id'] = f"{os.path.basename(input_file)}_{abs(hash(warc_id)) % 10000}"
                    
                    # 内容开始
                    elif line == '' and current_record.get('url'):
                        in_content = True
                    
                    # 收集内容
                    elif in_content and line:
                        content_lines.append(line)
        
        # 输出统计信息
        print("\n" + "="*60)
        print("处理完成！统计信息:")
        print(f"总共处理记录: {processed_count}")
        print(f"保存高质量记录: {saved_count}")
        print(f"拒绝原因统计:")
        for reason, count in sorted(rejection_reasons.items(), key=lambda x: x[1], reverse=True):
            print(f"  - {reason}: {count}")
        if processed_count > 0:
            print(f"质量通过率: {saved_count/processed_count*100:.2f}%")
        print("="*60)
        
        return saved_count

def main():
    processor = AdvancedTraditionalChineseProcessor()
    
    input_file = "fineweb-zhtw/data/WARC/CC-MAIN-2024-26/CC-MAIN-20240612140424-20240612170424-00001.warc.gz"
    output_file = "fineweb-zhtw/data/output_high_quality/clean_traditional_chinese.jsonl"
    
    # 使用较低的繁体字比例要求，但严格的质量过滤
    saved_count = processor.process_warc_file(
        input_file=input_file,
        output_file=output_file,
        min_ratio=0.05,  # 最小繁体字比例5%（比较宽松）
        target_count=100  # 目标100条高质量记录
    )
    
    print(f"\n✅ 成功提取 {saved_count} 条高质量繁体中文内容")
    print(f"📁 输出文件: {output_file}")
    
    # 显示几个样本
    if saved_count > 0:
        print(f"\n📋 样本预览:")
        with open(output_file, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i >= 3:
                    break
                data = json.loads(line)
                print(f"  样本 {i+1}:")
                print(f"    URL: {data['url']}")
                print(f"    繁体比例: {data['traditional_ratio']:.3f}")
                print(f"    中文比例: {data['chinese_ratio']:.3f}")
                print(f"    内容: {data['text'][:150]}...")
                print()

if __name__ == "__main__":
    main()
