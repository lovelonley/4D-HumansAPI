"""后台任务处理器"""
import asyncio
from typing import Optional
from ..config import settings
from ..constants import ProcessStep
from ..utils.logger import logger
from ..services.task_manager import get_task_manager
from ..services.pipeline import FourDHumansPipeline


class Worker:
    """后台任务处理器（单例）"""
    
    def __init__(self):
        self.task_manager = get_task_manager()
        self.pipeline = FourDHumansPipeline()
        self.running = False
        self.task: Optional[asyncio.Task] = None
    
    async def start(self):
        """启动工作器"""
        if self.running:
            return
        
        self.running = True
        self.task = asyncio.create_task(self._process_loop())
        logger.info("Worker started")
    
    async def stop(self):
        """停止工作器"""
        if not self.running:
            return
        
        self.running = False
        
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        
        logger.info("Worker stopped")
    
    async def _process_loop(self):
        """处理循环"""
        while self.running:
            try:
                # 获取下一个任务
                task = self.task_manager.get_next_task()
                
                if task:
                    # 处理任务
                    await self._process_task(task.task_id)
                else:
                    # 没有任务，等待
                    await asyncio.sleep(1)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker error: {e}", exc_info=True)
                await asyncio.sleep(5)
    
    async def _process_task(self, task_id: str):
        """
        处理单个任务
        
        Args:
            task_id: 任务ID
        """
        task = self.task_manager.get_task(task_id)
        if not task:
            return
        
        logger.info(f"Processing task {task_id}")
        
        try:
            # 进度回调
            def progress_callback(progress: int):
                # 根据进度推断当前步骤
                if progress < 30:
                    step = ProcessStep.TRACKING
                elif progress < 45:
                    step = ProcessStep.TRACK_EXTRACTION
                elif progress < 70:
                    step = ProcessStep.SMOOTHING
                elif progress < 95:
                    step = ProcessStep.FBX_EXPORT
                else:
                    step = ProcessStep.PACKAGING
                
                self.task_manager.update_task_step(task_id, step, progress)
            
            # 获取参数
            params = task.params or {}
            track_id = params.track_id if params else None
            fps = params.fps if params and params.fps else settings.DEFAULT_FPS
            with_root_motion = params.with_root_motion if params and params.with_root_motion is not None else settings.DEFAULT_WITH_ROOT_MOTION
            cam_scale = params.cam_scale if params and params.cam_scale else settings.DEFAULT_CAM_SCALE
            smoothing_strength = params.smoothing_strength if params and params.smoothing_strength else settings.DEFAULT_SMOOTHING_STRENGTH
            smoothing_window = params.smoothing_window if params and params.smoothing_window else settings.DEFAULT_SMOOTHING_WINDOW
            smoothing_ema = params.smoothing_ema if params and params.smoothing_ema else settings.DEFAULT_SMOOTHING_EMA
            
            # 运行 Pipeline（在线程池中运行，避免阻塞事件循环）
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self.pipeline.run_full_pipeline,
                task.video_path,
                task_id,
                track_id,
                fps,
                with_root_motion,
                cam_scale,
                smoothing_strength,
                smoothing_window,
                smoothing_ema,
                progress_callback
            )
            
            if result["success"]:
                # 任务成功
                self.task_manager.complete_task(
                    task_id=task_id,
                    fbx_path=result["fbx_path"],
                    tracking_pkl=result.get("tracking_pkl"),
                    extracted_npz=result.get("extracted_npz"),
                    smoothed_npz=result.get("smoothed_npz")
                )
            else:
                # 任务失败
                self.task_manager.fail_task(
                    task_id=task_id,
                    error_message=result.get("error", "Unknown error"),
                    error_code=result.get("error_code", "INTERNAL_ERROR"),
                    error_details=f"Failed at step: {result.get('error_step', 'unknown')}"
                )
        
        except Exception as e:
            logger.error(f"Task {task_id} failed with exception: {e}", exc_info=True)
            self.task_manager.fail_task(
                task_id=task_id,
                error_message=str(e),
                error_code="INTERNAL_ERROR",
                error_details=None
            )


# 全局 Worker 实例
_worker_instance = None


def get_worker() -> Worker:
    """获取 Worker 单例"""
    global _worker_instance
    if _worker_instance is None:
        _worker_instance = Worker()
    return _worker_instance

