# services/pipeline_pool.py
"""Pipeline池管理 - 复用模型实例，避免重复加载"""

import gc
import torch
from typing import Dict, Optional, Tuple
from collections import defaultdict


class PipelinePool:
    """Pipeline池 - 单例模式"""
    
    _instance = None
    _pipelines: Dict[str, Dict] = {}
    _ref_counts: Dict[str, int] = defaultdict(int)
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_pipeline(self, model_path: str, model_name: str = None,
                     lora_path: str = None, lora_weight: float = 1.0,
                     task_id: str = None) -> Tuple[Optional[object], bool]:
        """
        获取Pipeline
        
        参数:
            model_path: 模型路径
            model_name: 模型名称（用于显示）
            lora_path: LoRA路径（可选）
            lora_weight: LoRA权重
            task_id: 任务ID（用于引用计数）
        
        返回:
            (pipeline, is_new)
        """
        if task_id is None:
            task_id = "default"
        
        # 生成缓存键
        cache_key = f"{model_path}_{lora_path}_{lora_weight}"
        
        # 检查缓存
        if cache_key in self._pipelines:
            pipe_data = self._pipelines[cache_key]
            self._ref_counts[task_id] += 1
            pipe_data['ref_count'] += 1
            return pipe_data['pipe'], False
        
        # 加载新Pipeline
        try:
            from diffusers import StableDiffusionPipeline
            
            pipe = StableDiffusionPipeline.from_single_file(
                model_path,
                torch_dtype=torch.float32,
                safety_checker=None,
                requires_safety_checker=False,
                use_safetensors=True,
                low_cpu_mem_usage=True
            )
            pipe.to("cpu")
            pipe.enable_vae_slicing()
            pipe.enable_attention_slicing()
            
            # 加载LoRA
            if lora_path and lora_path != "None":
                try:
                    pipe.load_lora_weights(lora_path)
                    if lora_weight != 1.0:
                        pipe.set_adapters(["default"], adapter_weights=[lora_weight])
                except Exception as e:
                    print(f"⚠️ LoRA加载失败: {e}")
            
            self._pipelines[cache_key] = {
                'pipe': pipe,
                'ref_count': 1,
                'model_path': model_path,
                'lora_path': lora_path,
                'lora_weight': lora_weight,
            }
            self._ref_counts[task_id] += 1
            
            return pipe, True
            
        except Exception as e:
            print(f"❌ Pipeline加载失败: {e}")
            return None, False
    
    def release_pipeline(self, model_path: str, lora_path: str = None,
                         task_id: str = None) -> bool:
        """释放Pipeline引用"""
        if task_id is None:
            task_id = "default"
        
        cache_key = f"{model_path}_{lora_path}"
        
        # 减少任务引用计数
        if task_id in self._ref_counts:
            self._ref_counts[task_id] -= 1
            if self._ref_counts[task_id] <= 0:
                del self._ref_counts[task_id]
        
        # 减少Pipeline引用计数
        if cache_key in self._pipelines:
            self._pipelines[cache_key]['ref_count'] -= 1
            
            # 如果没有引用，释放
            if self._pipelines[cache_key]['ref_count'] <= 0:
                pipe_data = self._pipelines.pop(cache_key)
                try:
                    pipe = pipe_data['pipe']
                    if pipe is not None:
                        del pipe
                except:
                    pass
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                return True
        
        return False
    
    def get_status(self) -> Dict:
        """获取池状态"""
        return {
            'total_pipelines': len(self._pipelines),
            'pipelines': {
                k: {'ref_count': v['ref_count'], 'model': v.get('model_path', '')}
                for k, v in self._pipelines.items()
            },
            'active_tasks': len(self._ref_counts),
        }
    
    def clear(self):
        """清空所有Pipeline"""
        for key, data in list(self._pipelines.items()):
            try:
                pipe = data['pipe']
                if pipe is not None:
                    del pipe
            except:
                pass
        self._pipelines.clear()
        self._ref_counts.clear()
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


# 全局单例
pipeline_pool = PipelinePool()