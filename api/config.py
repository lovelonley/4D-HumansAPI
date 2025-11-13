"""API 配置管理"""
import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""
    
    # ============================================================
    # 应用基础配置
    # ============================================================
    APP_NAME: str = "4D-Humans MoCap API"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # ============================================================
    # 路径配置
    # ============================================================
    PROJECT_ROOT: Path = Path(__file__).parent.parent
    UPLOAD_DIR: Path = PROJECT_ROOT / "uploads"
    RESULT_DIR: Path = PROJECT_ROOT / "results"
    OUTPUT_DIR: Path = PROJECT_ROOT / "outputs"
    TEMP_DIR: Path = PROJECT_ROOT / "tmp"
    LOG_DIR: Path = PROJECT_ROOT / "logs"
    
    # ============================================================
    # 依赖配置（必需）
    # ============================================================
    # Blender 路径（可选，如果在 PATH 中可不设置）
    BLENDER_PATH: str = ""
    
    # SmoothNet 检查点路径（必需）
    SMOOTHNET_CHECKPOINT: str = "smoothnet/data/checkpoints/pw3d_spin_3D/checkpoint_8.pth.tar"
    
    # ============================================================
    # 业务配置
    # ============================================================
    # 视频限制
    MAX_FILE_SIZE: int = 500 * 1024 * 1024  # 500MB
    MAX_VIDEO_DURATION: int = 30  # 30秒
    MAX_VIDEO_RESOLUTION: int = 2048  # 2K
    ALLOWED_VIDEO_FORMATS: List[str] = [".mp4", ".avi", ".mov", ".mkv"]
    
    # 队列配置
    MAX_QUEUE_SIZE: int = 10
    
    # ============================================================
    # 超时配置（秒）
    # ============================================================
    TASK_TIMEOUT: int = 1200  # 总超时（20分钟）
    TRACKING_TIMEOUT: int = 900  # 追踪超时（15分钟）
    EXTRACTION_TIMEOUT: int = 60  # 提取超时（1分钟）
    SMOOTHING_TIMEOUT: int = 120  # 平滑超时（2分钟）
    FBX_EXPORT_TIMEOUT: int = 120  # 导出超时（2分钟）
    
    # ============================================================
    # 清理配置
    # ============================================================
    AUTO_CLEANUP_ENABLED: bool = True
    CLEANUP_INTERVAL_HOURS: int = 6  # 清理间隔
    CLEANUP_COMPLETED_HOURS: int = 72  # 完成任务保留时间（3天）
    CLEANUP_FAILED_HOURS: int = 72  # 失败任务保留时间（3天）
    
    # 开发/演示文件清理
    CLEANUP_DEMO_FILES_ENABLED: bool = True
    CLEANUP_DEMO_FILES_DAYS: int = 30  # 演示文件保留时间（30天）
    CLEANUP_TEST_FILES_ENABLED: bool = True
    CLEANUP_TEST_FILES_DAYS: int = 7  # 测试文件保留时间（7天）
    CLEANUP_LOG_FILES_DAYS: int = 7  # 日志文件保留时间（7天）
    
    # ============================================================
    # SmoothNet 配置
    # ============================================================
    DEFAULT_SMOOTHING_STRENGTH: float = 1.0
    DEFAULT_SMOOTHING_WINDOW: int = 9
    DEFAULT_SMOOTHING_EMA: float = 0.2
    
    # ============================================================
    # 默认参数
    # ============================================================
    DEFAULT_FPS: int = 30
    DEFAULT_WITH_ROOT_MOTION: bool = True
    DEFAULT_CAM_SCALE: float = 1.0
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# 全局配置实例
settings = Settings()


def ensure_directories():
    """确保所有必要的目录存在"""
    directories = [
        settings.UPLOAD_DIR,
        settings.RESULT_DIR,
        settings.OUTPUT_DIR,
        settings.TEMP_DIR,
        settings.LOG_DIR,
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

