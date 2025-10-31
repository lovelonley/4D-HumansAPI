"""任务数据模型"""
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    """创建任务请求"""
    # 可选参数
    track_id: Optional[int] = Field(None, description="指定提取的人物ID（默认自动选择最长轨迹）")
    fps: Optional[int] = Field(None, description="输出FPS（默认30）")
    with_root_motion: Optional[bool] = Field(None, description="是否包含根运动（默认True）")
    cam_scale: Optional[float] = Field(None, description="相机缩放（默认1.0）")
    smoothing_strength: Optional[float] = Field(None, description="平滑强度（默认1.0）")
    smoothing_window: Optional[int] = Field(None, description="平滑窗口大小（默认9）")
    smoothing_ema: Optional[float] = Field(None, description="相机EMA平滑系数（默认0.2）")


class Task(BaseModel):
    """任务模型"""
    task_id: str
    status: str  # queued, processing, completed, failed
    current_step: Optional[str] = None
    progress: int = 0  # 0-100
    
    # 文件信息
    video_path: Optional[str] = None
    video_info: Optional[Dict] = None
    
    # 中间文件
    tracking_pkl: Optional[str] = None
    extracted_npz: Optional[str] = None
    smoothed_npz: Optional[str] = None
    
    # 输出文件
    fbx_path: Optional[str] = None
    
    # 任务参数
    params: Optional[TaskCreate] = None
    
    # 时间信息
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # 错误信息
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    error_details: Optional[str] = None
    
    # 统计信息
    processing_time: Optional[float] = None  # 秒
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TaskResponse(BaseModel):
    """任务响应"""
    task_id: str
    status: str
    current_step: Optional[str] = None
    progress: int
    
    # 输出文件
    fbx_url: Optional[str] = None
    
    # 时间信息
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # 错误信息
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    
    # 统计信息
    processing_time: Optional[float] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TaskListResponse(BaseModel):
    """任务列表响应"""
    tasks: List[TaskResponse]
    total: int

