# 4D-Humans 视频动作捕捉 API 服务规划

## 📋 项目概述

将 4D-Humans 项目改造为类似 UniRig 的 FastAPI RESTful 服务，提供**视频到 FBX 动画**的端到端 API。

### 核心功能
- ✅ 上传视频文件（单人优先，多人可选）
- ✅ 自动执行完整工作流（追踪 → 提取 → 平滑 → 导出）
- ✅ 异步任务队列处理
- ✅ 实时进度查询
- ✅ 下载 FBX 动画文件

---

## 🎯 技术方案对比

### UniRig 架构（参考）
```
输入: 3D 模型文件 (GLB/FBX/OBJ)
  ↓
Pipeline: skeleton → rename → skin → merge
  ↓
输出: 绑骨后的 3D 模型 (GLB/FBX)
```

### 4D-Humans 架构（目标）
```
输入: 视频文件 (MP4/AVI/MOV)
  ↓
Pipeline: track → extract → smooth → blender_export
  ↓
输出: 动作动画文件 (FBX)
```

---

## 🏗️ 系统架构设计

### 目录结构（参考 UniRig）
```
4D-Humans/
├── api/                          # FastAPI 应用（新增）
│   ├── __init__.py
│   ├── main.py                   # FastAPI 主应用
│   ├── config.py                 # 配置管理
│   ├── constants.py              # 常量定义
│   │
│   ├── models/                   # Pydantic 数据模型
│   │   ├── __init__.py
│   │   ├── request.py            # 请求模型
│   │   └── response.py           # 响应模型
│   │
│   ├── routers/                  # API 路由
│   │   ├── __init__.py
│   │   ├── mocap.py              # 动捕相关 API
│   │   └── admin.py              # 管理 API
│   │
│   ├── services/                 # 业务逻辑
│   │   ├── __init__.py
│   │   ├── pipeline.py           # 4D-Humans 管线封装
│   │   ├── task_manager.py       # 任务管理器
│   │   └── worker.py             # 后台工作器
│   │
│   └── utils/                    # 工具函数
│       ├── __init__.py
│       ├── file_handler.py       # 文件处理
│       ├── gpu_monitor.py        # GPU 监控
│       └── logger.py             # 日志
│
├── tools/                        # 现有工具（保持不变）
│   ├── list_tids.py
│   ├── extract_track_for_tid.py
│   ├── adapt_smoothnet.py
│   └── blender/
│       ├── smplx_npz_to_fbx.py
│       └── pkl_npz_to_fbx.py
│
├── uploads/                      # 上传目录（新增）
├── results/                      # 结果目录（新增）
├── tmp/                          # 临时目录（新增）
├── logs/                         # 日志目录（新增）
│
├── requirements-api.txt          # API 依赖（新增）
├── .env.example                  # 环境变量模板（新增）
└── scripts/
    └── start.sh                  # 启动脚本（新增）
```

---

## 🔄 完整工作流设计

### Pipeline 步骤定义
```python
class ProcessStep:
    VIDEO_UPLOAD = "video_upload"           # 视频上传
    TRACKING = "tracking"                   # 4D-Humans 追踪
    TRACK_EXTRACTION = "track_extraction"   # 提取 Track ID
    SMOOTHING = "smoothing"                 # SmoothNet 平滑
    FBX_EXPORT = "fbx_export"              # Blender 导出 FBX
    PACKAGING = "packaging"                 # 打包结果（可选）

PROCESS_STEPS = [
    ProcessStep.VIDEO_UPLOAD,
    ProcessStep.TRACKING,
    ProcessStep.TRACK_EXTRACTION,
    ProcessStep.SMOOTHING,
    ProcessStep.FBX_EXPORT,
    ProcessStep.PACKAGING
]

# 预估时间（秒）
STEP_ESTIMATED_TIME = {
    ProcessStep.VIDEO_UPLOAD: 5,
    ProcessStep.TRACKING: 180,        # 3分钟（取决于视频长度）
    ProcessStep.TRACK_EXTRACTION: 10,
    ProcessStep.SMOOTHING: 30,
    ProcessStep.FBX_EXPORT: 20,
    ProcessStep.PACKAGING: 5
}
```

### 详细流程

#### Step 1: VIDEO_UPLOAD (视频上传)
```python
# 输入: video.mp4
# 输出: uploads/{task_id}/video.mp4
# 工具: FastAPI UploadFile
# 验证: 
#   - 文件格式 (mp4/avi/mov)
#   - 文件大小 (< 500MB)
#   - 视频时长 (< 60秒，可配置)
```

#### Step 2: TRACKING (4D-Humans 追踪)
```python
# 输入: uploads/{task_id}/video.mp4
# 输出: outputs/results/demo_{task_id}.pkl
# 工具: track.py
# 命令:
python track.py \
  video.source="uploads/{task_id}/video.mp4" \
  video.output_dir="outputs" \
  video.extract_video=True

# 输出文件:
#   - outputs/results/demo_{task_id}.pkl  (tracklets)
#   - outputs/PHALP_{task_id}.mp4         (可视化视频)
```

#### Step 3: TRACK_EXTRACTION (提取 Track ID)
```python
# 场景 A: 单人视频（默认）
# 输入: outputs/results/demo_{task_id}.pkl
# 输出: outputs/results/demo_{task_id}_tid{tid}.npz
# 工具: tools/list_tids.py + tools/extract_track_for_tid.py

# 流程:
# 1. 列出所有 Track IDs
python tools/list_tids.py --pkl outputs/results/demo_{task_id}.pkl

# 2. 选择主要 Track ID（帧数最多的）
#    或由用户指定 track_id 参数

# 3. 提取单人轨迹
python tools/extract_track_for_tid.py \
  --pkl outputs/results/demo_{task_id}.pkl \
  --tid {selected_tid} \
  --out outputs/results/demo_{task_id}_tid{tid}.npz \
  --fps 30

# 场景 B: 多人视频（可选）
# 选项 1: 提取所有 Track IDs，返回多个 FBX
# 选项 2: 让用户选择特定 Track ID
# 选项 3: 只返回主要角色（帧数最多）
```

#### Step 4: SMOOTHING (时序平滑)
```python
# 输入: outputs/results/demo_{task_id}_tid{tid}.npz
# 输出: outputs/results/demo_{task_id}_tid{tid}_smoothed.npz
# 工具: tools/adapt_smoothnet.py

# 命令:
export PYTHONPATH=$PWD/SmoothNet:$PWD/SmoothNet/lib:$PYTHONPATH
python tools/adapt_smoothnet.py \
  --npz outputs/results/demo_{task_id}_tid{tid}.npz \
  --ckpt SmoothNet/data/checkpoints/pw3d_spin_3D/checkpoint_8.pth.tar \
  --out outputs/results/demo_{task_id}_tid{tid}_smoothed.npz \
  --win 9 \
  --ema 0.2 \
  --strength 1.0

# 可选参数:
#   --strength: 平滑强度 (0.0-1.0)，默认 1.0
#   --win: 窗口大小，默认 9
```

#### Step 5: FBX_EXPORT (Blender 导出)
```python
# 输入: outputs/results/demo_{task_id}_tid{tid}_smoothed.npz
# 输出: results/{task_id}/animation.fbx
# 工具: tools/blender/smplx_npz_to_fbx.py

# 命令:
blender -b -P tools/blender/smplx_npz_to_fbx.py -- \
  --npz outputs/results/demo_{task_id}_tid{tid}_smoothed.npz \
  --out results/{task_id}/animation.fbx \
  --fps 30 \
  --with-root-motion \
  --cam-scale 1.0

# 可选参数:
#   --with-root-motion: 启用根运动
#   --cam-scale: 相机缩放比例
```

#### Step 6: PACKAGING (打包结果)
```python
# 输入: results/{task_id}/animation.fbx
# 输出: results/{task_id}/animation.zip (如果有 .fbm 文件夹)
# 工具: Python zipfile

# 逻辑:
# 1. 检查是否存在 animation.fbm/ 文件夹
# 2. 如果存在，打包成 ZIP
# 3. 如果不存在，直接返回 FBX
```

---

## 📡 API 端点设计

### 核心端点

#### 1. 创建动捕任务
```http
POST /api/v1/mocap
Content-Type: multipart/form-data

参数:
  - file: UploadFile          # 视频文件（必填）
  - track_mode: str           # 追踪模式: "single" | "multi" | "auto" (默认 "auto")
  - track_id: int             # 指定 Track ID（可选，multi 模式）
  - enable_smoothing: bool    # 启用平滑（默认 true）
  - smoothing_strength: float # 平滑强度 0.0-1.0（默认 1.0）
  - with_root_motion: bool    # 启用根运动（默认 true）
  - fps: int                  # 输出帧率（默认 30）
  - keep_intermediate: bool   # 保留中间文件（默认 false）

响应:
{
  "task_id": "uuid",
  "status": "queued",
  "position_in_queue": 1,
  "estimated_time": 250,
  "message": "任务已创建"
}
```

#### 2. 查询任务状态
```http
GET /api/v1/mocap/{task_id}

响应:
{
  "task_id": "uuid",
  "status": "processing",  # queued | processing | completed | failed
  "progress": {
    "current_step": "smoothing",
    "total_steps": 6,
    "percentage": 60,
    "steps": [
      {
        "name": "video_upload",
        "status": "completed",
        "duration": 5.2
      },
      {
        "name": "tracking",
        "status": "completed",
        "duration": 182.5
      },
      {
        "name": "track_extraction",
        "status": "completed",
        "duration": 8.3
      },
      {
        "name": "smoothing",
        "status": "processing",
        "duration": null
      },
      {
        "name": "fbx_export",
        "status": "pending",
        "duration": null
      },
      {
        "name": "packaging",
        "status": "pending",
        "duration": null
      }
    ]
  },
  "metadata": {
    "filename": "video.mp4",
    "file_size": 10485760,
    "duration": 30.5,
    "fps": 30,
    "track_count": 2,
    "selected_track_id": 1,
    "created_at": "2025-01-01T10:00:00",
    "started_at": "2025-01-01T10:00:05",
    "estimated_completion": "2025-01-01T10:04:15"
  },
  "result": null  # 完成后才有
}
```

#### 3. 下载结果
```http
GET /api/v1/mocap/{task_id}/download

响应:
  - 单人: animation.fbx 或 animation.zip
  - 多人: animations.zip (包含多个 FBX)
  
Content-Type: application/octet-stream
Content-Disposition: attachment; filename="animation.fbx"
```

#### 4. 下载中间文件
```http
GET /api/v1/mocap/{task_id}/intermediate?file={filename}

可选文件:
  - visualization.mp4  # PHALP 可视化视频
  - tracklets.pkl      # 原始 tracklets
  - track_npz.npz      # 提取的 NPZ
  - smoothed.npz       # 平滑后的 NPZ
```

#### 5. 列出 Track IDs（多人场景）
```http
GET /api/v1/mocap/{task_id}/tracks

响应:
{
  "task_id": "uuid",
  "tracks": [
    {
      "track_id": 1,
      "frame_count": 842,
      "percentage": 95.2
    },
    {
      "track_id": 2,
      "frame_count": 320,
      "percentage": 36.2
    }
  ],
  "recommended_track_id": 1
}
```

#### 6. 重新导出（指定 Track ID）
```http
POST /api/v1/mocap/{task_id}/re-export
Content-Type: application/json

{
  "track_id": 2,
  "enable_smoothing": true,
  "smoothing_strength": 0.8,
  "with_root_motion": true
}

响应:
{
  "task_id": "uuid-new",
  "status": "queued",
  "message": "重新导出任务已创建"
}
```

### 管理端点

#### 7. 查看队列
```http
GET /api/v1/queue

响应:
{
  "queue_size": 2,
  "max_queue_size": 10,
  "current_task": {
    "task_id": "uuid",
    "filename": "video.mp4",
    "progress": 45,
    "estimated_remaining": 120
  },
  "queued_tasks": [
    {
      "task_id": "uuid2",
      "filename": "video2.mp4",
      "position": 1,
      "estimated_start": "2025-01-01T10:05:00"
    }
  ]
}
```

#### 8. 统计信息
```http
GET /api/v1/stats

响应:
{
  "uptime": 86400,
  "total_tasks": 150,
  "completed_tasks": 140,
  "failed_tasks": 10,
  "active_tasks": 1,
  "queued_tasks": 2,
  "success_rate": 0.933,
  "average_processing_time": 245.5,
  "step_average_times": {
    "tracking": 180.2,
    "smoothing": 28.5,
    "fbx_export": 18.3
  },
  "gpu_info": {
    "gpu_count": 1,
    "gpu_name": "NVIDIA RTX 4090",
    "memory_used": 8192,
    "memory_total": 24576,
    "utilization": 85
  },
  "storage": {
    "uploads_size": 1073741824,
    "results_size": 536870912,
    "total_used": 1610612736,
    "total_available": 107374182400
  }
}
```

#### 9. 健康检查
```http
GET /api/v1/health

响应:
{
  "status": "healthy",  # healthy | degraded | unhealthy
  "checks": {
    "api": "ok",
    "gpu": "ok",
    "disk": "ok",
    "queue": "ok"
  },
  "warnings": []
}
```

#### 10. 清理过期任务
```http
POST /api/v1/admin/cleanup

响应:
{
  "cleaned_tasks": 15,
  "freed_space": 536870912
}
```

---

## 🔧 核心代码实现

### 1. Pipeline 封装 (`api/services/pipeline.py`)

```python
class FourDHumansPipeline:
    """4D-Humans 完整流程封装"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.tools_dir = self.project_root / "tools"
        self.smoothnet_dir = self.project_root / "SmoothNet"
        
    def run_tracking(
        self,
        video_path: str,
        output_dir: str,
        task_id: str,
        progress_callback: Optional[Callable] = None
    ) -> PipelineResult:
        """执行 4D-Humans 追踪"""
        cmd = [
            "python", "track.py",
            f'video.source="{video_path}"',
            f'video.output_dir="{output_dir}"',
            "video.extract_video=True"
        ]
        
        result = self._run_command(
            cmd=cmd,
            timeout=settings.TRACKING_TIMEOUT,
            step_name=ProcessStep.TRACKING,
            cwd=self.project_root
        )
        
        if result.success:
            pkl_path = Path(output_dir) / "results" / f"demo_{task_id}.pkl"
            result.output_path = str(pkl_path)
        
        return result
    
    def extract_track(
        self,
        pkl_path: str,
        track_id: int,
        output_path: str,
        fps: int = 30,
        progress_callback: Optional[Callable] = None
    ) -> PipelineResult:
        """提取单个 Track"""
        cmd = [
            "python", str(self.tools_dir / "extract_track_for_tid.py"),
            "--pkl", pkl_path,
            "--tid", str(track_id),
            "--out", output_path,
            "--fps", str(fps)
        ]
        
        result = self._run_command(
            cmd=cmd,
            timeout=settings.EXTRACTION_TIMEOUT,
            step_name=ProcessStep.TRACK_EXTRACTION,
            cwd=self.project_root
        )
        
        if result.success:
            result.output_path = output_path
        
        return result
    
    def smooth_track(
        self,
        input_npz: str,
        output_npz: str,
        checkpoint: str,
        strength: float = 1.0,
        window: int = 9,
        progress_callback: Optional[Callable] = None
    ) -> PipelineResult:
        """应用 SmoothNet 平滑"""
        # 设置 PYTHONPATH
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{self.smoothnet_dir}:{self.smoothnet_dir}/lib:{env.get('PYTHONPATH', '')}"
        
        cmd = [
            "python", str(self.tools_dir / "adapt_smoothnet.py"),
            "--npz", input_npz,
            "--ckpt", checkpoint,
            "--out", output_npz,
            "--win", str(window),
            "--strength", str(strength)
        ]
        
        result = self._run_command(
            cmd=cmd,
            timeout=settings.SMOOTHING_TIMEOUT,
            step_name=ProcessStep.SMOOTHING,
            cwd=self.project_root,
            env=env
        )
        
        if result.success:
            result.output_path = output_npz
        
        return result
    
    def export_fbx(
        self,
        input_npz: str,
        output_fbx: str,
        fps: int = 30,
        with_root_motion: bool = True,
        cam_scale: float = 1.0,
        progress_callback: Optional[Callable] = None
    ) -> PipelineResult:
        """导出 FBX"""
        cmd = [
            "blender", "-b",
            "-P", str(self.tools_dir / "blender" / "smplx_npz_to_fbx.py"),
            "--",
            "--npz", input_npz,
            "--out", output_fbx,
            "--fps", str(fps),
            "--cam-scale", str(cam_scale)
        ]
        
        if with_root_motion:
            cmd.append("--with-root-motion")
        
        result = self._run_command(
            cmd=cmd,
            timeout=settings.FBX_EXPORT_TIMEOUT,
            step_name=ProcessStep.FBX_EXPORT,
            cwd=self.project_root
        )
        
        if result.success:
            result.output_path = output_fbx
        
        return result
    
    def run_full_pipeline(
        self,
        task_id: str,
        video_path: str,
        track_mode: str = "auto",
        track_id: Optional[int] = None,
        enable_smoothing: bool = True,
        smoothing_strength: float = 1.0,
        with_root_motion: bool = True,
        fps: int = 30,
        progress_callback: Optional[Callable[[str, float, Optional[str]], None]] = None
    ) -> Dict:
        """执行完整流程"""
        logger.info(f"[Pipeline] Starting full pipeline for task: {task_id}")
        
        # 准备路径
        output_dir = Path(settings.OUTPUT_DIR)
        results_dir = output_dir / "results"
        task_results_dir = Path(settings.RESULT_DIR) / task_id
        task_results_dir.mkdir(parents=True, exist_ok=True)
        
        pkl_path = results_dir / f"demo_{task_id}.pkl"
        npz_path = results_dir / f"demo_{task_id}_tid{{tid}}.npz"
        smoothed_npz = results_dir / f"demo_{task_id}_tid{{tid}}_smoothed.npz"
        final_fbx = task_results_dir / "animation.fbx"
        
        intermediate_files = {}
        step_durations = {}
        
        try:
            # Step 1: Tracking
            if progress_callback:
                progress_callback(ProcessStep.TRACKING, 0, None)
            
            result = self.run_tracking(video_path, str(output_dir), task_id)
            step_durations[ProcessStep.TRACKING] = result.duration
            
            if not result.success:
                return self._build_error_result(result, intermediate_files, step_durations)
            
            intermediate_files["tracklets"] = str(pkl_path)
            intermediate_files["visualization"] = str(output_dir / f"PHALP_{task_id}.mp4")
            
            if progress_callback:
                progress_callback(ProcessStep.TRACKING, 100, None)
            
            # Step 2: 确定 Track ID
            if track_mode == "auto" or track_id is None:
                # 自动选择帧数最多的 Track
                selected_tid = self._get_primary_track_id(str(pkl_path))
            else:
                selected_tid = track_id
            
            # Step 3: Extract Track
            if progress_callback:
                progress_callback(ProcessStep.TRACK_EXTRACTION, 0, None)
            
            npz_output = str(npz_path).format(tid=selected_tid)
            result = self.extract_track(str(pkl_path), selected_tid, npz_output, fps)
            step_durations[ProcessStep.TRACK_EXTRACTION] = result.duration
            
            if not result.success:
                return self._build_error_result(result, intermediate_files, step_durations)
            
            intermediate_files["track_npz"] = npz_output
            
            if progress_callback:
                progress_callback(ProcessStep.TRACK_EXTRACTION, 100, None)
            
            # Step 4: Smoothing (可选)
            smooth_input = npz_output
            if enable_smoothing:
                if progress_callback:
                    progress_callback(ProcessStep.SMOOTHING, 0, None)
                
                smoothed_output = str(smoothed_npz).format(tid=selected_tid)
                checkpoint = str(self.smoothnet_dir / "data/checkpoints/pw3d_spin_3D/checkpoint_8.pth.tar")
                
                result = self.smooth_track(
                    npz_output,
                    smoothed_output,
                    checkpoint,
                    strength=smoothing_strength
                )
                step_durations[ProcessStep.SMOOTHING] = result.duration
                
                if not result.success:
                    # 平滑失败不致命，使用原始数据
                    logger.warning(f"Smoothing failed, using original track: {result.error}")
                else:
                    smooth_input = smoothed_output
                    intermediate_files["smoothed_npz"] = smoothed_output
                
                if progress_callback:
                    progress_callback(ProcessStep.SMOOTHING, 100, None)
            else:
                step_durations[ProcessStep.SMOOTHING] = 0
            
            # Step 5: Export FBX
            if progress_callback:
                progress_callback(ProcessStep.FBX_EXPORT, 0, None)
            
            result = self.export_fbx(
                smooth_input,
                str(final_fbx),
                fps=fps,
                with_root_motion=with_root_motion
            )
            step_durations[ProcessStep.FBX_EXPORT] = result.duration
            
            if not result.success:
                return self._build_error_result(result, intermediate_files, step_durations)
            
            if progress_callback:
                progress_callback(ProcessStep.FBX_EXPORT, 100, None)
            
            # Step 6: Packaging (检查是否有 .fbm 文件夹)
            if progress_callback:
                progress_callback(ProcessStep.PACKAGING, 0, None)
            
            fbm_dir = final_fbx.parent / f"{final_fbx.stem}.fbm"
            final_output = str(final_fbx)
            
            if fbm_dir.exists() and fbm_dir.is_dir():
                # 打包成 ZIP
                zip_path = task_results_dir / "animation.zip"
                self._create_zip(final_fbx, fbm_dir, zip_path)
                final_output = str(zip_path)
            
            step_durations[ProcessStep.PACKAGING] = 0.5
            
            if progress_callback:
                progress_callback(ProcessStep.PACKAGING, 100, None)
            
            logger.info(f"[Pipeline] Successfully completed task: {task_id}")
            return {
                "success": True,
                "final_path": final_output,
                "intermediate_files": intermediate_files,
                "selected_track_id": selected_tid,
                "error": None,
                "error_code": None,
                "step_durations": step_durations
            }
            
        except Exception as e:
            logger.exception(f"[Pipeline] Unexpected error in task: {task_id}")
            return {
                "success": False,
                "final_path": None,
                "intermediate_files": intermediate_files,
                "error": str(e),
                "error_code": ErrorCode.INTERNAL_ERROR,
                "step_durations": step_durations
            }
    
    def _get_primary_track_id(self, pkl_path: str) -> int:
        """获取主要 Track ID（帧数最多）"""
        import joblib
        data = joblib.load(pkl_path)
        
        track_counts = {}
        for frame_data in data.values():
            if isinstance(frame_data, dict):
                tids = frame_data.get("tracked_ids") or frame_data.get("tid") or []
                for tid in tids:
                    if tid is not None:
                        track_counts[int(tid)] = track_counts.get(int(tid), 0) + 1
        
        if not track_counts:
            raise ValueError("No tracks found in PKL file")
        
        # 返回帧数最多的 Track ID
        return max(track_counts.items(), key=lambda x: x[1])[0]
```

### 2. 配置文件 (`api/config.py`)

```python
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "4D-Humans MoCap API"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # 路径配置
    PROJECT_ROOT: Path = Path(__file__).parent.parent
    UPLOAD_DIR: Path = PROJECT_ROOT / "uploads"
    RESULT_DIR: Path = PROJECT_ROOT / "results"
    OUTPUT_DIR: Path = PROJECT_ROOT / "outputs"
    TEMP_DIR: Path = PROJECT_ROOT / "tmp"
    LOG_DIR: Path = PROJECT_ROOT / "logs"
    
    # 业务配置
    MAX_FILE_SIZE: int = 500 * 1024 * 1024  # 500MB
    MAX_VIDEO_DURATION: int = 120  # 120秒
    MAX_QUEUE_SIZE: int = 10
    ALLOWED_VIDEO_FORMATS: list = [".mp4", ".avi", ".mov", ".mkv"]
    
    # 超时配置（秒）
    TASK_TIMEOUT: int = 600
    TRACKING_TIMEOUT: int = 300
    EXTRACTION_TIMEOUT: int = 30
    SMOOTHING_TIMEOUT: int = 60
    FBX_EXPORT_TIMEOUT: int = 60
    
    # 清理配置
    AUTO_CLEANUP_ENABLED: bool = True
    CLEANUP_INTERVAL_HOURS: int = 6
    CLEANUP_COMPLETED_HOURS: int = 24
    CLEANUP_FAILED_HOURS: int = 48
    
    # SmoothNet 配置
    SMOOTHNET_CHECKPOINT: str = "SmoothNet/data/checkpoints/pw3d_spin_3D/checkpoint_8.pth.tar"
    DEFAULT_SMOOTHING_STRENGTH: float = 1.0
    DEFAULT_SMOOTHING_WINDOW: int = 9
    
    # 默认参数
    DEFAULT_FPS: int = 30
    DEFAULT_WITH_ROOT_MOTION: bool = True
    DEFAULT_CAM_SCALE: float = 1.0
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

def ensure_directories():
    """确保所有必要的目录存在"""
    for dir_path in [
        settings.UPLOAD_DIR,
        settings.RESULT_DIR,
        settings.OUTPUT_DIR,
        settings.TEMP_DIR,
        settings.LOG_DIR
    ]:
        dir_path.mkdir(parents=True, exist_ok=True)
```

---

## ❓ 需要确认的问题

### 1. 多人场景处理策略
**问题**: 当视频中有多个人时，如何处理？

**选项 A（推荐）**: 自动模式 + 手动选择
```
- 默认: 自动选择帧数最多的 Track（主角）
- 可选: 用户查看所有 Tracks，选择特定 Track ID 重新导出
- API: GET /api/v1/mocap/{task_id}/tracks
- API: POST /api/v1/mocap/{task_id}/re-export
```

**选项 B**: 导出所有人
```
- 一次性导出所有 Track IDs 为多个 FBX
- 打包成 ZIP 返回
- 文件命名: animation_track1.fbx, animation_track2.fbx
```

**选项 C**: 让用户在上传时指定
```
- 增加参数: track_selection: "primary" | "all" | "manual"
- manual 模式需要先运行 tracking，然后返回 Track 列表让用户选择
```

**您的选择**: _______________

---

### 2. 视频预处理
**问题**: 是否需要视频预处理（裁剪、降分辨率、提取关键帧）？

**考虑因素**:
- 长视频会导致处理时间过长
- 高分辨率视频占用更多 GPU 显存
- 4D-Humans 对视频质量有要求

**建议**:
```python
# 配置项
MAX_VIDEO_DURATION: int = 120  # 最大120秒
MAX_VIDEO_RESOLUTION: tuple = (1920, 1080)  # 最大分辨率
AUTO_RESIZE: bool = True  # 自动降分辨率
```

**您的选择**: _______________

---

### 3. SmoothNet 检查点
**问题**: SmoothNet 需要预训练模型，如何处理？

**选项 A（推荐）**: 自动下载
```python
# 首次运行时自动下载到 SmoothNet/data/checkpoints/
# 需要网络连接
```

**选项 B**: 手动下载
```bash
# 在 README 中说明下载步骤
# 用户需要手动下载并放置到指定目录
```

**选项 C**: Fallback 机制
```python
# 如果 SmoothNet 不可用，使用 Moving Average 降级
# 已在 adapt_smoothnet.py 中实现
```

**您的选择**: _______________

---

### 4. Blender 依赖
**问题**: Blender 需要在系统中安装，如何确保可用？

**选项 A**: 检查并提示
```python
# 启动时检查 blender 是否在 PATH 中
# 如果不存在，返回错误提示
```

**选项 B**: Docker 部署
```dockerfile
# 在 Docker 镜像中预装 Blender
# 适合生产环境
```

**选项 C**: 使用 bpy 模块
```python
# 直接 import bpy（Blender as a Python module）
# 需要特殊安装
```

**您的选择**: _______________

---

### 5. GPU 资源管理
**问题**: 如何处理 GPU 显存不足的情况？

**当前策略**:
```python
# 单任务队列，一次只处理一个视频
# 如果 GPU OOM，任务失败，返回错误
```

**改进选项**:
- 增加 GPU 监控，任务开始前检查显存
- 支持 CPU 降级（速度慢但不会失败）
- 支持多 GPU 并行处理

**您的选择**: _______________

---

### 6. 中间文件保留策略
**问题**: 中间文件（PKL、NPZ、可视化视频）如何处理？

**选项 A（推荐）**: 可选保留
```python
# keep_intermediate: bool 参数
# true: 保留所有中间文件，可通过 API 下载
# false: 只保留最终 FBX，其他自动清理
```

**选项 B**: 全部保留
```python
# 所有中间文件都保留
# 定期清理（24小时后）
```

**选项 C**: 全部删除
```python
# 只保留最终 FBX
# 节省磁盘空间
```

**您的选择**: _______________

---

### 7. 错误处理和重试
**问题**: 任务失败后如何处理？

**建议机制**:
```python
# 1. 详细错误日志
#    - 记录每个步骤的 stdout/stderr
#    - 提供 /api/v1/mocap/{task_id}/logs 端点

# 2. 部分重试
#    - 如果只是平滑失败，跳过平滑继续导出
#    - 如果是 tracking 失败，整个任务失败

# 3. 手动重试
#    - 提供 POST /api/v1/mocap/{task_id}/retry 端点
#    - 从失败步骤重新开始
```

**您的选择**: _______________

---

### 8. 输出格式
**问题**: 是否支持除 FBX 外的其他格式？

**可选格式**:
- FBX（当前）
- BVH（更通用，但信息较少）
- GLB/GLTF（Web 友好）
- USD（电影级）

**建议**: 先支持 FBX，后续可扩展

**您的选择**: _______________

---

### 9. 认证和权限
**问题**: API 是否需要认证？

**选项 A**: 无认证（开发/内网）
```python
# 适合内部使用或开发环境
```

**选项 B**: API Key
```python
# 简单的 API Key 认证
# Header: X-API-Key: your-key
```

**选项 C**: OAuth2/JWT
```python
# 完整的用户系统
# 适合生产环境
```

**您的选择**: _______________

---

### 10. 部署方式
**问题**: 推荐的部署方式？

**选项 A（推荐）**: Systemd + Nginx
```bash
# 类似 UniRig 的部署方式
# 适合单服务器部署
```

**选项 B**: Docker Compose
```yaml
# 容器化部署
# 包含 API + GPU 支持
```

**选项 C**: Kubernetes
```yaml
# 大规模部署
# 支持自动扩缩容
```

**您的选择**: _______________

---

## 📦 可直接复用的 UniRig 代码

### 完全复用（无需修改）
```
api/
├── models/__init__.py          ✅ 数据模型基础结构
├── models/response.py          ✅ 响应模型（TaskResponse, StatusResponse 等）
├── utils/__init__.py           ✅ 工具模块初始化
├── utils/file_handler.py       ✅ 文件处理（上传、验证、清理）
├── utils/gpu_monitor.py        ✅ GPU 监控
├── utils/logger.py             ✅ 日志配置
├── services/task_manager.py    ✅ 任务管理器（90%复用）
├── services/worker.py          ✅ 后台工作器
└── routers/admin.py            ✅ 管理端点
```

### 需要修改（适配业务逻辑）
```
api/
├── main.py                     🔧 修改应用名称和配置
├── config.py                   🔧 修改配置项（路径、超时等）
├── constants.py                🔧 修改步骤定义和错误码
├── models/request.py           🔧 修改请求参数
├── services/pipeline.py        🔧 完全重写（核心业务逻辑）
└── routers/mocap.py            🔧 修改路由逻辑（对应新业务）
```

---

## 🚀 实施步骤

### Phase 1: 基础架构（1-2天）
1. ✅ 创建 `api/` 目录结构
2. ✅ 复用 UniRig 的基础代码（models, utils, task_manager, worker）
3. ✅ 修改 `config.py` 和 `constants.py`
4. ✅ 编写 `requirements-api.txt`
5. ✅ 测试基础框架（健康检查、队列管理）

### Phase 2: Pipeline 实现（2-3天）
1. ✅ 实现 `FourDHumansPipeline` 类
2. ✅ 封装 `track.py` 调用
3. ✅ 封装 `tools/` 脚本调用
4. ✅ 实现进度回调机制
5. ✅ 测试完整流程

### Phase 3: API 端点（1-2天）
1. ✅ 实现 `POST /api/v1/mocap`（创建任务）
2. ✅ 实现 `GET /api/v1/mocap/{task_id}`（查询状态）
3. ✅ 实现 `GET /api/v1/mocap/{task_id}/download`（下载结果）
4. ✅ 实现多人场景相关端点
5. ✅ 测试所有端点

### Phase 4: 优化和文档（1-2天）
1. ✅ 错误处理和日志优化
2. ✅ 编写 API 文档（README_API.md）
3. ✅ 编写快速开始指南（QUICKSTART_API.md）
4. ✅ 编写部署指南（DEPLOYMENT.md）
5. ✅ 编写测试脚本

### Phase 5: 测试和部署（1-2天）
1. ✅ 端到端测试
2. ✅ 压力测试（多任务并发）
3. ✅ GPU OOM 测试
4. ✅ 部署到服务器
5. ✅ 监控和日志验证

---

## 📝 总结

### 核心改动
1. **Pipeline 逻辑**: 从 3D 模型绑骨 → 视频动作捕捉
2. **处理步骤**: 4步（skeleton/skin/merge/rename） → 6步（track/extract/smooth/export/package）
3. **输入格式**: GLB/FBX/OBJ → MP4/AVI/MOV
4. **输出格式**: 绑骨模型 → 动画 FBX
5. **处理时间**: ~2分钟 → ~4分钟（取决于视频长度）

### 技术栈
- FastAPI（Web 框架）
- PyTorch（4D-Humans + SmoothNet）
- Blender（FBX 导出）
- joblib（PKL 处理）
- numpy（数据处理）

### 预期性能
- 单任务处理时间: 3-5分钟（30秒视频）
- 并发能力: 1个 GPU 同时处理 1个任务
- 队列容量: 10个任务
- 磁盘占用: ~500MB/任务（包含中间文件）

---

## 🤔 等待您的反馈

请确认以上 10 个问题的选择，我将根据您的决策开始实施。

如果有任何疑问或需要调整的地方，请告诉我！

