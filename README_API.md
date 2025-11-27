# 4D-Humans MoCap API

基于 4D-Humans 的视频动作捕捉 API 服务，从视频生成 Unity Humanoid 兼容的 FBX 动画文件。

## ✨ 特性

- 📹 **视频输入**：支持 MP4、AVI、MOV、MKV 格式
- 🎯 **自动追踪**：基于 PHALP 的多人追踪，自动选择最长轨迹
- 🔄 **时序平滑**：使用 SmoothNet 消除抖动
- 🎨 **Unity 兼容**：导出 Unity Humanoid 兼容的 FBX 文件
- 📊 **进度追踪**：实时查询任务状态和进度
- 🔧 **灵活配置**：支持自定义 FPS、根运动、平滑参数等

## 📁 文件类型支持

### API 接受的文件类型

**输入文件**（上传）：
- `.mp4` - MPEG-4 视频
- `.avi` - AVI 视频
- `.mov` - QuickTime 视频
- `.mkv` - Matroska 视频

**文件名格式限制**：
- 只允许字母、数字、点（`.`）、下划线（`_`）、连字符（`-`）
- 必须包含文件扩展名
- 示例：`video.mp4` ✅ | `video file.mp4` ❌ | `video@test.mp4` ❌

### 项目处理的文件类型

**输入**：
- 视频文件：`.mp4`, `.avi`, `.mov`, `.mkv`

**中间文件**（自动生成，无需手动处理）：
- `.pkl` - PHALP 追踪结果（存储在 `outputs/results/`）
- `.npz` - NumPy 压缩格式
  - 提取的轨迹数据：`{task_id}_tid{track_id}_extracted.npz`
  - 平滑后的数据：`{task_id}_smoothed.npz`
  - 存储在 `tmp/` 目录

**输出文件**：
- `.fbx` - FBX 动画文件（最终输出，Unity Humanoid 兼容）
- `.fbm` - FBX 材质文件夹（伴随 FBX 文件自动生成，包含纹理等资源）

**其他文件**（可选）：
- `.png`, `.jpg` - 视频缩略图、渲染图片（如果启用）
- `.obj` - 3D 网格文件（某些处理步骤可能生成）

### 文件限制

**文件大小**：
- 最大文件大小：**500MB**（`MAX_FILE_SIZE`）
- 磁盘空间要求：文件大小 × 3（`DISK_SPACE_MULTIPLIER`）

**视频限制**：
- 最大时长：**30 秒**（`MAX_VIDEO_DURATION`）
- 最大分辨率：**2048 像素**（最大边长，`MAX_VIDEO_RESOLUTION`）
- 最小帧数：**10 帧**（`MIN_VIDEO_FRAMES`）
- 必须可被 OpenCV 读取（`cv2.VideoCapture`）

**文件验证流程**：
1. **文件名格式验证**：检查文件名是否符合安全规范
2. **扩展名验证**：检查是否为支持的视频格式
3. **文件大小验证**：检查是否超过 500MB
4. **视频内容验证**：
   - 能否被 OpenCV 打开
   - 分辨率是否超限
   - 时长是否超限
   - 帧数是否足够

## 📋 系统要求

### 必需依赖

1. **Blender 3.0+**
   - 用于 FBX 导出
   - 必须在 PATH 中或通过 `BLENDER_PATH` 配置

2. **SmoothNet 检查点**
   - 必须存在且可加载
   - 配置路径：`SMOOTHNET_CHECKPOINT`

3. **GPU**
   - NVIDIA GPU with CUDA support
   - 至少 8GB 显存（推荐）

### Python 依赖

```bash
# 安装 API 依赖
pip install -r requirements-api.txt

# 安装主项目依赖
pip install -r requirements.txt
```

## 🚀 快速开始

### 1. 配置环境

复制环境变量示例文件：

```bash
cp deploy/env.example .env
```

编辑 `.env` 文件，配置必要参数：

```bash
# Blender 路径（如果不在 PATH 中）
BLENDER_PATH=/Applications/Blender.app/Contents/MacOS/blender

# SmoothNet 检查点路径（必需）
SMOOTHNET_CHECKPOINT=smoothnet/data/checkpoints/pw3d_spin_3D/checkpoint_8.pth.tar

# 视频限制
MAX_VIDEO_DURATION=30          # 30秒
MAX_VIDEO_RESOLUTION=2048      # 2K
```

### 2. 启动服务

```bash
# 开发模式
python -m api.main

# 或使用 uvicorn
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. 测试 API

访问 API 文档：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

使用测试脚本：

```bash
# 上传视频并创建任务
python scripts/test_api.py example_data/videos/gymnasts.mp4

# 查询任务状态
python scripts/test_api.py --task-id <task_id>
```

## 📖 API 端点

### MoCap API

#### 创建任务

```http
POST /api/v1/mocap/tasks
Content-Type: multipart/form-data

video: <video_file>
track_id: <int> (可选，≥0，默认自动选择最长轨迹)
fps: <int> (可选，1-120，默认30)
with_root_motion: <bool> (可选，默认true)
cam_scale: <float> (可选，0.0-10.0，默认1.0)
smoothing_strength: <float> (可选，0.0-2.0，默认1.0)
smoothing_window: <int> (可选，3-21，默认9)
smoothing_ema: <float> (可选，0.0-1.0，默认0.2)
```

**响应**：

```json
{
  "task_id": "uuid",
  "status": "queued",
  "current_step": null,
  "progress": 0,
  "fbx_url": null,
  "created_at": "2024-01-01T00:00:00",
  "started_at": null,
  "completed_at": null,
  "error_code": null,
  "error_message": null,
  "processing_time": null
}
```

**错误响应**：
- `400`: 参数验证失败、文件格式无效、视频时长/分辨率超限
- `413`: 文件过大
- `429`: 请求频率超限（10次/分钟，100次/小时）
- `503`: 任务队列已满

#### 查询任务状态

```http
GET /api/v1/mocap/tasks/{task_id}
```

**响应**：

```json
{
  "task_id": "uuid",
  "status": "completed",
  "current_step": null,
  "progress": 100,
  "fbx_url": "/api/v1/mocap/tasks/{task_id}/download",
  "created_at": "2024-01-01T00:00:00",
  "started_at": "2024-01-01T00:00:05",
  "completed_at": "2024-01-01T00:05:00",
  "error_code": null,
  "error_message": null,
  "processing_time": 295.5
}
```

**任务状态**：
- `queued`: 排队中
- `processing`: 处理中
- `completed`: 已完成
- `failed`: 失败

**处理步骤** (`current_step`)：
- `video_upload`: 视频上传
- `tracking`: 人物追踪
- `track_extraction`: 轨迹提取
- `smoothing`: 时序平滑
- `fbx_export`: FBX 导出
- `packaging`: 打包完成

#### 下载 FBX

```http
GET /api/v1/mocap/tasks/{task_id}/download
```

返回 FBX 文件。

#### 删除任务

```http
DELETE /api/v1/mocap/tasks/{task_id}?keep_intermediate=false
```

**参数**：
- `keep_intermediate`: 是否保留中间文件（默认 `false`）

**响应**：

```json
{
  "message": "Task {task_id} deleted successfully"
}
```

#### 获取任务列表

```http
GET /api/v1/mocap/tasks
```

**响应**：

```json
{
  "tasks": [
    {
      "task_id": "uuid",
      "status": "completed",
      "current_step": null,
      "progress": 100,
      "fbx_url": "/api/v1/mocap/tasks/{task_id}/download",
      "created_at": "2024-01-01T00:00:00",
      "started_at": "2024-01-01T00:00:05",
      "completed_at": "2024-01-01T00:05:00",
      "error_code": null,
      "error_message": null,
      "processing_time": 295.5
    }
  ],
  "total": 1
}
```

### 管理 API

#### 健康检查

```http
GET /health
```

简单健康检查（用于负载均衡器）。

**响应**：

```json
{
  "status": "healthy",
  "active_tasks": 1,
  "queued_tasks": 2,
  "disk_usage_percent": 45.2,
  "warnings": []
}
```

```http
GET /api/v1/admin/health
```

详细健康检查（包含 GPU、磁盘、队列信息）。

**响应**：

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime": 3600.5,
  "disk": {
    "total_gb": 500.0,
    "used_gb": 225.0,
    "usage_percent": 45.0
  },
  "gpu": {
    "available": true,
    "memory_free_mb": 8192,
    "temperature": 65
  },
  "queue": {
    "current_task_id": "uuid",
    "queued_count": 2,
    "max_size": 10
  },
  "stats": {
    "total_tasks": 100,
    "completed_tasks": 95,
    "failed_tasks": 5
  }
}
```

#### 统计信息

```http
GET /api/v1/admin/stats
```

#### 队列信息

```http
GET /api/v1/admin/queue
```

#### 手动清理

```http
POST /api/v1/admin/cleanup
```

**响应**：

```json
{
  "message": "Cleaned up 5 items",
  "cleaned_tasks": 2,
  "cleaned_demo_files": 1,
  "cleaned_test_files": 1,
  "cleaned_log_files": 1,
  "total_cleaned": 5
}
```

## 🔧 配置说明

### 视频限制

```bash
MAX_FILE_SIZE=524288000        # 500MB（最大文件大小）
MAX_VIDEO_DURATION=30          # 30秒（最大视频时长）
MAX_VIDEO_RESOLUTION=2048      # 2K（最大分辨率，最大边长）
MIN_VIDEO_FRAMES=10            # 最小帧数
ALLOWED_VIDEO_FORMATS=.mp4,.avi,.mov,.mkv  # 支持的视频格式
```

**支持的视频格式**：
- `.mp4` - MPEG-4（推荐，兼容性最好）
- `.avi` - AVI 容器
- `.mov` - QuickTime
- `.mkv` - Matroska

**视频编码建议**：
- 推荐使用 H.264 编码（`.mp4`）
- 确保视频可以被 OpenCV 读取
- 避免使用过于冷门的编码格式

### 队列配置

```bash
MAX_QUEUE_SIZE=10              # 最大队列长度
```

### 请求频率限制

```bash
RATE_LIMIT_ENABLED=true        # 启用频率限制
RATE_LIMIT_PER_MINUTE=10       # 每分钟最多 10 个请求
RATE_LIMIT_PER_HOUR=100       # 每小时最多 100 个请求
```

### 超时配置

```bash
TASK_TIMEOUT=1200              # 总超时（20分钟）
TRACKING_TIMEOUT=900           # 追踪超时（15分钟）
EXTRACTION_TIMEOUT=60          # 提取超时（1分钟）
SMOOTHING_TIMEOUT=120          # 平滑超时（2分钟）
FBX_EXPORT_TIMEOUT=120         # 导出超时（2分钟）
```

### 清理配置

```bash
# API 任务文件清理
AUTO_CLEANUP_ENABLED=true
CLEANUP_INTERVAL_HOURS=6       # 每6小时清理一次
CLEANUP_COMPLETED_HOURS=72     # 完成任务保留3天
CLEANUP_FAILED_HOURS=72        # 失败任务保留3天

# 开发/演示文件清理
CLEANUP_DEMO_FILES_ENABLED=true
CLEANUP_DEMO_FILES_DAYS=30     # 演示文件保留30天
CLEANUP_TEST_FILES_ENABLED=true
CLEANUP_TEST_FILES_DAYS=7      # 测试文件保留7天
CLEANUP_LOG_FILES_DAYS=7       # 日志文件保留7天
```

### SmoothNet 配置

```bash
DEFAULT_SMOOTHING_STRENGTH=1.0
DEFAULT_SMOOTHING_WINDOW=9
DEFAULT_SMOOTHING_EMA=0.2
```

### GPU 监控配置

```bash
GPU_MIN_FREE_MEMORY_MB=8192   # 最小可用显存（8GB）
GPU_MAX_TEMPERATURE=85        # 最大温度（摄氏度）
```

### 文件处理配置

```bash
DISK_SPACE_MULTIPLIER=3       # 磁盘空间倍数（文件大小 * 倍数）
FILE_UPLOAD_CHUNK_SIZE=8192   # 文件上传块大小（8KB）
MIN_VIDEO_FRAMES=10           # 最小视频帧数
PROCESS_KILL_TIMEOUT=5        # 进程终止等待超时（秒）
```

## 🐛 故障排除

### 1. 服务无法启动

**错误**: `Blender not found`

**解决**:
- 安装 Blender 3.0+: https://www.blender.org/download/
- 确保 Blender 在 PATH 中，或设置 `BLENDER_PATH`

**错误**: `SmoothNet checkpoint not found`

**解决**:
- 下载 SmoothNet 检查点
- 更新 `.env` 中的 `SMOOTHNET_CHECKPOINT` 路径

### 2. API 错误码

**通用错误**：
- `INTERNAL_ERROR`: 服务器内部错误
- `INVALID_REQUEST`: 请求参数无效

**文件相关**：
- `INVALID_FILE_FORMAT`: 文件格式不支持
- `FILE_TOO_LARGE`: 文件过大
- `VIDEO_TOO_LONG`: 视频时长超限
- `VIDEO_RESOLUTION_TOO_HIGH`: 视频分辨率过高

**任务相关**：
- `TASK_NOT_FOUND`: 任务不存在
- `TASK_TIMEOUT`: 任务超时
- `QUEUE_FULL`: 任务队列已满
- `RATE_LIMIT_EXCEEDED`: 请求频率超限

**处理步骤错误**：
- `TRACKING_FAILED`: 追踪失败
- `TRACK_EXTRACTION_FAILED`: 轨迹提取失败
- `NO_TRACKS_FOUND`: 未找到轨迹
- `SMOOTHING_FAILED`: 平滑失败
- `FBX_EXPORT_FAILED`: FBX 导出失败

**资源错误**：
- `GPU_OUT_OF_MEMORY`: GPU 显存不足
- `DISK_FULL`: 磁盘空间不足

**依赖错误**：
- `BLENDER_NOT_FOUND`: Blender 未找到
- `SMOOTHNET_NOT_AVAILABLE`: SmoothNet 不可用

### 3. 任务失败

**错误**: `CUDA out of memory` / `GPU_OUT_OF_MEMORY`

**解决**:
- 降低视频分辨率
- 减少队列大小（一次只处理一个任务）
- 增加 GPU 显存
- 检查 GPU 温度是否过高

**错误**: `Video too long` / `VIDEO_TOO_LONG`

**解决**:
- 视频时长限制为 30 秒（默认）
- 裁剪视频或调整 `MAX_VIDEO_DURATION`

**错误**: `RATE_LIMIT_EXCEEDED`

**解决**:
- 请求频率超限（10次/分钟，100次/小时）
- 等待一段时间后重试
- 如需提高限制，调整 `RATE_LIMIT_PER_MINUTE` 和 `RATE_LIMIT_PER_HOUR`

### 4. 查看日志

```bash
# 查看应用日志
tail -f logs/4d-humans-api.log

# 查看错误日志
tail -f logs/4d-humans-error.log
```

## 📦 部署

### 使用 Systemd（推荐）

创建服务文件：

```bash
sudo cp deploy/4d-humans-api.service /etc/systemd/system/
# 编辑服务文件，修改 User、WorkingDirectory、ExecStart 等路径
sudo nano /etc/systemd/system/4d-humans-api.service
sudo systemctl daemon-reload
sudo systemctl enable 4d-humans-api
sudo systemctl start 4d-humans-api
```

查看状态：

```bash
sudo systemctl status 4d-humans-api
```

**服务名称**: `4d-humans-api`

详细配置说明请参考 [DEPLOY_REMOTE.md](DEPLOY_REMOTE.md#systemd-服务配置)

### 使用 Nginx 反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 500M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 超时设置（处理长时间运行的任务）
        proxy_read_timeout 600s;
        proxy_connect_timeout 600s;
        proxy_send_timeout 600s;
    }
}
```

## 📝 开发

### 项目结构

```
4D-Humans/
├── api/                    # FastAPI 应用
│   ├── __init__.py
│   ├── main.py             # FastAPI 主应用
│   ├── config.py           # 配置管理
│   ├── constants.py        # 常量定义
│   ├── models/             # 数据模型
│   │   ├── task.py
│   │   └── error.py
│   ├── routers/            # API 路由
│   │   ├── mocap.py        # MoCap API
│   │   └── admin.py        # 管理 API
│   ├── services/           # 业务逻辑
│   │   ├── pipeline.py     # 4D-Humans Pipeline
│   │   ├── task_manager.py # 任务管理（含清理机制）
│   │   └── worker.py       # 后台工作器
│   └── utils/              # 工具函数
│       ├── logger.py
│       ├── file_handler.py
│       ├── gpu_monitor.py
│       ├── video_validator.py
│       └── dependency_checker.py
├── phalp/                  # PHALP submodule
├── smoothnet/              # SmoothNet submodule
├── hmr2/                   # HMR2 模型代码
├── tools/                   # 工具脚本
├── scripts/                 # 辅助脚本
│   ├── start_api.sh
│   ├── test_api.py
│   └── cleanup_old_files.sh
└── deploy/                  # 部署配置
```

### 添加新功能

1. 在 `api/routers/` 中添加新路由
2. 在 `api/services/` 中添加业务逻辑
3. 在 `api/models/` 中定义数据模型
4. 更新 `api/main.py` 注册路由

## 📄 许可证

本项目基于 4D-Humans 项目，遵循其原始许可证。

## 🙏 致谢

- [4D-Humans](https://github.com/shubham-goel/4D-Humans)
- [PHALP](https://github.com/brjathu/PHALP)
- [SmoothNet](https://github.com/cure-lab/SmoothNet)
- [UniRig](https://github.com/your-repo/UniRig) - API 架构参考

