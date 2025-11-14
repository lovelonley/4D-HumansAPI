"""4D-Humans MoCap 完整流程封装"""
import subprocess
import os
import sys
import time
import pickle
import shutil
from pathlib import Path
from typing import Optional, Dict, Callable
from ..config import settings
from ..utils.logger import logger
from ..constants import ProcessStep, ErrorCode


class PipelineResult:
    """Pipeline 执行结果"""
    
    def __init__(
        self,
        success: bool,
        output_path: Optional[str] = None,
        error: Optional[str] = None,
        error_code: Optional[str] = None,
        logs: str = "",
        duration: float = 0.0
    ):
        self.success = success
        self.output_path = output_path
        self.error = error
        self.error_code = error_code
        self.logs = logs
        self.duration = duration
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "output_path": self.output_path,
            "error": self.error,
            "error_code": self.error_code,
            "logs": self.logs,
            "duration": self.duration
        }


class FourDHumansPipeline:
    """4D-Humans MoCap 完整流程封装"""
    
    def __init__(self):
        self.project_root = Path(settings.PROJECT_ROOT)
        self.output_dir = Path(settings.OUTPUT_DIR)
        self.temp_dir = Path(settings.TEMP_DIR)
        
        # 确保目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 工具路径
        self.track_script = self.project_root / "track.py"
        self.extract_script = self.project_root / "tools" / "extract_track_for_tid.py"
        self.smooth_script = self.project_root / "tools" / "adapt_smoothnet.py"
        # Use official SMPL-X addon based script for better quality
        self.fbx_script = self.project_root / "tools" / "blender" / "smplx_npz_to_fbx.py"
        self.mesh_removal_script = self.project_root / "tools" / "blender" / "remove_mesh_from_fbx.py"
        
        # 验证脚本存在
        for script in [self.track_script, self.extract_script, self.smooth_script, self.fbx_script, self.mesh_removal_script]:
            if not script.exists():
                raise ValueError(f"Required script not found: {script}")
    
    def _run_command(
        self,
        cmd: list,
        timeout: int,
        step_name: str,
        cwd: Optional[Path] = None
    ) -> PipelineResult:
        """
        执行命令
        
        Args:
            cmd: 命令列表
            timeout: 超时时间（秒）
            step_name: 步骤名称（用于日志）
            cwd: 工作目录
            
        Returns:
            PipelineResult
        """
        logger.info(f"[{step_name}] Starting...")
        logger.debug(f"[{step_name}] Command: {' '.join(cmd)}")
        
        start_time = time.time()
        
        # 继承当前环境变量
        env = os.environ.copy()
        
        try:
            result = subprocess.run(
                cmd,
                cwd=str(cwd) if cwd else None,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env
            )
            
            duration = time.time() - start_time
            
            if result.returncode != 0:
                logger.error(f"[{step_name}] Failed in {duration:.2f}s")
                logger.error(f"[{step_name}] stderr: {result.stderr[:500]}")
                
                return PipelineResult(
                    success=False,
                    error=result.stderr,
                    error_code=self._infer_error_code(step_name, result.stderr),
                    logs=result.stdout + "\n" + result.stderr,
                    duration=duration
                )
            
            logger.info(f"[{step_name}] Completed in {duration:.2f}s")
            
            return PipelineResult(
                success=True,
                logs=result.stdout,
                duration=duration
            )
            
        except subprocess.TimeoutExpired as e:
            duration = time.time() - start_time
            logger.error(f"[{step_name}] Timeout after {duration:.2f}s")
            
            # P0修复: 强制终止超时的子进程，防止资源泄露
            if e.process:
                try:
                    # P1修复: 使用配置中的超时时间
                    logger.warning(f"[{step_name}] Killing timed out process (PID: {e.process.pid})")
                    e.process.kill()
                    e.process.wait(timeout=settings.PROCESS_KILL_TIMEOUT)  # 等待进程完全退出
                    logger.info(f"[{step_name}] Process terminated successfully")
                except Exception as kill_error:
                    logger.error(f"[{step_name}] Failed to kill process: {kill_error}")
            
            return PipelineResult(
                success=False,
                error=f"Command timed out after {timeout}s",
                error_code=ErrorCode.TASK_TIMEOUT,
                duration=duration
            )
        except (OSError, IOError) as e:
            # P1修复: 区分文件系统错误
            duration = time.time() - start_time
            logger.error(f"[{step_name}] File system error: {str(e)}")
            
            return PipelineResult(
                success=False,
                error=str(e),
                error_code=ErrorCode.DISK_FULL if "space" in str(e).lower() or "disk" in str(e).lower() else ErrorCode.INTERNAL_ERROR,
                duration=duration
            )
        except ValueError as e:
            # P1修复: 区分参数错误
            duration = time.time() - start_time
            logger.error(f"[{step_name}] Value error: {str(e)}")
            
            return PipelineResult(
                success=False,
                error=str(e),
                error_code=ErrorCode.INVALID_REQUEST,
                duration=duration
            )
        except Exception as e:
            # 其他未知异常
            duration = time.time() - start_time
            logger.error(f"[{step_name}] Unexpected exception: {str(e)}", exc_info=True)
            
            return PipelineResult(
                success=False,
                error=str(e),
                error_code=ErrorCode.INTERNAL_ERROR,
                duration=duration
            )
    
    def _infer_error_code(self, step_name: str, error_msg: str) -> str:
        """根据错误信息推断错误码"""
        error_lower = error_msg.lower()
        
        # GPU 相关错误
        if "cuda out of memory" in error_lower or "out of memory" in error_lower:
            return ErrorCode.GPU_OUT_OF_MEMORY
        
        # 磁盘相关错误
        if "no space left" in error_lower or "disk full" in error_lower:
            return ErrorCode.DISK_FULL
        
        # 步骤特定错误
        if step_name == ProcessStep.TRACKING:
            return ErrorCode.TRACKING_FAILED
        elif step_name == ProcessStep.TRACK_EXTRACTION:
            return ErrorCode.TRACK_EXTRACTION_FAILED
        elif step_name == ProcessStep.SMOOTHING:
            return ErrorCode.SMOOTHING_FAILED
        elif step_name == ProcessStep.FBX_EXPORT:
            return ErrorCode.FBX_EXPORT_FAILED
        
        return ErrorCode.INTERNAL_ERROR
    
    def _validate_path(self, file_path: str, allowed_dir: Path) -> bool:
        """
        P0修复: 验证文件路径是否在允许的目录内（兼容 Python 3.8+）
        
        Args:
            file_path: 文件路径
            allowed_dir: 允许的目录
            
        Returns:
            是否在允许的目录内
        """
        try:
            resolved = Path(file_path).resolve()
            allowed = allowed_dir.resolve()
            
            # P0修复: 兼容 Python 3.8 和 3.9+
            if hasattr(resolved, 'is_relative_to'):
                # Python 3.9+ 使用 is_relative_to
                return resolved.is_relative_to(allowed)
            else:
                # Python 3.8 兼容方案：使用 relative_to
                try:
                    resolved.relative_to(allowed)
                    return True
                except ValueError:
                    return False
        except (ValueError, AttributeError):
            return False
    
    def run_tracking(
        self,
        video_path: str,
        task_id: str,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> PipelineResult:
        """
        步骤 1: 运行 PHALP 追踪
        
        Args:
            video_path: 视频文件路径
            task_id: 任务ID
            progress_callback: 进度回调函数
            
        Returns:
            PipelineResult (output_path = tracking_pkl)
        """
        if progress_callback:
            progress_callback(10)
        
        # P1修复: 验证视频路径安全性
        if not self._validate_path(video_path, settings.UPLOAD_DIR):
            return PipelineResult(
                success=False,
                error=f"Invalid video path: {video_path}",
                error_code=ErrorCode.INVALID_REQUEST,
                duration=0.0
            )
        
        # 从视频路径提取文件名（PHALP 会自动使用视频文件名作为输出）
        video_name = Path(video_path).stem
        
        # PHALP 输出路径（使用 video_name，PHALP 内部会生成 demo_{video_name}.pkl）
        phalp_output_pkl = self.output_dir / "results" / f"demo_{video_name}.pkl"
        phalp_output_pkl.parent.mkdir(parents=True, exist_ok=True)
        
        # 最终输出路径（使用 task_id 统一命名）
        output_pkl = self.output_dir / "results" / f"{task_id}.pkl"
        
        # 构建命令（不使用 video.seq 参数，PHALP 会自动从视频文件名提取）
        cmd = [
            sys.executable,  # 使用当前 Python
            str(self.track_script),
            f"video.source={video_path}",
            f"video.output_dir={self.output_dir}"
        ]
        
        result = self._run_command(
            cmd=cmd,
            timeout=settings.TRACKING_TIMEOUT,
            step_name=ProcessStep.TRACKING,
            cwd=self.project_root
        )
        
        if result.success:
            # P1修复: 验证 PHALP 输出文件（TOCTOU 保护）
            # 先检查文件是否存在，然后立即使用
            if phalp_output_pkl.exists():
                # 重命名为使用 task_id 的文件名（统一命名规范）
                try:
                    # P1修复: 在使用文件前再次检查存在性（TOCTOU 保护）
                    if not phalp_output_pkl.exists():
                        raise FileNotFoundError(f"File disappeared: {phalp_output_pkl}")
                    shutil.move(str(phalp_output_pkl), str(output_pkl))
                    logger.info(f"Renamed tracking output: {phalp_output_pkl.name} -> {output_pkl.name}")
                except (OSError, IOError, shutil.Error, FileNotFoundError) as e:
                    # P1修复: 区分文件操作错误
                    logger.warning(f"Failed to rename tracking file, using original: {e}")
                    output_pkl = phalp_output_pkl
                
                # P1修复: 验证输出文件确实存在
                if output_pkl.exists():
                    result.output_path = str(output_pkl)
                    if progress_callback:
                        progress_callback(30)
                else:
                    result.success = False
                    result.error = f"Output file not found: {output_pkl}"
                    result.error_code = ErrorCode.TRACKING_FAILED
            else:
                result.success = False
                result.error = f"Tracking output file not found: {phalp_output_pkl}"
                result.error_code = ErrorCode.TRACKING_FAILED
        
        return result
    
    def run_extraction(
        self,
        tracking_pkl: str,
        task_id: str,
        track_id: Optional[int] = None,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> PipelineResult:
        """
        步骤 2: 提取单人轨迹
        
        Args:
            tracking_pkl: PHALP 输出的 .pkl 文件
            task_id: 任务ID
            track_id: 指定的人物ID（None 则自动选择最长轨迹）
            progress_callback: 进度回调函数
            
        Returns:
            PipelineResult (output_path = extracted_npz)
        """
        if progress_callback:
            progress_callback(35)
        
        # 如果没有指定 track_id，自动选择最长轨迹
        if track_id is None:
            track_id = self._get_longest_track_id(tracking_pkl)
            if track_id is None:
                return PipelineResult(
                    success=False,
                    error="No tracks found in tracking result",
                    error_code=ErrorCode.NO_TRACKS_FOUND
                )
        
        logger.info(f"Extracting track_id: {track_id}")
        
        # 输出路径
        output_npz = self.temp_dir / f"{task_id}_tid{track_id}_extracted.npz"
        
        # 构建命令
        cmd = [
            sys.executable,
            str(self.extract_script),
            "--pkl", tracking_pkl,
            "--out", str(output_npz),
            "--tid", str(track_id)
        ]
        
        result = self._run_command(
            cmd=cmd,
            timeout=settings.EXTRACTION_TIMEOUT,
            step_name=ProcessStep.TRACK_EXTRACTION,
            cwd=self.project_root
        )
        
        if result.success:
            # P1修复: TOCTOU 保护 - 验证文件存在
            if output_npz.exists():
                # P1修复: 再次检查文件确实存在（TOCTOU 保护）
                if not output_npz.exists():
                    result.success = False
                    result.error = f"Output file disappeared: {output_npz}"
                    result.error_code = ErrorCode.TRACK_EXTRACTION_FAILED
                else:
                    result.output_path = str(output_npz)
                    if progress_callback:
                        progress_callback(45)
            else:
                result.success = False
                result.error = f"Extraction output file not found: {output_npz}"
                result.error_code = ErrorCode.TRACK_EXTRACTION_FAILED
        
        return result
    
    def run_smoothing(
        self,
        extracted_npz: str,
        task_id: str,
        smoothing_strength: float = 1.0,
        smoothing_window: int = 9,
        smoothing_ema: float = 0.2,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> PipelineResult:
        """
        步骤 3: SmoothNet 平滑
        
        Args:
            extracted_npz: 提取的 NPZ 文件
            task_id: 任务ID
            smoothing_strength: 平滑强度
            smoothing_window: 平滑窗口大小
            smoothing_ema: 相机 EMA 系数
            progress_callback: 进度回调函数
            
        Returns:
            PipelineResult (output_path = smoothed_npz)
        """
        if progress_callback:
            progress_callback(50)
        
        # 输出路径
        output_npz = self.temp_dir / f"{task_id}_smoothed.npz"
        
        # SmoothNet 检查点路径
        checkpoint_path = self.project_root / settings.SMOOTHNET_CHECKPOINT
        
        # 构建命令
        cmd = [
            sys.executable,
            str(self.smooth_script),
            "--npz", extracted_npz,
            "--out", str(output_npz),
            "--ckpt", str(checkpoint_path),
            "--win", str(smoothing_window),
            "--ema", str(smoothing_ema),
            "--strength", str(smoothing_strength)
        ]
        
        result = self._run_command(
            cmd=cmd,
            timeout=settings.SMOOTHING_TIMEOUT,
            step_name=ProcessStep.SMOOTHING,
            cwd=self.project_root
        )
        
        if result.success:
            # P1修复: TOCTOU 保护 - 验证文件存在
            if output_npz.exists():
                # P1修复: 再次检查文件确实存在（TOCTOU 保护）
                if not output_npz.exists():
                    result.success = False
                    result.error = f"Output file disappeared: {output_npz}"
                    result.error_code = ErrorCode.SMOOTHING_FAILED
                else:
                    result.output_path = str(output_npz)
                    if progress_callback:
                        progress_callback(70)
            else:
                result.success = False
                result.error = f"Smoothing output file not found: {output_npz}"
                result.error_code = ErrorCode.SMOOTHING_FAILED
        
        return result
    
    def run_fbx_export(
        self,
        smoothed_npz: str,
        task_id: str,
        fps: int = 30,
        with_root_motion: bool = True,
        cam_scale: float = 1.0,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> PipelineResult:
        """
        步骤 4: 导出 FBX
        
        Args:
            smoothed_npz: 平滑后的 NPZ 文件
            task_id: 任务ID
            fps: 帧率
            with_root_motion: 是否包含根运动
            cam_scale: 相机缩放
            progress_callback: 进度回调函数
            
        Returns:
            PipelineResult (output_path = fbx_path)
        """
        if progress_callback:
            progress_callback(75)
        
        # 输出路径
        result_dir = Path(settings.RESULT_DIR)
        result_dir.mkdir(parents=True, exist_ok=True)
        
        root_motion_suffix = "_rootmotion" if with_root_motion else ""
        output_fbx = result_dir / f"{task_id}{root_motion_suffix}.fbx"
        
        # 构建命令
        cmd = [
            settings.BLENDER_PATH,
            "-b",  # 后台模式
            "-P", str(self.fbx_script),
            "--",
            "--npz", smoothed_npz,
            "--out", str(output_fbx),
            "--fps", str(fps)
        ]
        
        # Note: --with-root-motion removed, motion analysis now built-in
        
        result = self._run_command(
            cmd=cmd,
            timeout=settings.FBX_EXPORT_TIMEOUT,
            step_name=ProcessStep.FBX_EXPORT,
            cwd=self.project_root
        )
        
        if result.success:
            # P1修复: TOCTOU 保护 - 验证文件存在
            if output_fbx.exists():
                # P1修复: 再次检查文件确实存在（TOCTOU 保护）
                if not output_fbx.exists():
                    result.success = False
                    result.error = f"Output file disappeared: {output_fbx}"
                    result.error_code = ErrorCode.FBX_EXPORT_FAILED
                else:
                    # Remove mesh from FBX to reduce file size
                    mesh_removal_result = self._remove_mesh_from_fbx(
                        output_fbx, 
                        task_id, 
                        progress_callback
                    )
                    
                    if mesh_removal_result.success:
                        result.output_path = mesh_removal_result.output_path
                        if progress_callback:
                            progress_callback(95)
                    else:
                        # Mesh removal failed, but keep original FBX
                        logger.warning(f"Mesh removal failed, using original FBX: {mesh_removal_result.error}")
                        result.output_path = str(output_fbx)
                        if progress_callback:
                            progress_callback(95)
            else:
                result.success = False
                result.error = f"FBX output file not found: {output_fbx}"
                result.error_code = ErrorCode.FBX_EXPORT_FAILED
        
        return result
    
    def _remove_mesh_from_fbx(
        self,
        input_fbx: Path,
        task_id: str,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> PipelineResult:
        """
        Remove mesh from FBX file (keep skeleton and animation only)
        
        Args:
            input_fbx: Input FBX file path (with mesh)
            task_id: Task ID for output naming
            progress_callback: Optional progress callback
            
        Returns:
            PipelineResult with output_path pointing to mesh-free FBX
        """
        logger.info(f"Removing mesh from FBX: {input_fbx}")
        
        # Output path (replace original file)
        output_fbx = input_fbx.parent / f"{task_id}_no_mesh.fbx"
        
        # Build command
        cmd = [
            settings.BLENDER_PATH,
            "-b",  # Background mode
            "-P", str(self.mesh_removal_script),
            "--",
            "--input", str(input_fbx),
            "--output", str(output_fbx)
        ]
        
        result = self._run_command(
            cmd=cmd,
            timeout=settings.FBX_EXPORT_TIMEOUT,  # Reuse FBX export timeout
            step_name=ProcessStep.FBX_EXPORT,  # Part of FBX export step
            cwd=self.project_root
        )
        
        if result.success:
            if output_fbx.exists():
                result.output_path = str(output_fbx)
                logger.info(f"Mesh removed successfully: {output_fbx}")
                
                # Delete original FBX with mesh to save space
                try:
                    input_fbx.unlink()
                    logger.info(f"Deleted original FBX with mesh: {input_fbx}")
                except Exception as e:
                    logger.warning(f"Failed to delete original FBX: {e}")
            else:
                result.success = False
                result.error = f"Mesh-free FBX output file not found: {output_fbx}"
                result.error_code = ErrorCode.FBX_EXPORT_FAILED
        
        return result
    
    def run_full_pipeline(
        self,
        video_path: str,
        task_id: str,
        track_id: Optional[int] = None,
        fps: int = 30,
        with_root_motion: bool = True,
        cam_scale: float = 1.0,
        smoothing_strength: float = 1.0,
        smoothing_window: int = 9,
        smoothing_ema: float = 0.2,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> Dict[str, any]:
        """
        运行完整流程
        
        Args:
            video_path: 视频文件路径
            task_id: 任务ID
            track_id: 指定的人物ID（None 则自动选择最长轨迹）
            fps: 输出帧率
            with_root_motion: 是否包含根运动
            cam_scale: 相机缩放
            smoothing_strength: 平滑强度
            smoothing_window: 平滑窗口大小
            smoothing_ema: 相机 EMA 系数
            progress_callback: 进度回调函数
            
        Returns:
            {
                "success": bool,
                "fbx_path": str,
                "tracking_pkl": str,
                "extracted_npz": str,
                "smoothed_npz": str,
                "error": str,
                "error_code": str,
                "error_step": str,
                "total_duration": float
            }
        """
        total_start = time.time()
        # P0修复: 跟踪已生成的文件，失败时清理
        generated_files = []
        
        try:
            # 步骤 1: 追踪
            result = self.run_tracking(video_path, task_id, progress_callback)
            if not result.success:
                self._cleanup_generated_files(generated_files)
                return {
                    "success": False,
                    "error": result.error,
                    "error_code": result.error_code,
                    "error_step": ProcessStep.TRACKING,
                    "total_duration": time.time() - total_start
                }
            # P1修复: 验证文件存在（错误恢复）
            tracking_pkl = result.output_path
            if not tracking_pkl or not Path(tracking_pkl).exists():
                self._cleanup_generated_files(generated_files)
                return {
                    "success": False,
                    "error": f"Tracking output file not found: {tracking_pkl}",
                    "error_code": ErrorCode.TRACKING_FAILED,
                    "error_step": ProcessStep.TRACKING,
                    "total_duration": time.time() - total_start
                }
            generated_files.append(tracking_pkl)
            
            # 步骤 2: 提取
            result = self.run_extraction(tracking_pkl, task_id, track_id, progress_callback)
            if not result.success:
                # 清理已生成的文件
                self._cleanup_generated_files(generated_files)
                return {
                    "success": False,
                    "error": result.error,
                    "error_code": result.error_code,
                    "error_step": ProcessStep.TRACK_EXTRACTION,
                    "total_duration": time.time() - total_start
                }
            # P1修复: 验证文件存在（错误恢复）
            extracted_npz = result.output_path
            if not extracted_npz or not Path(extracted_npz).exists():
                self._cleanup_generated_files(generated_files)
                return {
                    "success": False,
                    "error": f"Extraction output file not found: {extracted_npz}",
                    "error_code": ErrorCode.TRACK_EXTRACTION_FAILED,
                    "error_step": ProcessStep.TRACK_EXTRACTION,
                    "total_duration": time.time() - total_start
                }
            generated_files.append(extracted_npz)
            
            # 步骤 3: 平滑
            result = self.run_smoothing(
                extracted_npz, task_id,
                smoothing_strength, smoothing_window, smoothing_ema,
                progress_callback
            )
            if not result.success:
                # 清理已生成的文件
                self._cleanup_generated_files(generated_files)
                return {
                    "success": False,
                    "error": result.error,
                    "error_code": result.error_code,
                    "error_step": ProcessStep.SMOOTHING,
                    "total_duration": time.time() - total_start
                }
            # P1修复: 验证文件存在（错误恢复）
            smoothed_npz = result.output_path
            if not smoothed_npz or not Path(smoothed_npz).exists():
                self._cleanup_generated_files(generated_files)
                return {
                    "success": False,
                    "error": f"Smoothing output file not found: {smoothed_npz}",
                    "error_code": ErrorCode.SMOOTHING_FAILED,
                    "error_step": ProcessStep.SMOOTHING,
                    "total_duration": time.time() - total_start
                }
            generated_files.append(smoothed_npz)
            
            # 步骤 4: 导出 FBX
            result = self.run_fbx_export(
                smoothed_npz, task_id,
                fps, with_root_motion, cam_scale,
                progress_callback
            )
            if not result.success:
                # 清理已生成的文件
                self._cleanup_generated_files(generated_files)
                return {
                    "success": False,
                    "error": result.error,
                    "error_code": result.error_code,
                    "error_step": ProcessStep.FBX_EXPORT,
                    "total_duration": time.time() - total_start
                }
            # P1修复: 验证文件存在（错误恢复）
            fbx_path = result.output_path
            if not fbx_path or not Path(fbx_path).exists():
                self._cleanup_generated_files(generated_files)
                return {
                    "success": False,
                    "error": f"FBX output file not found: {fbx_path}",
                    "error_code": ErrorCode.FBX_EXPORT_FAILED,
                    "error_step": ProcessStep.FBX_EXPORT,
                    "total_duration": time.time() - total_start
                }
            
            if progress_callback:
                progress_callback(100)
            
            total_duration = time.time() - total_start
            logger.info(f"Full pipeline completed in {total_duration:.2f}s")
            
            return {
                "success": True,
                "fbx_path": fbx_path,
                "tracking_pkl": tracking_pkl,
                "extracted_npz": extracted_npz,
                "smoothed_npz": smoothed_npz,
                "total_duration": total_duration
            }
        
        except (OSError, IOError) as e:
            # P1修复: 区分文件系统错误
            logger.error(f"Pipeline file system error: {e}", exc_info=True)
            self._cleanup_generated_files(generated_files)
            raise
        except ValueError as e:
            # P1修复: 区分参数错误
            logger.error(f"Pipeline value error: {e}", exc_info=True)
            self._cleanup_generated_files(generated_files)
            raise
        except Exception as e:
            # P0修复: 异常时清理已生成的文件
            logger.error(f"Pipeline unexpected exception: {e}", exc_info=True)
            self._cleanup_generated_files(generated_files)
            raise
    
    def _cleanup_generated_files(self, file_paths: list):
        """
        P0修复: 清理已生成的文件，防止磁盘泄露
        
        Args:
            file_paths: 文件路径列表
        """
        from ..utils.file_handler import FileHandler
        
        for file_path in file_paths:
            if file_path and Path(file_path).exists():
                try:
                    FileHandler.delete_file(file_path)
                    logger.info(f"Cleaned up generated file: {file_path}")
                except (OSError, IOError) as e:
                    # P1修复: 区分文件操作错误
                    logger.error(f"Failed to cleanup file {file_path}: {e}")
    
    def _get_longest_track_id(self, tracking_pkl: str) -> Optional[int]:
        """
        从 tracking.pkl 中获取最长轨迹的 ID
        
        Args:
            tracking_pkl: PHALP 输出的 .pkl 文件
            
        Returns:
            track_id 或 None
        """
        try:
            import joblib
            data = joblib.load(tracking_pkl)
            
            if not data:
                return None
            
            # 统计每个 track_id 的帧数
            track_counts = {}
            for frame_data in data.values():
                if 'tid' in frame_data:
                    tids = frame_data['tid']
                    for tid in tids:
                        track_counts[tid] = track_counts.get(tid, 0) + 1
            
            if not track_counts:
                return None
            
            # 返回帧数最多的 track_id
            longest_tid = max(track_counts, key=track_counts.get)
            logger.info(f"Longest track: tid={longest_tid}, frames={track_counts[longest_tid]}")
            
            return longest_tid
            
        except (FileNotFoundError, IOError) as e:
            # P1修复: 区分文件读取错误
            logger.error(f"Failed to read tracking file: {e}")
            return None
        except (KeyError, AttributeError, TypeError) as e:
            # P1修复: 区分数据格式错误
            logger.error(f"Invalid tracking data format: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to get longest track ID: {e}")
            return None

