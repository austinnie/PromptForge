# services/image_processor.py
"""图片后处理 - 水印去除、元数据清理、EXIF注入、照片真实化"""

import os
import random
from PIL import Image
import numpy as np
from typing import Optional


class ImageProcessor:
    """图片处理器"""
    
    def __init__(self):
        self.enabled = True
    
    def process(self, filepath: str) -> str:
        """处理图片"""
        if not self.enabled:
            return filepath
        
        try:
            # 1. 检查是否为素描/线稿风格
            is_sketch = self._is_sketch_style(filepath)
            
            # 2. 元数据清理（转换为JPG）
            if not is_sketch:
                filepath = self._clean_metadata(filepath)
            
            # 3. 照片真实化
            if not is_sketch:
                filepath = self._make_realistic(filepath)
            
            return filepath
            
        except Exception as e:
            print(f"⚠️ 图片处理失败: {e}")
            return filepath
    
    def _is_sketch_style(self, filepath: str) -> bool:
        """检测是否为素描风格"""
        sketch_keywords = ['sketch', 'pencil', 'lineart', '素描', '线稿', '白描']
        filename = os.path.basename(filepath).lower()
        return any(kw in filename for kw in sketch_keywords)
    
    def _clean_metadata(self, filepath: str) -> str:
        """清理元数据并转换为JPG"""
        try:
            img = Image.open(filepath).convert('RGB')
            jpg_path = filepath.replace('.png', '.jpg')
            if jpg_path == filepath:
                jpg_path = filepath.rsplit('.', 1)[0] + '.jpg'
            img.save(jpg_path, 'JPEG', quality=92)
            
            # 删除原文件
            if jpg_path != filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass
            
            return jpg_path
            
        except Exception as e:
            print(f"⚠️ 元数据清理失败: {e}")
            return filepath
    
    def _make_realistic(self, filepath: str) -> str:
        """照片真实化处理"""
        try:
            img = Image.open(filepath).convert('RGB')
            arr = np.array(img).astype(np.float32)
            
            # 添加轻微噪点
            noise = np.random.normal(0, 1.5, arr.shape)
            arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
            
            # 轻微锐化
            from PIL import ImageFilter
            img = Image.fromarray(arr)
            img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=50, threshold=3))
            
            img.save(filepath, quality=92)
            return filepath
            
        except Exception as e:
            print(f"⚠️ 照片真实化失败: {e}")
            return filepath