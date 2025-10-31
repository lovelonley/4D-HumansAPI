"""依赖检查工具 - 强制要求所有依赖可用"""
import os
import sys
import subprocess
from pathlib import Path
from typing import Tuple, Optional
from ..config import settings
from ..utils.logger import logger


class DependencyChecker:
    """依赖检查器 - 启动时强制检查"""
    
    @staticmethod
    def check_blender() -> Tuple[bool, Optional[str], Optional[str]]:
        """
        检查 Blender 是否可用
        
        Returns:
            (is_available, blender_path, error_message)
        """
        # 1. 检查配置中的路径
        if settings.BLENDER_PATH:
            blender_path = settings.BLENDER_PATH
            if os.path.isfile(blender_path) and os.access(blender_path, os.X_OK):
                # 验证版本
                is_valid, version, error = DependencyChecker._verify_blender_version(blender_path)
                if is_valid:
                    logger.info(f"✓ Blender found at {blender_path} (version: {version})")
                    return True, blender_path, None
                else:
                    return False, None, error
            else:
                return False, None, f"Blender path in config is invalid: {blender_path}"
        
        # 2. 检查 PATH 中的 blender
        try:
            result = subprocess.run(
                ["which", "blender"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                blender_path = result.stdout.strip()
                is_valid, version, error = DependencyChecker._verify_blender_version(blender_path)
                if is_valid:
                    logger.info(f"✓ Blender found in PATH: {blender_path} (version: {version})")
                    return True, blender_path, None
                else:
                    return False, None, error
        except Exception as e:
            pass
        
        # 3. 检查常见安装位置
        common_paths = [
            "/usr/bin/blender",
            "/usr/local/bin/blender",
            "/Applications/Blender.app/Contents/MacOS/blender",  # macOS
            "C:\\Program Files\\Blender Foundation\\Blender\\blender.exe",  # Windows
        ]
        
        for path in common_paths:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                is_valid, version, error = DependencyChecker._verify_blender_version(path)
                if is_valid:
                    logger.info(f"✓ Blender found at {path} (version: {version})")
                    return True, path, None
        
        # 未找到 Blender
        error_msg = (
            "❌ Blender not found!\n"
            "Please install Blender 3.0+ and ensure it's in PATH, or set BLENDER_PATH in .env\n"
            "Download: https://www.blender.org/download/"
        )
        return False, None, error_msg
    
    @staticmethod
    def _verify_blender_version(blender_path: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        验证 Blender 版本
        
        Returns:
            (is_valid, version, error_message)
        """
        try:
            result = subprocess.run(
                [blender_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return False, None, f"Failed to get Blender version: {result.stderr}"
            
            # 解析版本号（例如：Blender 3.6.0）
            output = result.stdout
            for line in output.split('\n'):
                if 'Blender' in line:
                    parts = line.split()
                    for part in parts:
                        if part[0].isdigit():
                            version = part
                            # 检查版本是否 >= 3.0
                            major_version = int(version.split('.')[0])
                            if major_version >= 3:
                                return True, version, None
                            else:
                                return False, None, (
                                    f"Blender version too old: {version} "
                                    f"(required: 3.0+)"
                                )
            
            return False, None, "Could not parse Blender version"
            
        except subprocess.TimeoutExpired:
            return False, None, "Blender version check timed out"
        except Exception as e:
            return False, None, f"Failed to verify Blender: {str(e)}"
    
    @staticmethod
    def check_smoothnet() -> Tuple[bool, Optional[str]]:
        """
        检查 SmoothNet 是否可用
        
        Returns:
            (is_available, error_message)
        """
        # 1. 检查检查点文件
        checkpoint_path = Path(settings.PROJECT_ROOT) / settings.SMOOTHNET_CHECKPOINT
        
        if not checkpoint_path.exists():
            error_msg = (
                f"❌ SmoothNet checkpoint not found!\n"
                f"Expected path: {checkpoint_path}\n"
                f"Please download the checkpoint or update SMOOTHNET_CHECKPOINT in .env"
            )
            return False, error_msg
        
        logger.info(f"✓ SmoothNet checkpoint found: {checkpoint_path}")
        
        # 2. 尝试导入 SmoothNet 模块
        try:
            # 添加 SmoothNet 到 Python 路径
            smoothnet_dir = Path(settings.PROJECT_ROOT) / "SmoothNet"
            if smoothnet_dir not in sys.path:
                sys.path.insert(0, str(smoothnet_dir))
            
            # 尝试导入
            from lib.models.smoothnet import SmoothNet
            logger.info("✓ SmoothNet module imported successfully")
            
            # 3. 验证检查点文件可读
            try:
                import torch
                checkpoint = torch.load(checkpoint_path, map_location='cpu')
                if 'model_pos' not in checkpoint:
                    return False, f"Invalid checkpoint format: 'model_pos' key not found in {checkpoint_path}"
                
                logger.info("✓ SmoothNet checkpoint validated")
                return True, None
                
            except Exception as e:
                return False, f"Failed to load SmoothNet checkpoint: {str(e)}"
            
        except ImportError as e:
            error_msg = (
                f"❌ Failed to import SmoothNet module!\n"
                f"Error: {str(e)}\n"
                f"Please ensure SmoothNet is properly installed in: {smoothnet_dir}"
            )
            return False, error_msg
        except Exception as e:
            return False, f"Failed to check SmoothNet: {str(e)}"
    
    @staticmethod
    def check_all_dependencies() -> Tuple[bool, list]:
        """
        检查所有依赖
        
        Returns:
            (all_ok, error_messages)
        """
        errors = []
        
        # 检查 Blender
        blender_ok, blender_path, blender_error = DependencyChecker.check_blender()
        if not blender_ok:
            errors.append(f"Blender: {blender_error}")
        else:
            # 更新配置中的 Blender 路径
            settings.BLENDER_PATH = blender_path
        
        # 检查 SmoothNet
        smoothnet_ok, smoothnet_error = DependencyChecker.check_smoothnet()
        if not smoothnet_ok:
            errors.append(f"SmoothNet: {smoothnet_error}")
        
        return len(errors) == 0, errors


def ensure_dependencies():
    """
    确保所有依赖可用，否则退出程序
    
    这个函数应该在应用启动时调用
    """
    logger.info("=" * 60)
    logger.info("Checking dependencies...")
    logger.info("=" * 60)
    
    all_ok, errors = DependencyChecker.check_all_dependencies()
    
    if not all_ok:
        logger.error("=" * 60)
        logger.error("❌ DEPENDENCY CHECK FAILED!")
        logger.error("=" * 60)
        for error in errors:
            logger.error(error)
        logger.error("=" * 60)
        logger.error("Service cannot start without required dependencies.")
        logger.error("Please fix the above errors and try again.")
        logger.error("=" * 60)
        
        # 退出程序
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("✓ All dependencies are available!")
    logger.info("=" * 60)

