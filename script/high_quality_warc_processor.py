import gzip
import json
import re
import html
import opencc
from urllib.parse import urlparse
import os

class HighQualityChineseProcessor:
    def __init__(self):
        # 初始化转换器
        self.converter_s2t = opencc.OpenCC('s2t')
        self.converter_t2s = opencc.OpenCC('t2s') 
        
        # 不合适的关键词过滤
        self.inappropriate_keywords = [
            # 成人内容
            'AV', '做爱', '操逼', '色情', '裸体', '性爱', '三级', 'porn', 'sex',
            '无码', '有码', '成人', '情色', '激情', '淫', '骚', '爽',
            # 赌博相关
            '赌', '博彩', '赌场', '彩票', '投注', '下注',
            # 其他不良内容
            '盗版', '破解', '免费下载', '种子', 'torrent'
        ]
        
        # 导航/垃圾内容关键词
        self.navigation_keywords = [
            '首页', '联系我们', '关于我们', '版权所有', 'Copyright', '网站地图', 'sitemap',
            '产品大全', '友情链接', '更多', 'More', '下一页', '上一页', '菜单', 'menu',
            '登录', '注册', '购物车', '搜索结果', '全部分类', '热门推荐', '最新更新',
            '相关推荐', '点击查看', '立即购买', '免费试用', '马上注册'
        ]
        
        # 高质量域名白名单（台湾、香港等繁体中文网站）
        self.quality_domains = [
            'gov.tw', 'edu.tw', 'org.tw', 'com.tw', 'net.tw',
            'gov.hk', 'edu.hk', 'org.hk', 'com.hk', 'net.hk',
            'wikipedia.org', 'wikimedia.org', 'news', 'blog'
        ]
        
        # 低质量域名黑名单
        self.blacklist_domains = [
            'porn', 'xxx', 'sex', 'adult', 'casino', 'bet', 'gamble',
            'download', 'torrent', 'crack', 'hack', 'free-movie',
            'movie-free', 'av', 'jav'
        ]
        
    def clean_text(self, text):
        """深度清理文本"""
        # HTML实体解码
        text = html.unescape(text)
        
        # 移除HTML标签残留
        text = re.sub(r'<[^>]+>', '', text)
        
        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text)
        
        # 移除特殊符号和数字垃圾
        text = re.sub(r'[^\u4e00-\u9fff\u3000-\u303f\uFF00-\uFFEF\w\s.,;:!?(){}[\]"""''—\-]', '', text)
        
        # 移除过多的重复字符
        text = re.sub(r'(.)\1{3,}', r'\1\1', text)
        
        return text.strip()
    
    def is_quality_domain(self, url):
        """检查是否为高质量域名"""
        try:
            domain = urlparse(url).netloc.lower()
            
            # 检查黑名单
            for bad_domain in self.blacklist_domains:
                if bad_domain in domain:
                    return False
            
            # 检查白名单
            for good_domain in self.quality_domains:
                if good_domain in domain:
                    return True
                    
            return False
        except:
            return False
    
    def detect_language_interference(self, text):
        """检测语言干扰"""
        # 检查日语假名
        hiragana_count = len(re.findall(r'[\u3040-\u309f]', text))
        katakana_count = len(re.findall(r'[\u30a0-\u30ff]', text))
        japanese_ratio = (hiragana_count + katakana_count) / len(text) if text else 0
        
        # 检查韩语
        korean_count = len(re.findall(r'[\uac00-\ud7af]', text))
        korean_ratio = korean_count / len(text) if text else 0
        
        # 检查越南语等其他语言特殊字符
        vietnamese_count = len(re.findall(r'[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]', text))
        vietnamese_ratio = vietnamese_count / len(text) if text else 0
        
        return {
            'japanese_ratio': japanese_ratio,
            'korean_ratio': korean_ratio,
            'vietnamese_ratio': vietnamese_ratio,
            'has_interference': japanese_ratio > 0.02 or korean_ratio > 0.02 or vietnamese_ratio > 0.02
        }
    
    def is_traditional_chinese(self, text, min_ratio=0.25):
        """判断是否为高质量繁体中文"""
        if not text or len(text) < 50:
            return False, 0, {}
        
        # 清理文本
        cleaned_text = self.clean_text(text)
        
        # 检查不适宜内容
        text_lower = cleaned_text.lower()
        for keyword in self.inappropriate_keywords:
            if keyword in text_lower:
                return False, 0, {'inappropriate_content': True}
        
        # 检查是否主要是导航内容
        nav_count = sum(1 for keyword in self.navigation_keywords if keyword in cleaned_text)
        if nav_count >= 4:  # 包含4个或以上导航关键词
            return False, 0, {'navigation_content': True}
        
        # 检查语言干扰
        interference = self.detect_language_interference(cleaned_text)
        if interference['has_interference']:
            return False, 0, interference
        
        # 计算中文字符比例
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', cleaned_text))
        chinese_ratio = chinese_chars / len(cleaned_text) if cleaned_text else 0
        
        # 中文字符比例太低
        if chinese_ratio < 0.3:
            return False, 0, {'low_chinese_ratio': chinese_ratio}
        
        # 转换测试
        simplified = self.converter_t2s.convert(cleaned_text)
        traditional = self.converter_s2t.convert(cleaned_text)
        
        # 计算与简体、繁体的差异
        diff_from_simplified = sum(1 for a, b in zip(cleaned_text, simplified) if a != b)
        diff_from_traditional = sum(1 for a, b in zip(cleaned_text, traditional) if a != b)
        
        # 计算繁体字比例
        traditional_ratio = diff_from_simplified / len(cleaned_text) if cleaned_text else 0
        
        # 判断是否为繁体中文
        is_traditional = (
            traditional_ratio >= min_ratio and  # 繁体字比例足够
            diff_from_simplified > diff_from_traditional and  # 更接近繁体
            chinese_ratio >= 0.3  # 中文字符比例足够
        )
        
        confidence_score = min(1.0, traditional_ratio * 2 + chinese_ratio * 0.5)
        
        analysis = {
            'chinese_ratio': chinese_ratio,
            'traditional_ratio': traditional_ratio,
            'confidence_score': confidence_score,
            'diff_from_simplified': diff_from_simplified,
            'diff_from_traditional': diff_from_traditional,
            **interference
        }
        
        return is_traditional, traditional_ratio, analysis

    def process_warc_file(self, input_file, output_file, min_ratio=0.25, target_count=1000):
        """处理WARC文件，提取高质量繁体中文内容"""
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
            'navigation_content': 0,
            'language_interference': 0,
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
                            
                            # 合并内容
                            content = '\n'.join(content_lines)
                            content = self.clean_text(content)
                            
                            if len(content) >= 100:  # 最小长度要求
                                # 检查域名质量
                                url = current_record.get('url', '')
                                domain_quality = self.is_quality_domain(url)
                                
                                # 检查是否为高质量繁体中文
                                is_traditional, trad_ratio, analysis = self.is_traditional_chinese(content, min_ratio)
                                
                                # 记录统计信息
                                if analysis.get('inappropriate_content'):
                                    quality_stats['inappropriate_content'] += 1
                                elif analysis.get('navigation_content'):
                                    quality_stats['navigation_content'] += 1
                                elif analysis.get('has_interference'):
                                    quality_stats['language_interference'] += 1
                                elif analysis.get('low_chinese_ratio', 1) < 0.3:
                                    quality_stats['low_chinese_ratio'] += 1
                                elif trad_ratio < min_ratio:
                                    quality_stats['low_traditional_ratio'] += 1
                                
                                # 如果通过所有质量检查
                                if is_traditional:
                                    quality_stats['high_quality'] += 1
                                    saved_count += 1
                                    
                                    # 构建输出记录
                                    output_record = {
                                        'id': current_record.get('id', f'record_{processed_count}'),
                                        'url': url,
                                        'text': content,
                                        'text_length': len(content),
                                        'traditional_ratio': trad_ratio,
                                        'confidence_score': analysis['confidence_score'],
                                        'chinese_ratio': analysis['chinese_ratio'],
                                        'domain_quality': domain_quality,
                                        'is_traditional_chinese': True,
                                        'source_file': os.path.basename(input_file),
                                        'analysis': analysis
                                    }
                                    
                                    out_f.write(json.dumps(output_record, ensure_ascii=False) + '\n')
                                    out_f.flush()
                                    
                                    if saved_count % 10 == 0:
                                        print(f"已保存 {saved_count} 条高质量繁体中文记录")
                                    
                                    # 达到目标数量则停止
                                    if saved_count >= target_count:
                                        print(f"已达到目标数量 {target_count}，停止处理")
                                        break
                        
                        # 重置状态
                        current_record = {}
                        in_content = False
                        content_lines = []
                        
                        if processed_count % 1000 == 0:
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
        print(f"总共处理记录: {quality_stats['total']}")
        print(f"保存高质量记录: {quality_stats['high_quality']}")
        print(f"过滤原因统计:")
        print(f"  - 不适宜内容: {quality_stats['inappropriate_content']}")
        print(f"  - 导航内容: {quality_stats['navigation_content']}")
        print(f"  - 语言干扰: {quality_stats['language_interference']}")
        print(f"  - 中文比例过低: {quality_stats['low_chinese_ratio']}")
        print(f"  - 繁体字比例过低: {quality_stats['low_traditional_ratio']}")
        print(f"质量通过率: {quality_stats['high_quality']/quality_stats['total']*100:.2f}%")
        print("="*60)
        
        return saved_count

def main():
    processor = HighQualityChineseProcessor()
    
    input_file = "fineweb-zhtw/data/WARC/CC-MAIN-2024-26/CC-MAIN-20240612140424-20240612170424-00001.warc.gz"
    output_file = "fineweb-zhtw/data/output_high_quality/traditional_chinese_CC-MAIN-20240612140424-20240612170424-00001.warc.jsonl"
    
    # 使用更严格的标准：最小繁体字比例0.25，目标500条高质量记录
    saved_count = processor.process_warc_file(
        input_file=input_file,
        output_file=output_file,
        min_ratio=0.25,  # 最小繁体字比例25%
        target_count=500  # 目标500条高质量记录
    )
    
    print(f"\n✅ 成功提取 {saved_count} 条高质量繁体中文内容")
    print(f"📁 输出文件: {output_file}")

if __name__ == "__main__":
    main()
