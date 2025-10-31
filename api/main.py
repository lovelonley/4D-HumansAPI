"""4D-Humans MoCap API 主应用"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import time

from .config import settings, ensure_directories
from .utils.logger import logger
from .utils.dependency_checker import ensure_dependencies
from .services.worker import get_worker
from .services.task_manager import get_task_manager
from .routers import mocap, admin


# 启动和关闭事件
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动
    logger.info("=" * 60)
    logger.info(f"Starting {settings.APP_NAME} v{settings.VERSION}")
    logger.info("=" * 60)
    
    # ⚠️ 强制检查依赖（SmoothNet + Blender）
    ensure_dependencies()
    
    # 确保目录存在
    ensure_directories()
    
    # 启动后台工作器
    worker = get_worker()
    await worker.start()
    
    # 启动自动清理任务（如果启用）
    cleanup_task = None
    if settings.AUTO_CLEANUP_ENABLED:
        cleanup_task = asyncio.create_task(_auto_cleanup())
    
    logger.info("=" * 60)
    logger.info("✓ Application started successfully")
    logger.info("=" * 60)
    
    yield
    
    # 关闭
    logger.info("Shutting down application")
    
    # 停止工作器
    await worker.stop()
    
    # 停止清理任务
    if cleanup_task:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
    
    logger.info("Application stopped")


async def _auto_cleanup():
    """自动清理过期任务"""
    task_manager = get_task_manager()
    
    while True:
        try:
            await asyncio.sleep(settings.CLEANUP_INTERVAL_HOURS * 3600)
            logger.info("Running auto cleanup")
            cleaned = task_manager.cleanup_old_tasks()
            logger.info(f"Auto cleanup completed: {cleaned} tasks removed")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Auto cleanup error: {e}")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="4D-Humans 视频动作捕捉服务 - 从视频生成 Unity Humanoid FBX 动画",
    lifespan=lifespan
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录请求日志"""
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    
    logger.info(
        f"{request.method} {request.url.path} "
        f"- {response.status_code} "
        f"- {process_time:.3f}s"
    )
    
    return response


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器"""
    logger.exception(f"Unhandled exception: {exc}")
    
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_ERROR",
            "error_message": "服务器内部错误",
            "error_details": str(exc) if settings.DEBUG else None
        }
    )


# 注册路由
app.include_router(mocap.router)
app.include_router(admin.router)


# 根路径
@app.get("/")
async def root():
    """根路径"""
    return {
        "name": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health"
    }


# 简单健康检查（用于负载均衡器）
@app.get("/health")
async def simple_health_check():
    """简单健康检查"""
    from .services.task_manager import get_task_manager
    from .utils.file_handler import FileHandler
    
    task_manager = get_task_manager()
    
    # 获取磁盘使用情况
    total, used, usage_percent = FileHandler.get_disk_usage()
    
    # 判断健康状态
    status = "healthy"
    warnings = []
    
    if usage_percent > 90:
        status = "degraded"
        warnings.append(f"磁盘使用率过高: {usage_percent:.1f}%")
    
    if len(task_manager.queue) >= settings.MAX_QUEUE_SIZE:
        status = "degraded"
        warnings.append("任务队列已满")
    
    response = {
        "status": status,
        "active_tasks": 1 if task_manager.current_task_id else 0,
        "queued_tasks": len(task_manager.queue),
        "disk_usage_percent": round(usage_percent, 2)
    }
    
    if warnings:
        response["warnings"] = warnings
    
    return response


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "api.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )

