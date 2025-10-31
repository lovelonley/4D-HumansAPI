# 4D-Humans MoCap API - 快速开始

## 🎯 5分钟快速上手

### 1. 安装依赖

```bash
# 安装 API 依赖
pip install -r requirements-api.txt

# 确保主项目依赖已安装
pip install -r requirements.txt
```

### 2. 配置环境

```bash
# 复制环境变量模板
cp deploy/env.example .env

# 编辑 .env（必需）
vim .env
```

**必须配置**：

```bash
# SmoothNet 检查点（必需）
SMOOTHNET_CHECKPOINT=SmoothNet/data/checkpoints/pw3d_spin_3D/checkpoint_8.pth.tar

# Blender 路径（如果不在 PATH 中）
BLENDER_PATH=/Applications/Blender.app/Contents/MacOS/blender
```

### 3. 启动服务

```bash
# 方法 1: 使用启动脚本
./scripts/start_api.sh

# 方法 2: 直接运行
python -m api.main

# 方法 3: 使用 uvicorn
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### 4. 测试 API

打开浏览器访问：http://localhost:8000/docs

或使用测试脚本：

```bash
# 上传视频
python scripts/test_api.py example_data/videos/gymnasts.mp4 --wait

# 查看健康状态
python scripts/test_api.py --health

# 列出所有任务
python scripts/test_api.py --list
```

## 📖 基本用法

### 使用 cURL

```bash
# 创建任务
curl -X POST "http://localhost:8000/api/v1/mocap/tasks" \
  -F "video=@example_data/videos/gymnasts.mp4"

# 查询任务状态
curl "http://localhost:8000/api/v1/mocap/tasks/{task_id}"

# 下载 FBX
curl -O "http://localhost:8000/api/v1/mocap/tasks/{task_id}/download"
```

### 使用 Python

```python
import requests

# 创建任务
with open('video.mp4', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/v1/mocap/tasks',
        files={'video': f}
    )
    task = response.json()
    task_id = task['task_id']

# 查询状态
response = requests.get(f'http://localhost:8000/api/v1/mocap/tasks/{task_id}')
status = response.json()

# 下载 FBX
if status['status'] == 'completed':
    response = requests.get(f'http://localhost:8000/api/v1/mocap/tasks/{task_id}/download')
    with open('output.fbx', 'wb') as f:
        f.write(response.content)
```

## 🔧 常用参数

### 创建任务时的可选参数

```bash
# 指定人物 ID
-F "track_id=1"

# 设置输出帧率
-F "fps=60"

# 禁用根运动
-F "with_root_motion=false"

# 调整相机缩放
-F "cam_scale=1.5"

# 平滑参数
-F "smoothing_strength=1.2"
-F "smoothing_window=11"
-F "smoothing_ema=0.3"
```

### 完整示例

```bash
curl -X POST "http://localhost:8000/api/v1/mocap/tasks" \
  -F "video=@video.mp4" \
  -F "fps=60" \
  -F "with_root_motion=true" \
  -F "smoothing_strength=1.2"
```

## 🚨 常见问题

### Q: 服务启动失败，提示 "Blender not found"

**A**: 安装 Blender 3.0+ 并确保在 PATH 中，或在 `.env` 中设置 `BLENDER_PATH`。

### Q: 服务启动失败，提示 "SmoothNet checkpoint not found"

**A**: 确保 SmoothNet 检查点文件存在，路径在 `.env` 中正确配置。

### Q: 任务失败，错误 "CUDA out of memory"

**A**: 降低视频分辨率，或减少队列大小（一次只处理一个任务）。

### Q: 视频上传失败，提示 "Video too long"

**A**: 视频时长限制为 30 秒，请裁剪视频或调整 `.env` 中的 `MAX_VIDEO_DURATION`。

### Q: 如何查看日志？

**A**: 日志文件位于 `logs/` 目录：
- `logs/4d-humans-api.log` - 应用日志
- `logs/4d-humans-error.log` - 错误日志

## 📊 监控

### 健康检查

```bash
# 简单健康检查
curl http://localhost:8000/health

# 详细健康检查
curl http://localhost:8000/api/v1/admin/health
```

### 统计信息

```bash
# 任务统计
curl http://localhost:8000/api/v1/admin/stats

# 队列信息
curl http://localhost:8000/api/v1/admin/queue
```

## 🎓 下一步

- 阅读完整文档：[README_API.md](README_API.md)
- 查看 API 文档：http://localhost:8000/docs
- 了解部署方式：[README_API.md#部署](README_API.md#部署)

## 💡 提示

1. **视频限制**：最大 500MB，30 秒，2K 分辨率
2. **队列管理**：单队列，一次处理一个任务
3. **文件清理**：完成/失败的任务保留 3 天后自动清理
4. **GPU 要求**：推荐至少 8GB 显存

## 🆘 获取帮助

- 查看日志：`tail -f logs/4d-humans-api.log`
- 测试脚本：`python scripts/test_api.py --help`
- API 文档：http://localhost:8000/docs

