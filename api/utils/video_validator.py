"""视频验证工具"""
import cv2
from pathlib import Path
from typing import Tuple, Optional, Dict
from ..config import settings
from ..utils.logger import logger


class VideoValidator:
    """视频验证器"""
    
    @staticmethod
    def validate_video(video_path: str) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        验证视频文件
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            (is_valid, error_message, video_info)
            video_info = {
                "width": int,
                "height": int,
                "fps": float,
                "frame_count": int,
                "duration": float,  # 秒
            }
        """
        try:
            # 打开视频
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                return False, "无法打开视频文件", None
            
            # 获取视频信息
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # 计算时长
            if fps > 0:
                duration = frame_count / fps
            else:
                return False, "无法获取视频帧率", None
            
            video_info = {
                "width": width,
                "height": height,
                "fps": fps,
                "frame_count": frame_count,
                "duration": duration,
            }
            
            cap.release()
            
            # 验证分辨率
            max_resolution = max(width, height)
            if max_resolution > settings.MAX_VIDEO_RESOLUTION:
                return False, (
                    f"视频分辨率过高: {width}x{height} "
                    f"(最大边长: {settings.MAX_VIDEO_RESOLUTION})"
                ), video_info
            
            # 验证时长
            if duration > settings.MAX_VIDEO_DURATION:
                return False, (
                    f"视频时长过长: {duration:.2f}秒 "
                    f"(最大: {settings.MAX_VIDEO_DURATION}秒)"
                ), video_info
            
            # 验证帧数（至少需要 10 帧）
            if frame_count < 10:
                return False, f"视频帧数过少: {frame_count}帧（至少需要 10 帧）", video_info
            
            logger.info(
                f"Video validated: {width}x{height}, {fps:.2f}fps, "
                f"{frame_count} frames, {duration:.2f}s"
            )
            
            return True, None, video_info
            
        except Exception as e:
            logger.error(f"Failed to validate video: {e}")
            return False, f"视频验证失败: {str(e)}", None
    
    @staticmethod
    def get_video_thumbnail(video_path: str, output_path: str, frame_index: int = 0) -> bool:
        """
        提取视频缩略图
        
        Args:
            video_path: 视频文件路径
            output_path: 输出图片路径
            frame_index: 帧索引（默认第一帧）
            
        Returns:
            是否成功
        """
        try:
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                return False
            
            # 跳到指定帧
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            
            # 读取帧
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                return False
            
            # 保存缩略图
            cv2.imwrite(output_path, frame)
            logger.info(f"Saved thumbnail: {output_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to extract thumbnail: {e}")
            return False

