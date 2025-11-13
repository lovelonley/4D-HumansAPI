# 4D-Humans MoCap API

基于 4D-Humans 的视频动作捕捉 API 服务，从视频生成 Unity Humanoid 兼容的 FBX 动画文件。

## ✨ 特性

- 📹 **视频输入**：支持 MP4、AVI、MOV、MKV 格式
- 🎯 **自动追踪**：基于 PHALP 的多人追踪，自动选择最长轨迹
- 🔄 **时序平滑**：使用 SmoothNet 消除抖动
- 🎨 **Unity 兼容**：导出 Unity Humanoid 兼容的 FBX 文件
- 📊 **进度追踪**：实时查询任务状态和进度
- 🔧 **灵活配置**：支持自定义 FPS、根运动、平滑参数等

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
track_id: <int> (可选)
fps: <int> (可选，默认30)
with_root_motion: <bool> (可选，默认true)
cam_scale: <float> (可选，默认1.0)
smoothing_strength: <float> (可选，默认1.0)
smoothing_window: <int> (可选，默认9)
smoothing_ema: <float> (可选，默认0.2)
```

**响应**：

```json
{
  "task_id": "uuid",
  "status": "queued",
  "progress": 0,
  "created_at": "2024-01-01T00:00:00"
}
```

#### 查询任务状态

```http
GET /api/v1/mocap/tasks/{task_id}
```

**响应**：

```json
{
  "task_id": "uuid",
  "status": "completed",
  "progress": 100,
  "fbx_url": "/api/v1/mocap/tasks/{task_id}/download",
  "created_at": "2024-01-01T00:00:00",
  "started_at": "2024-01-01T00:00:05",
  "completed_at": "2024-01-01T00:05:00",
  "processing_time": 295.5
}
```

**任务状态**：
- `queued`: 排队中
- `processing`: 处理中
- `completed`: 已完成
- `failed`: 失败

#### 下载 FBX

```http
GET /api/v1/mocap/tasks/{task_id}/download
```

返回 FBX 文件。

#### 删除任务

```http
DELETE /api/v1/mocap/tasks/{task_id}?keep_intermediate=false
```

#### 获取任务列表

```http
GET /api/v1/mocap/tasks
```

### 管理 API

#### 健康检查

```http
GET /health
```

简单健康检查（用于负载均衡器）。

```http
GET /api/v1/admin/health
```

详细健康检查（包含 GPU、磁盘、队列信息）。

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
MAX_FILE_SIZE=524288000        # 500MB
MAX_VIDEO_DURATION=30          # 30秒
MAX_VIDEO_RESOLUTION=2048      # 2K
```

### 队列配置

```bash
MAX_QUEUE_SIZE=10              # 最大队列长度
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

### 2. 任务失败

**错误**: `CUDA out of memory`

**解决**:
- 降低视频分辨率
- 减少队列大小（一次只处理一个任务）
- 增加 GPU 显存

**错误**: `Video too long`

**解决**:
- 视频时长限制为 30 秒
- 裁剪视频或调整 `MAX_VIDEO_DURATION`

### 3. 查看日志

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
sudo systemctl daemon-reload
sudo systemctl enable 4d-humans-api
sudo systemctl start 4d-humans-api
```

查看状态：

```bash
sudo systemctl status 4d-humans-api
```

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

