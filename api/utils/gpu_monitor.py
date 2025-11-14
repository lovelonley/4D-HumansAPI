"""GPU 监控工具"""
from typing import Optional, Dict
from ..utils.logger import logger


class GPUMonitor:
    """GPU 监控器"""
    
    def __init__(self):
        self.pynvml = None
        self.initialized = False
        self._init_pynvml()
    
    def _init_pynvml(self):
        """初始化 pynvml"""
        try:
            import py3nvml.py3nvml as pynvml
            self.pynvml = pynvml
            self.pynvml.nvmlInit()
            self.initialized = True
            logger.info("GPU monitoring initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize GPU monitoring: {e}")
            self.initialized = False
    
    def get_gpu_stats(self, device_id: int = 0) -> Optional[Dict]:
        """
        获取 GPU 统计信息
        
        Args:
            device_id: GPU 设备ID（默认0）
            
        Returns:
            {
                "name": str,
                "utilization": int,  # %
                "memory_total": int,  # MB
                "memory_used": int,  # MB
                "memory_free": int,  # MB
                "temperature": int,  # °C
            }
        """
        if not self.initialized:
            return None
        
        try:
            handle = self.pynvml.nvmlDeviceGetHandleByIndex(device_id)
            
            # GPU 名称
            name = self.pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode('utf-8')
            
            # GPU 利用率
            utilization = self.pynvml.nvmlDeviceGetUtilizationRates(handle)
            gpu_util = utilization.gpu
            
            # 显存信息
            memory = self.pynvml.nvmlDeviceGetMemoryInfo(handle)
            memory_total = memory.total // (1024 * 1024)  # 转换为 MB
            memory_used = memory.used // (1024 * 1024)
            memory_free = memory.free // (1024 * 1024)
            
            # 温度
            temperature = self.pynvml.nvmlDeviceGetTemperature(
                handle,
                self.pynvml.NVML_TEMPERATURE_GPU
            )
            
            return {
                "name": name,
                "utilization": gpu_util,
                "memory_total": memory_total,
                "memory_used": memory_used,
                "memory_free": memory_free,
                "temperature": temperature,
            }
            
        except Exception as e:
            logger.error(f"Failed to get GPU stats: {e}")
            return None
    
    def check_gpu_available(self) -> bool:
        """检查 GPU 是否可用"""
        stats = self.get_gpu_stats()
        if not stats:
            return False
        
        # P1修复: 使用配置中的阈值
        from ..config import settings
        
        # 检查显存是否充足
        if stats["memory_free"] < settings.GPU_MIN_FREE_MEMORY_MB:
            logger.warning(f"GPU memory low: {stats['memory_free']}MB free (min: {settings.GPU_MIN_FREE_MEMORY_MB}MB)")
            return False
        
        # 检查温度是否正常
        if stats["temperature"] > settings.GPU_MAX_TEMPERATURE:
            logger.warning(f"GPU temperature high: {stats['temperature']}°C (max: {settings.GPU_MAX_TEMPERATURE}°C)")
            return False
        
        return True
    
    def shutdown(self):
        """关闭 GPU 监控"""
        if self.initialized and self.pynvml:
            try:
                self.pynvml.nvmlShutdown()
                logger.info("GPU monitoring shutdown")
            except Exception as e:
                logger.error(f"Failed to shutdown GPU monitoring: {e}")


# 全局 GPU 监控实例
_gpu_monitor_instance = None


def get_gpu_monitor() -> GPUMonitor:
    """获取 GPU 监控单例"""
    global _gpu_monitor_instance
    if _gpu_monitor_instance is None:
        _gpu_monitor_instance = GPUMonitor()
    return _gpu_monitor_instance

