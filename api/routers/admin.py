"""管理 API 路由"""
from fastapi import APIRouter
from ..config import settings
from ..services.task_manager import get_task_manager
from ..utils.file_handler import FileHandler
from ..utils.gpu_monitor import get_gpu_monitor


router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"]
)


@router.get(
    "/health",
    summary="详细健康检查",
    description="获取服务的详细健康状态"
)
async def detailed_health_check():
    """详细健康检查"""
    task_manager = get_task_manager()
    gpu_monitor = get_gpu_monitor()
    
    # 磁盘使用情况
    total, used, usage_percent = FileHandler.get_disk_usage()
    
    # GPU 状态
    gpu_stats = gpu_monitor.get_gpu_stats()
    
    # 队列信息
    queue_info = task_manager.get_queue_info()
    
    # 统计信息
    stats = task_manager.get_stats()
    
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "uptime": stats["uptime"],
        "disk": {
            "total_gb": round(total / (1024**3), 2),
            "used_gb": round(used / (1024**3), 2),
            "usage_percent": round(usage_percent, 2)
        },
        "gpu": gpu_stats,
        "queue": queue_info,
        "stats": stats
    }


@router.get(
    "/stats",
    summary="统计信息",
    description="获取任务处理统计信息"
)
async def get_stats():
    """获取统计信息"""
    task_manager = get_task_manager()
    return task_manager.get_stats()


@router.get(
    "/queue",
    summary="队列信息",
    description="获取任务队列信息"
)
async def get_queue_info():
    """获取队列信息"""
    task_manager = get_task_manager()
    return task_manager.get_queue_info()


@router.post(
    "/cleanup",
    summary="手动清理",
    description="手动触发过期任务和文件清理"
)
async def manual_cleanup():
    """手动清理过期任务和文件"""
    task_manager = get_task_manager()
    
    cleaned_tasks = task_manager.cleanup_old_tasks()
    cleaned_demo = task_manager.cleanup_demo_files()
    cleaned_test = task_manager.cleanup_test_files()
    cleaned_logs = task_manager.cleanup_log_files()
    
    total_cleaned = cleaned_tasks + cleaned_demo + cleaned_test + cleaned_logs
    
    return {
        "message": f"Cleaned up {total_cleaned} items",
        "cleaned_tasks": cleaned_tasks,
        "cleaned_demo_files": cleaned_demo,
        "cleaned_test_files": cleaned_test,
        "cleaned_log_files": cleaned_logs,
        "total_cleaned": total_cleaned
    }

