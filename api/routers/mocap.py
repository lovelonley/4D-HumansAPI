"""MoCap API 路由"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Path as PathParam
from fastapi.responses import FileResponse
from typing import Optional
from pathlib import Path

from ..config import settings
from ..constants import TaskStatus, ErrorCode
from ..models.task import TaskCreate, TaskResponse, TaskListResponse
from ..models.error import ErrorResponse
from ..services.task_manager import get_task_manager
from ..utils.logger import logger
from ..utils.file_handler import FileHandler
from ..utils.video_validator import VideoValidator


router = APIRouter(
    prefix="/api/v1/mocap",
    tags=["mocap"]
)


@router.post(
    "/tasks",
    response_model=TaskResponse,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        503: {"model": ErrorResponse}
    },
    summary="创建动作捕捉任务",
    description="上传视频文件，创建动作捕捉任务。任务将自动排队处理。"
)
async def create_mocap_task(
    video: UploadFile = File(..., description="视频文件"),
    track_id: Optional[int] = Form(None, description="指定提取的人物ID（默认自动选择最长轨迹）"),
    fps: Optional[int] = Form(None, description="输出FPS（默认30）"),
    with_root_motion: Optional[bool] = Form(None, description="是否包含根运动（默认True）"),
    cam_scale: Optional[float] = Form(None, description="相机缩放（默认1.0）"),
    smoothing_strength: Optional[float] = Form(None, description="平滑强度（默认1.0）"),
    smoothing_window: Optional[int] = Form(None, description="平滑窗口大小（默认9）"),
    smoothing_ema: Optional[float] = Form(None, description="相机EMA平滑系数（默认0.2）")
):
    """创建动作捕捉任务"""
    task_manager = get_task_manager()
    
    # 检查队列是否已满
    if task_manager.is_queue_full():
        raise HTTPException(
            status_code=503,
            detail={
                "error_code": ErrorCode.QUEUE_FULL,
                "error_message": f"任务队列已满（最大: {settings.MAX_QUEUE_SIZE}），请稍后再试"
            }
        )
    
    # 验证文件格式
    is_valid, error_msg = FileHandler.validate_file(video.filename)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": ErrorCode.INVALID_FILE_FORMAT,
                "error_message": error_msg
            }
        )
    
    # 读取文件内容以获取大小
    content = await video.read()
    file_size = len(content)
    await video.seek(0)  # 重置文件指针
    
    # 验证文件大小
    is_valid, error_msg = FileHandler.validate_file_size(file_size)
    if not is_valid:
        raise HTTPException(
            status_code=413,
            detail={
                "error_code": ErrorCode.FILE_TOO_LARGE,
                "error_message": error_msg
            }
        )
    
    # 创建任务（先创建以获取 task_id）
    params = TaskCreate(
        track_id=track_id,
        fps=fps,
        with_root_motion=with_root_motion,
        cam_scale=cam_scale,
        smoothing_strength=smoothing_strength,
        smoothing_window=smoothing_window,
        smoothing_ema=smoothing_ema
    )
    
    task = task_manager.create_task(
        video_path="",  # 临时占位
        video_info={},
        params=params
    )
    
    try:
        # 保存上传的视频
        video_path, _ = await FileHandler.save_upload_file(video, task.task_id)
        
        # 验证视频
        is_valid, error_msg, video_info = VideoValidator.validate_video(video_path)
        if not is_valid:
            # P0修复: 确保删除失败任务的视频文件，防止磁盘泄露
            # 删除任务和文件
            task_manager.delete_task(task.task_id)
            # 确保删除视频文件
            if Path(video_path).exists():
                FileHandler.delete_file(video_path)
                logger.info(f"Deleted invalid video file: {video_path}")
            
            # 根据错误类型返回不同的错误码
            if "分辨率" in error_msg:
                error_code = ErrorCode.VIDEO_RESOLUTION_TOO_HIGH
            elif "时长" in error_msg:
                error_code = ErrorCode.VIDEO_TOO_LONG
            else:
                error_code = ErrorCode.INVALID_FILE_FORMAT
            
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": error_code,
                    "error_message": error_msg
                }
            )
        
        # 更新任务信息
        task.video_path = video_path
        task.video_info = video_info
        
        logger.info(f"Created task {task.task_id}: {video.filename}")
        
        # 返回任务信息
        return TaskResponse(
            task_id=task.task_id,
            status=task.status,
            current_step=task.current_step,
            progress=task.progress,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            error_code=task.error_code,
            error_message=task.error_message,
            processing_time=task.processing_time
        )
    
    except HTTPException:
        raise
    except Exception as e:
        # P0修复: 确保删除失败任务的视频文件
        # 删除任务
        task_manager.delete_task(task.task_id)
        # 确保删除视频文件（如果已保存）
        if 'video_path' in locals() and Path(video_path).exists():
            FileHandler.delete_file(video_path)
            logger.info(f"Deleted video file after exception: {video_path}")
        logger.error(f"Failed to create task: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": ErrorCode.INTERNAL_ERROR,
                "error_message": f"创建任务失败: {str(e)}"
            }
        )


@router.get(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    responses={404: {"model": ErrorResponse}},
    summary="查询任务状态",
    description="根据任务ID查询任务状态和进度"
)
async def get_task_status(
    task_id: str = PathParam(..., description="任务ID")
):
    """查询任务状态"""
    task_manager = get_task_manager()
    task = task_manager.get_task(task_id)
    
    if not task:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": ErrorCode.TASK_NOT_FOUND,
                "error_message": f"任务不存在: {task_id}"
            }
        )
    
    # 构建 FBX URL
    fbx_url = None
    if task.status == TaskStatus.COMPLETED and task.fbx_path:
        fbx_url = f"/api/v1/mocap/tasks/{task_id}/download"
    
    return TaskResponse(
        task_id=task.task_id,
        status=task.status,
        current_step=task.current_step,
        progress=task.progress,
        fbx_url=fbx_url,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        error_code=task.error_code,
        error_message=task.error_message,
        processing_time=task.processing_time
    )


@router.get(
    "/tasks/{task_id}/download",
    response_class=FileResponse,
    responses={404: {"model": ErrorResponse}},
    summary="下载FBX文件",
    description="下载任务生成的FBX动画文件"
)
async def download_fbx(
    task_id: str = PathParam(..., description="任务ID")
):
    """下载FBX文件"""
    task_manager = get_task_manager()
    task = task_manager.get_task(task_id)
    
    if not task:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": ErrorCode.TASK_NOT_FOUND,
                "error_message": f"任务不存在: {task_id}"
            }
        )
    
    if task.status != TaskStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "TASK_NOT_COMPLETED",
                "error_message": f"任务尚未完成，当前状态: {task.status}"
            }
        )
    
    if not task.fbx_path or not Path(task.fbx_path).exists():
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "FILE_NOT_FOUND",
                "error_message": "FBX文件不存在"
            }
        )
    
    filename = Path(task.fbx_path).name
    
    return FileResponse(
        path=task.fbx_path,
        filename=filename,
        media_type="application/octet-stream"
    )


@router.delete(
    "/tasks/{task_id}",
    responses={404: {"model": ErrorResponse}},
    summary="删除任务",
    description="删除任务及其相关文件"
)
async def delete_task(
    task_id: str = PathParam(..., description="任务ID"),
    keep_intermediate: bool = False
):
    """删除任务"""
    task_manager = get_task_manager()
    
    success = task_manager.delete_task(task_id, keep_intermediate)
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": ErrorCode.TASK_NOT_FOUND,
                "error_message": f"任务不存在: {task_id}"
            }
        )
    
    return {"message": f"Task {task_id} deleted successfully"}


@router.get(
    "/tasks",
    response_model=TaskListResponse,
    summary="获取任务列表",
    description="获取所有任务的列表"
)
async def list_tasks():
    """获取任务列表"""
    task_manager = get_task_manager()
    tasks = task_manager.get_all_tasks()
    
    task_responses = []
    for task in tasks:
        fbx_url = None
        if task.status == TaskStatus.COMPLETED and task.fbx_path:
            fbx_url = f"/api/v1/mocap/tasks/{task.task_id}/download"
        
        task_responses.append(TaskResponse(
            task_id=task.task_id,
            status=task.status,
            current_step=task.current_step,
            progress=task.progress,
            fbx_url=fbx_url,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            error_code=task.error_code,
            error_message=task.error_message,
            processing_time=task.processing_time
        ))
    
    return TaskListResponse(
        tasks=task_responses,
        total=len(task_responses)
    )

