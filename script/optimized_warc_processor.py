import gzip
import json
import re
import html
import opencc
from urllib.parse import urlparse
import os

class OptimizedChineseProcessor:
    def __init__(self):
        # 初始化转换器
        self.converter_s2t = opencc.OpenCC('s2t')
        self.converter_t2s = opencc.OpenCC('t2s') 
        
        # 严格的成人内容过滤
        self.inappropriate_keywords = [
            'AV', '做爱', '操逼', '色情', '裸体', '性爱', '三级', 'porn', 'sex',
            '无码', '有码', '成人', '情色', '激情', '淫', '骚', '爽', '18+',
            '赌', '博彩', '赌场', '投注', '下注'
        ]
        
        # 简化的导航检测
        self.heavy_navigation_keywords = [
            '搜索结果', '产品大全', '全部分类', '购物车', '立即购买', '免费试用',
            '马上注册', '点击查看', '相关推荐', '热门推荐', '最新更新'
        ]
        
    def clean_text(self, text):
        """基础文本清理"""
        # HTML实体解码
        text = html.unescape(text)
        
        # 移除HTML标签残留
        text = re.sub(r'<[^>]+>', '', text)
        
        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text)
        
        # 移除特殊符号垃圾
        text = re.sub(r'[^\u4e00-\u9fff\u3000-\u303f\uFF00-\uFFEF\w\s.,;:!?(){}[\]"""''—\-]', '', text)
        
        return text.strip()
    
    def detect_language_interference(self, text):
        """检测严重的语言干扰"""
        # 只检测严重干扰
        japanese_count = len(re.findall(r'[\u3040-\u309f\u30a0-\u30ff]', text))
        korean_count = len(re.findall(r'[\uac00-\ud7af]', text))
        
        japanese_ratio = japanese_count / len(text) if text else 0
        korean_ratio = korean_count / len(text) if text else 0
        
        # 只有当干扰比例很高时才拒绝
        has_severe_interference = japanese_ratio > 0.1 or korean_ratio > 0.1
        
        return {
            'japanese_ratio': japanese_ratio,
            'korean_ratio': korean_ratio,
            'has_severe_interference': has_severe_interference
        }
    
    def is_traditional_chinese(self, text, min_ratio=0.15):
        """放宽的繁体中文判断标准"""
        if not text or len(text) < 30:  # 降低最小长度要求
            return False, 0, {}
        
        # 清理文本
        cleaned_text = self.clean_text(text)
        
        # 检查严重不适宜内容
        text_lower = cleaned_text.lower()
        inappropriate_count = sum(1 for keyword in self.inappropriate_keywords if keyword in text_lower)
        if inappropriate_count >= 2:  # 只有包含多个不当词汇才拒绝
            return False, 0, {'inappropriate_content': True}
        
        # 检查是否主要是导航内容（更严格的标准）
        nav_count = sum(1 for keyword in self.heavy_navigation_keywords if keyword in cleaned_text)
        if nav_count >= 3 and len(cleaned_text) < 200:  # 短文本且大量导航
            return False, 0, {'heavy_navigation': True}
        
        # 检查严重语言干扰
        interference = self.detect_language_interference(cleaned_text)
        if interference['has_severe_interference']:
            return False, 0, interference
        
        # 计算中文字符比例（放宽标准）
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', cleaned_text))
        chinese_ratio = chinese_chars / len(cleaned_text) if cleaned_text else 0
        
        # 中文字符比例要求降低
        if chinese_ratio < 0.2:
            return False, 0, {'low_chinese_ratio': chinese_ratio}
        
        # 转换测试
        simplified = self.converter_t2s.convert(cleaned_text)
        traditional = self.converter_s2t.convert(cleaned_text)
        
        # 计算差异
        diff_from_simplified = sum(1 for a, b in zip(cleaned_text, simplified) if a != b)
        diff_from_traditional = sum(1 for a, b in zip(cleaned_text, traditional) if a != b)
        
        # 计算繁体字比例
        traditional_ratio = diff_from_simplified / len(cleaned_text) if cleaned_text else 0
        
        # 更灵活的判断标准
        is_traditional = (
            traditional_ratio >= min_ratio and  # 降低繁体字比例要求
            diff_from_simplified >= diff_from_traditional and  # 更接近繁体
            chinese_ratio >= 0.2  # 降低中文字符比例要求
        )
        
        confidence_score = min(1.0, traditional_ratio * 1.5 + chinese_ratio * 0.8)
        
        analysis = {
            'chinese_ratio': chinese_ratio,
            'traditional_ratio': traditional_ratio,
            'confidence_score': confidence_score,
            'diff_from_simplified': diff_from_simplified,
            'diff_from_traditional': diff_from_traditional,
            **interference
        }
        
        return is_traditional, traditional_ratio, analysis

    def process_warc_file(self, input_file, output_file, min_ratio=0.15, target_count=200):
        """处理WARC文件，使用优化的标准"""
        print(f"开始处理文件: {input_file}")
        print(f"最小繁体字比例: {min_ratio}")
        print(f"目标数量: {target_count}")
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        processed_count = 0
        saved_count = 0
        quality_stats = {
            'total': 0,
            'inappropriate_content': 0,
            'heavy_navigation': 0,
            'severe_interference': 0,
            'low_chinese_ratio': 0,
            'low_traditional_ratio': 0,
            'high_quality': 0
        }
        
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
                            quality_stats['total'] += 1
                            
                            # 合并内容，限制长度以提高处理速度
                            content = '\n'.join(content_lines[:100])  # 只取前100行
                            content = self.clean_text(content)
                            
                            if len(content) >= 50:  # 降低最小长度要求
                                # 检查是否为优质繁体中文
                                is_traditional, trad_ratio, analysis = self.is_traditional_chinese(content, min_ratio)
                                
                                # 记录统计信息
                                if analysis.get('inappropriate_content'):
                                    quality_stats['inappropriate_content'] += 1
                                elif analysis.get('heavy_navigation'):
                                    quality_stats['heavy_navigation'] += 1
                                elif analysis.get('has_severe_interference'):
                                    quality_stats['severe_interference'] += 1
                                elif analysis.get('low_chinese_ratio', 1) < 0.2:
                                    quality_stats['low_chinese_ratio'] += 1
                                elif trad_ratio < min_ratio:
                                    quality_stats['low_traditional_ratio'] += 1
                                
                                # 如果通过质量检查
                                if is_traditional:
                                    quality_stats['high_quality'] += 1
                                    saved_count += 1
                                    
                                    # 构建输出记录
                                    output_record = {
                                        'id': current_record.get('id', f'record_{processed_count}'),
                                        'url': current_record.get('url', ''),
                                        'text': content,
                                        'text_length': len(content),
                                        'traditional_ratio': trad_ratio,
                                        'confidence_score': analysis['confidence_score'],
                                        'chinese_ratio': analysis['chinese_ratio'],
                                        'is_traditional_chinese': True,
                                        'source_file': os.path.basename(input_file)
                                    }
                                    
                                    out_f.write(json.dumps(output_record, ensure_ascii=False) + '\n')
                                    out_f.flush()
                                    
                                    if saved_count % 5 == 0:
                                        print(f"已保存 {saved_count} 条优质繁体中文记录")
                                    
                                    # 达到目标数量则停止
                                    if saved_count >= target_count:
                                        print(f"已达到目标数量 {target_count}，停止处理")
                                        break
                        
                        # 重置状态
                        current_record = {}
                        in_content = False
                        content_lines = []
                        
                        if processed_count % 2000 == 0:
                            print(f"已处理 {processed_count} 条记录，已保存 {saved_count} 条优质记录")
                    
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
                    
                    # 收集内容（限制行数）
                    elif in_content and line and len(content_lines) < 100:
                        content_lines.append(line)
        
        # 输出统计信息
        print("\n" + "="*60)
        print("处理完成！统计信息:")
        print(f"总共处理记录: {quality_stats['total']}")
        print(f"保存优质记录: {quality_stats['high_quality']}")
        print(f"过滤原因统计:")
        print(f"  - 不适宜内容: {quality_stats['inappropriate_content']}")
        print(f"  - 重度导航内容: {quality_stats['heavy_navigation']}")
        print(f"  - 严重语言干扰: {quality_stats['severe_interference']}")
        print(f"  - 中文比例过低: {quality_stats['low_chinese_ratio']}")
        print(f"  - 繁体字比例过低: {quality_stats['low_traditional_ratio']}")
        if quality_stats['total'] > 0:
            print(f"质量通过率: {quality_stats['high_quality']/quality_stats['total']*100:.2f}%")
        print("="*60)
        
        return saved_count

def main():
    processor = OptimizedChineseProcessor()
    
    input_file = "fineweb-zhtw/data/WARC/CC-MAIN-2024-26/CC-MAIN-20240612140424-20240612170424-00001.warc.gz"
    output_file = "fineweb-zhtw/data/output_high_quality/optimized_traditional_chinese_CC-MAIN-20240612140424-20240612170424-00001.warc.jsonl"
    
    # 使用更宽松但仍有质量保证的标准
    saved_count = processor.process_warc_file(
        input_file=input_file,
        output_file=output_file,
        min_ratio=0.15,  # 降低最小繁体字比例到15%
        target_count=200  # 目标200条记录
    )
    
    print(f"\n✅ 成功提取 {saved_count} 条优质繁体中文内容")
    print(f"📁 输出文件: {output_file}")

if __name__ == "__main__":
    main()
