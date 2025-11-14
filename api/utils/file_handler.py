"""文件处理工具"""
import os
import shutil
from pathlib import Path
from typing import Optional, Tuple
from fastapi import UploadFile
from ..config import settings
from ..utils.logger import logger


class FileHandler:
    """文件处理器"""
    
    @staticmethod
    async def save_upload_file(
        file: UploadFile,
        task_id: str
    ) -> Tuple[str, int]:
        """
        保存上传的文件
        
        Args:
            file: 上传的文件
            task_id: 任务ID
            
        Returns:
            (file_path, file_size)
        """
        # P1修复: 文件名安全性验证
        import re
        filename = file.filename or ""
        # 验证文件名格式（只允许字母、数字、点、下划线、连字符）
        if not re.match(r'^[a-zA-Z0-9._-]+$', filename):
            raise ValueError(f"Invalid filename format: {filename}")
        
        file_ext = Path(filename).suffix.lower()
        file_path = Path(settings.UPLOAD_DIR) / f"{task_id}{file_ext}"
        
        try:
            # P0修复: 流式读取文件，防止大文件导致内存溢出
            # P1修复: 使用配置中的块大小
            file_size = 0
            chunk_size = settings.FILE_UPLOAD_CHUNK_SIZE
            
            # 确保目录存在
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # P1修复: 改进磁盘空间检查，减少竞态条件
            # 先检查磁盘空间（基于文件大小限制估算）
            stat = shutil.disk_usage(settings.UPLOAD_DIR)
            estimated_required_space = settings.MAX_FILE_SIZE * settings.DISK_SPACE_MULTIPLIER
            available_space = stat.free
            
            if available_space < estimated_required_space:
                required_mb = estimated_required_space / (1024 * 1024)
                available_mb = available_space / (1024 * 1024)
                raise IOError(
                    f"磁盘空间不足。需要至少: {required_mb:.2f}MB, "
                    f"可用: {available_mb:.2f}MB"
                )
            
            # 流式读取并写入文件
            with open(file_path, "wb") as f:
                while True:
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break
                    
                    # P1修复: 写入前再次检查磁盘空间（减少竞态条件）
                    stat = shutil.disk_usage(settings.UPLOAD_DIR)
                    if stat.free < chunk_size:
                        f.close()
                        file_path.unlink()
                        raise IOError("磁盘空间不足，写入过程中空间耗尽")
                    
                    f.write(chunk)
                    file_size += len(chunk)
                    
                    # 检查文件大小限制
                    if file_size > settings.MAX_FILE_SIZE:
                        # 删除已写入的文件
                        f.close()
                        file_path.unlink()
                        raise IOError(
                            f"文件过大: {file_size / (1024*1024):.2f}MB "
                            f"(最大: {settings.MAX_FILE_SIZE / (1024*1024):.2f}MB)"
                        )
            
            # P1修复: 写入后最终检查磁盘空间（基于实际文件大小）
            stat = shutil.disk_usage(settings.UPLOAD_DIR)
            required_space = file_size * settings.DISK_SPACE_MULTIPLIER
            available_space = stat.free
            
            if available_space < required_space:
                required_mb = required_space / (1024 * 1024)
                available_mb = available_space / (1024 * 1024)
                # 删除已写入的文件
                if file_path.exists():
                    file_path.unlink()
                raise IOError(
                    f"磁盘空间不足。需要: {required_mb:.2f}MB, "
                    f"可用: {available_mb:.2f}MB"
                )
            
            logger.info(f"Saved upload file: {file_path} ({file_size} bytes)")
            return str(file_path), file_size
            
        except Exception as e:
            logger.error(f"Failed to save upload file: {e}")
            raise
    
    @staticmethod
    def validate_file(filename: str) -> Tuple[bool, Optional[str]]:
        """
        验证文件格式
        
        Args:
            filename: 文件名
            
        Returns:
            (is_valid, error_message)
        """
        file_ext = Path(filename).suffix.lower()
        
        if not file_ext:
            return False, "文件没有扩展名"
        
        if file_ext not in settings.ALLOWED_VIDEO_FORMATS:
            allowed = ", ".join(settings.ALLOWED_VIDEO_FORMATS)
            return False, f"不支持的文件格式: {file_ext}。支持的格式: {allowed}"
        
        return True, None
    
    @staticmethod
    def validate_file_size(file_size: int) -> Tuple[bool, Optional[str]]:
        """
        验证文件大小
        
        Args:
            file_size: 文件大小（bytes）
            
        Returns:
            (is_valid, error_message)
        """
        if file_size > settings.MAX_FILE_SIZE:
            max_mb = settings.MAX_FILE_SIZE / (1024 * 1024)
            current_mb = file_size / (1024 * 1024)
            return False, f"文件过大: {current_mb:.2f}MB，最大允许: {max_mb:.2f}MB"
        
        return True, None
    
    @staticmethod
    def delete_file(file_path: str) -> bool:
        """
        删除文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            是否成功
        """
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                logger.info(f"Deleted file: {file_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            return False
    
    @staticmethod
    def delete_task_files(task_id: str, file_paths: list) -> int:
        """
        删除任务相关的所有文件
        
        Args:
            task_id: 任务ID
            file_paths: 文件路径列表
            
        Returns:
            删除的文件数
        """
        deleted_count = 0
        
        # 删除指定的文件
        for file_path in file_paths:
            if file_path and FileHandler.delete_file(file_path):
                deleted_count += 1
        
                # 如果是 FBX 文件，同时删除对应的 .fbm 文件夹
                if file_path.endswith('.fbx'):
                    fbm_dir = Path(file_path).parent / f"{Path(file_path).stem}.fbm"
                    if fbm_dir.exists() and fbm_dir.is_dir():
                        try:
                            shutil.rmtree(fbm_dir)
                            logger.info(f"Deleted .fbm directory: {fbm_dir}")
                            deleted_count += 1
                        except Exception as e:
                            logger.error(f"Failed to delete .fbm directory {fbm_dir}: {e}")
        
        # 删除临时文件（通过 task_id 匹配）
        temp_dir = Path(settings.TEMP_DIR)
        if temp_dir.exists():
            for temp_file in temp_dir.glob(f"{task_id}*"):
                if temp_file.is_file() and FileHandler.delete_file(str(temp_file)):
                    deleted_count += 1
                elif temp_file.is_dir():
                    # 删除目录（如 .fbm 文件夹）
                    try:
                        shutil.rmtree(temp_file)
                        logger.info(f"Deleted directory: {temp_file}")
                        deleted_count += 1
                    except Exception as e:
                        logger.error(f"Failed to delete directory {temp_file}: {e}")
        
        logger.info(f"Deleted {deleted_count} files/directories for task {task_id}")
        return deleted_count
    
    @staticmethod
    def get_file_size(file_path: str) -> Optional[int]:
        """
        获取文件大小
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件大小（bytes），文件不存在返回 None
        """
        try:
            path = Path(file_path)
            if path.exists():
                return path.stat().st_size
            return None
        except Exception as e:
            logger.error(f"Failed to get file size for {file_path}: {e}")
            return None
    
    @staticmethod
    def get_disk_usage() -> Tuple[int, int, float]:
        """
        获取磁盘使用情况
        
        Returns:
            (total_bytes, used_bytes, usage_percentage)
        """
        try:
            stat = shutil.disk_usage(settings.RESULT_DIR)
            usage_percentage = (stat.used / stat.total) * 100
            return stat.total, stat.used, usage_percentage
        except Exception as e:
            logger.error(f"Failed to get disk usage: {e}")
            return 0, 0, 0.0

