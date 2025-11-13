"""任务管理系统"""
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import deque
from ..config import settings
from ..constants import TaskStatus, ProcessStep, PROCESS_STEPS, STEP_ESTIMATED_TIME
from ..models.task import Task, TaskCreate
from ..utils.logger import logger
from ..utils.file_handler import FileHandler


class TaskManager:
    """任务管理器（单例）"""
    
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.queue: deque = deque()
        self.current_task_id: Optional[str] = None
        self.start_time = datetime.now()
        
        # 统计信息
        self.total_tasks = 0
        self.completed_tasks = 0
        self.failed_tasks = 0
    
    def create_task(
        self,
        video_path: str,
        video_info: Dict,
        params: Optional[TaskCreate] = None
    ) -> Task:
        """创建新任务"""
        task_id = str(uuid.uuid4())
        
        task = Task(
            task_id=task_id,
            status=TaskStatus.QUEUED,
            progress=0,
            video_path=video_path,
            video_info=video_info,
            params=params,
            created_at=datetime.now()
        )
        
        self.tasks[task_id] = task
        self.queue.append(task_id)
        self.total_tasks += 1
        
        logger.info(f"Created task {task_id}")
        return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self.tasks.get(task_id)
    
    def get_queue_position(self, task_id: str) -> Optional[int]:
        """获取任务在队列中的位置"""
        try:
            return list(self.queue).index(task_id) + 1
        except ValueError:
            return None
    
    def is_queue_full(self) -> bool:
        """检查队列是否已满"""
        return len(self.queue) >= settings.MAX_QUEUE_SIZE
    
    def has_processing_task(self) -> bool:
        """是否有正在处理的任务"""
        return self.current_task_id is not None
    
    def get_next_task(self) -> Optional[Task]:
        """获取下一个待处理任务"""
        if not self.queue or self.current_task_id:
            return None
        
        task_id = self.queue.popleft()
        task = self.tasks.get(task_id)
        
        if task:
            self.current_task_id = task_id
            task.status = TaskStatus.PROCESSING
            task.started_at = datetime.now()
            logger.info(f"Started processing task {task_id}")
        
        return task
    
    def update_task_step(
        self,
        task_id: str,
        step: str,
        progress: int
    ):
        """更新任务步骤"""
        task = self.get_task(task_id)
        if not task:
            return
        
        task.current_step = step
        task.progress = progress
        
        logger.debug(f"Task {task_id} - Step: {step}, Progress: {progress}%")
    
    def complete_task(
        self,
        task_id: str,
        fbx_path: str,
        tracking_pkl: Optional[str] = None,
        extracted_npz: Optional[str] = None,
        smoothed_npz: Optional[str] = None
    ):
        """完成任务"""
        task = self.get_task(task_id)
        if not task:
            return
        
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now()
        task.fbx_path = fbx_path
        task.tracking_pkl = tracking_pkl
        task.extracted_npz = extracted_npz
        task.smoothed_npz = smoothed_npz
        task.progress = 100
        
        # 计算处理时间
        if task.started_at:
            task.processing_time = (task.completed_at - task.started_at).total_seconds()
        
        self.current_task_id = None
        self.completed_tasks += 1
        
        logger.info(f"Completed task {task_id} in {task.processing_time:.2f}s")
    
    def fail_task(
        self,
        task_id: str,
        error_message: str,
        error_code: str,
        error_details: Optional[str] = None
    ):
        """任务失败"""
        task = self.get_task(task_id)
        if not task:
            return
        
        task.status = TaskStatus.FAILED
        task.completed_at = datetime.now()
        task.error_message = error_message
        task.error_code = error_code
        task.error_details = error_details
        
        # 计算处理时间
        if task.started_at:
            task.processing_time = (task.completed_at - task.started_at).total_seconds()
        
        self.current_task_id = None
        self.failed_tasks += 1
        
        logger.error(f"Failed task {task_id}: {error_message}")
    
    def delete_task(self, task_id: str, keep_intermediate: bool = False) -> bool:
        """删除任务"""
        task = self.get_task(task_id)
        if not task:
            return False
        
        # 收集所有文件路径
        file_paths = [task.video_path, task.fbx_path]
        
        if not keep_intermediate:
            file_paths.extend([
                task.tracking_pkl,
                task.extracted_npz,
                task.smoothed_npz
            ])
        
        # 删除文件
        FileHandler.delete_task_files(task_id, [f for f in file_paths if f])
        
        # 从队列中移除
        if task_id in self.queue:
            self.queue.remove(task_id)
        
        # 删除任务记录
        del self.tasks[task_id]
        
        logger.info(f"Deleted task {task_id}")
        return True
    
    def get_all_tasks(self) -> List[Task]:
        """获取所有任务"""
        return list(self.tasks.values())
    
    def get_queue_info(self) -> Dict:
        """获取队列信息"""
        current_task = None
        if self.current_task_id:
            task = self.get_task(self.current_task_id)
            if task:
                current_task = {
                    "task_id": task.task_id,
                    "progress": task.progress,
                    "current_step": task.current_step
                }
        
        queued_tasks = []
        for idx, task_id in enumerate(self.queue):
            task = self.get_task(task_id)
            if task:
                queued_tasks.append({
                    "task_id": task.task_id,
                    "position": idx + 1
                })
        
        return {
            "queue_size": len(self.queue),
            "max_queue_size": settings.MAX_QUEUE_SIZE,
            "current_task": current_task,
            "queued_tasks": queued_tasks
        }
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        uptime = int((datetime.now() - self.start_time).total_seconds())
        
        # 计算成功率
        success_rate = 0.0
        if self.total_tasks > 0:
            success_rate = self.completed_tasks / self.total_tasks
        
        # 计算平均处理时间
        avg_time = 0.0
        completed_with_time = [
            task for task in self.tasks.values()
            if task.status == TaskStatus.COMPLETED and task.processing_time
        ]
        if completed_with_time:
            total_time = sum(task.processing_time for task in completed_with_time)
            avg_time = total_time / len(completed_with_time)
        
        return {
            "uptime": uptime,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "active_tasks": 1 if self.current_task_id else 0,
            "queued_tasks": len(self.queue),
            "success_rate": success_rate,
            "average_processing_time": avg_time
        }
    
    def cleanup_old_tasks(self) -> int:
        """清理过期任务"""
        if not settings.AUTO_CLEANUP_ENABLED:
            return 0
        
        now = datetime.now()
        completed_threshold = timedelta(hours=settings.CLEANUP_COMPLETED_HOURS)
        failed_threshold = timedelta(hours=settings.CLEANUP_FAILED_HOURS)
        
        tasks_to_delete = []
        
        for task_id, task in self.tasks.items():
            if task.status == TaskStatus.COMPLETED:
                if task.completed_at and (now - task.completed_at) > completed_threshold:
                    tasks_to_delete.append(task_id)
            elif task.status == TaskStatus.FAILED:
                if task.completed_at and (now - task.completed_at) > failed_threshold:
                    tasks_to_delete.append(task_id)
        
        # 删除过期任务
        for task_id in tasks_to_delete:
            self.delete_task(task_id, keep_intermediate=False)
        
        if tasks_to_delete:
            logger.info(f"Cleaned up {len(tasks_to_delete)} old tasks")
        
        return len(tasks_to_delete)
    
    def cleanup_demo_files(self) -> int:
        """清理演示文件"""
        if not settings.CLEANUP_DEMO_FILES_ENABLED:
            return 0
        
        from datetime import timedelta
        from pathlib import Path
        import time
        
        deleted_count = 0
        threshold_days = settings.CLEANUP_DEMO_FILES_DAYS
        threshold_seconds = threshold_days * 24 * 3600
        now = time.time()
        
        # 清理 outputs/ 中的演示文件
        outputs_dir = Path(settings.OUTPUT_DIR)
        
        # 清理 PHALP_*.mp4 文件
        for mp4_file in outputs_dir.glob("PHALP_*.mp4"):
            if mp4_file.is_file():
                file_age = now - mp4_file.stat().st_mtime
                if file_age > threshold_seconds:
                    try:
                        mp4_file.unlink()
                        logger.info(f"Deleted old demo video: {mp4_file}")
                        deleted_count += 1
                    except Exception as e:
                        logger.error(f"Failed to delete {mp4_file}: {e}")
        
        # 清理 _DEMO/ 目录
        demo_dir = outputs_dir / "_DEMO"
        if demo_dir.exists():
            for item in demo_dir.iterdir():
                if item.is_dir() or item.is_file():
                    item_age = now - item.stat().st_mtime
                    if item_age > threshold_seconds:
                        try:
                            if item.is_dir():
                                import shutil
                                shutil.rmtree(item)
                            else:
                                item.unlink()
                            logger.info(f"Deleted old demo file: {item}")
                            deleted_count += 1
                        except Exception as e:
                            logger.error(f"Failed to delete {item}: {e}")
        
        # 清理 demo_out/ 目录
        demo_out_dir = Path(settings.PROJECT_ROOT) / "demo_out"
        if demo_out_dir.exists():
            for item in demo_out_dir.iterdir():
                if item.is_file():
                    item_age = now - item.stat().st_mtime
                    if item_age > threshold_seconds:
                        try:
                            item.unlink()
                            logger.info(f"Deleted old demo_out file: {item}")
                            deleted_count += 1
                        except Exception as e:
                            logger.error(f"Failed to delete {item}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} demo files")
        
        return deleted_count
    
    def cleanup_test_files(self) -> int:
        """清理测试文件"""
        if not settings.CLEANUP_TEST_FILES_ENABLED:
            return 0
        
        from pathlib import Path
        import time
        
        deleted_count = 0
        threshold_days = settings.CLEANUP_TEST_FILES_DAYS
        threshold_seconds = threshold_days * 24 * 3600
        now = time.time()
        
        # 清理 tmp/ 中的测试文件
        tmp_dir = Path(settings.TEMP_DIR)
        if tmp_dir.exists():
            for test_file in tmp_dir.glob("test_*"):
                if test_file.is_file():
                    file_age = now - test_file.stat().st_mtime
                    if file_age > threshold_seconds:
                        try:
                            test_file.unlink()
                            logger.info(f"Deleted old test file: {test_file}")
                            deleted_count += 1
                        except Exception as e:
                            logger.error(f"Failed to delete {test_file}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} test files")
        
        return deleted_count
    
    def cleanup_log_files(self) -> int:
        """清理日志文件"""
        from pathlib import Path
        import time
        
        deleted_count = 0
        threshold_days = settings.CLEANUP_LOG_FILES_DAYS
        threshold_seconds = threshold_days * 24 * 3600
        now = time.time()
        
        # 清理 logs/ 目录
        logs_dir = Path(settings.LOG_DIR)
        if logs_dir.exists():
            for log_file in logs_dir.glob("*.log"):
                if log_file.is_file():
                    file_age = now - log_file.stat().st_mtime
                    if file_age > threshold_seconds:
                        try:
                            log_file.unlink()
                            logger.info(f"Deleted old log file: {log_file}")
                            deleted_count += 1
                        except Exception as e:
                            logger.error(f"Failed to delete {log_file}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} log files")
        
        return deleted_count


# 全局任务管理器实例
_task_manager_instance = None


def get_task_manager() -> TaskManager:
    """获取任务管理器单例"""
    global _task_manager_instance
    if _task_manager_instance is None:
        _task_manager_instance = TaskManager()
    return _task_manager_instance

