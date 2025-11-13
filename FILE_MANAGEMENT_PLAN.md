# 4D-Humans 文件和数据管理方案

## 📊 当前问题分析

### 1. 文件分布混乱
- **outputs/**: 331MB，包含8月的旧文件（PHALP_*.mp4, _DEMO/, results/, track.log）
- **demo_out/**: 30个演示输出文件（.obj, .png）
- **tmp/**: 测试文件（test_betas_*.npz）
- **uploads/**: API 上传文件（空）
- **results/**: API 最终输出（空）

### 2. 文件命名不一致
- PHALP 输出：`demo_{video_name}.pkl`（在 `outputs/results/`）
- 提取输出：`{task_id}_tid{track_id}_extracted.npz`（在 `tmp/`）
- 平滑输出：`{task_id}_tid{track_id}_smoothed.npz`（在 `tmp/`）
- FBX 输出：`{task_id}_tid{track_id}_smoothed_fix_*.fbx`（在 `results/`）

### 3. 清理策略不完整
- ✅ API 任务自动清理（3天）
- ❌ 开发/演示文件无清理机制
- ❌ outputs/ 旧文件未清理
- ❌ 临时文件可能残留

---

## 🎯 文件管理方案

### 一、目录结构规范

```
4D-Humans/
├── uploads/              # API 上传文件（运行时）
│   └── {task_id}.{ext}
│
├── results/              # API 最终输出（运行时）
│   └── {task_id}_tid{track_id}_*.fbx
│
├── tmp/                  # API 中间文件（运行时）
│   ├── {task_id}_tid{track_id}_extracted.npz
│   └── {task_id}_tid{track_id}_smoothed.npz
│
├── outputs/              # PHALP 追踪输出（运行时）
│   ├── results/          # 追踪结果
│   │   └── demo_{video_name}.pkl
│   ├── _DEMO/            # PHALP 演示输出（可选）
│   └── PHALP_*.mp4       # PHALP 可视化视频（可选）
│
├── logs/                 # 日志文件（运行时）
│   ├── 4d-humans-api.log
│   └── 4d-humans-error.log
│
└── example_data/         # 示例数据（版本控制）
    ├── images/
    └── videos/
```

### 二、文件命名规范

#### API 任务文件（统一使用 task_id）

| 阶段 | 文件类型 | 命名格式 | 位置 |
|------|---------|---------|------|
| 上传 | 视频 | `{task_id}.{ext}` | `uploads/` |
| 追踪 | PKL | `demo_{video_name}.pkl` | `outputs/results/` |
| 提取 | NPZ | `{task_id}_tid{track_id}_extracted.npz` | `tmp/` |
| 平滑 | NPZ | `{task_id}_tid{track_id}_smoothed.npz` | `tmp/` |
| 导出 | FBX | `{task_id}_tid{track_id}_smoothed_fix_*.fbx` | `results/` |
| 导出 | FBM | `{task_id}_tid{track_id}_smoothed_fix_*.fbm/` | `results/` |

**问题**：追踪阶段使用 `video_name` 而非 `task_id`，导致文件关联困难。

**建议**：统一使用 `task_id` 命名所有文件。

---

### 三、文件生命周期管理

#### 1. API 运行时文件（自动管理）

| 文件类型 | 保留时间 | 清理策略 | 清理时机 |
|---------|---------|---------|---------|
| 上传视频 | 任务完成后 3 天 | 自动删除 | 定时任务（每6小时） |
| 追踪 PKL | 任务完成后 3 天 | 自动删除 | 定时任务 |
| 提取 NPZ | 任务完成后 3 天 | 自动删除 | 定时任务 |
| 平滑 NPZ | 任务完成后 3 天 | 自动删除 | 定时任务 |
| FBX 输出 | 任务完成后 3 天 | 自动删除 | 定时任务 |
| 失败任务 | 失败后 3 天 | 自动删除 | 定时任务 |

**当前实现**：✅ 已实现（`api/services/task_manager.py`）

#### 2. 开发/演示文件（手动管理）

| 文件类型 | 位置 | 建议清理策略 |
|---------|------|------------|
| PHALP 演示视频 | `outputs/PHALP_*.mp4` | 超过 30 天自动清理 |
| PHALP 演示输出 | `outputs/_DEMO/` | 超过 30 天自动清理 |
| 演示输出 | `demo_out/` | 超过 7 天自动清理 |
| 测试文件 | `tmp/test_*.npz` | 立即清理 |
| 日志文件 | `logs/*.log` | 超过 7 天自动清理或轮转 |

**当前实现**：❌ 未实现

---

### 四、清理策略优化

#### 1. 分层清理策略

```python
# 建议的清理配置（api/config.py）
class Settings:
    # API 任务文件清理
    AUTO_CLEANUP_ENABLED: bool = True
    CLEANUP_INTERVAL_HOURS: int = 6
    CLEANUP_COMPLETED_HOURS: int = 72  # 3天
    CLEANUP_FAILED_HOURS: int = 72
    
    # 开发/演示文件清理（新增）
    CLEANUP_DEMO_FILES_ENABLED: bool = True
    CLEANUP_DEMO_FILES_DAYS: int = 30  # 30天
    CLEANUP_TEST_FILES_ENABLED: bool = True
    CLEANUP_TEST_FILES_DAYS: int = 7   # 7天
    CLEANUP_LOG_FILES_DAYS: int = 7   # 7天
```

#### 2. 清理任务扩展

```python
# 建议在 api/main.py 中添加
async def _auto_cleanup():
    """自动清理过期任务和文件"""
    task_manager = get_task_manager()
    
    while True:
        try:
            await asyncio.sleep(settings.CLEANUP_INTERVAL_HOURS * 3600)
            
            # 1. 清理 API 任务文件（已有）
            cleaned_tasks = task_manager.cleanup_old_tasks()
            
            # 2. 清理开发/演示文件（新增）
            cleaned_demo = cleanup_demo_files()
            cleaned_test = cleanup_test_files()
            cleaned_logs = cleanup_log_files()
            
            logger.info(
                f"Auto cleanup: {cleaned_tasks} tasks, "
                f"{cleaned_demo} demo files, "
                f"{cleaned_test} test files, "
                f"{cleaned_logs} log files"
            )
        except Exception as e:
            logger.error(f"Auto cleanup error: {e}")
```

---

### 五、文件关联追踪

#### 当前问题
- 追踪文件使用 `video_name` 命名，无法直接关联到 `task_id`
- 需要从 `video_path` 提取 `video_name` 才能找到追踪文件

#### 建议方案

**方案 A：统一使用 task_id 命名（推荐）**

```python
# 修改 api/services/pipeline.py
def run_tracking(self, video_path: str, task_id: str, ...):
    # 使用 task_id 而非 video_name
    output_pkl = self.output_dir / "results" / f"{task_id}.pkl"
    
    # 修改 track.py 支持自定义输出文件名
    cmd = [
        sys.executable,
        str(self.track_script),
        f"video.source={video_path}",
        f"video.output_dir={self.output_dir}",
        f"video.output_name={task_id}"  # 新增参数
    ]
```

**方案 B：维护映射关系（临时方案）**

```python
# 在 Task 模型中添加
class Task:
    video_name: str  # 保存原始视频名
    tracking_pkl: str  # 保存完整路径
```

---

### 六、磁盘空间管理

#### 1. 空间检查

**当前实现**：✅ 上传时检查（`api/utils/file_handler.py`）

```python
# 检查磁盘空间（需要至少是文件大小的 3 倍）
required_space = file_size * 3
```

**建议优化**：
- 定期检查磁盘使用率
- 超过阈值（如 80%）时告警
- 超过阈值（如 90%）时拒绝新任务

#### 2. 空间预估

| 文件类型 | 大小估算 | 说明 |
|---------|---------|------|
| 上传视频 | 1-500MB | 用户上传 |
| 追踪 PKL | 10-100MB | 取决于视频长度 |
| 提取 NPZ | 1-10MB | 单人轨迹 |
| 平滑 NPZ | 1-10MB | 平滑后轨迹 |
| FBX 输出 | 0.5-5MB | 最终输出 |

**总空间需求**：约视频大小的 3-5 倍

---

### 七、文件访问控制

#### 1. 文件权限

| 目录 | 权限 | 说明 |
|------|------|------|
| `uploads/` | 600 | 仅 API 可读写 |
| `results/` | 644 | API 可写，用户可读 |
| `tmp/` | 600 | 仅 API 可读写 |
| `outputs/` | 755 | API 可写，用户可读 |
| `logs/` | 644 | API 可写，用户可读 |

#### 2. 文件访问接口

**当前实现**：
- ✅ 下载 FBX：`GET /api/v1/mocap/tasks/{task_id}/download`
- ❌ 下载中间文件：未实现
- ❌ 下载追踪结果：未实现

**建议**：
- 添加中间文件下载接口（可选，用于调试）
- 添加文件列表接口（查看任务相关文件）

---

### 八、备份策略

#### 1. 重要文件备份

| 文件类型 | 备份策略 | 备份位置 |
|---------|---------|---------|
| FBX 输出 | 可选备份 | 外部存储（S3/MinIO） |
| 配置文件 | 版本控制 | Git |
| 日志文件 | 轮转归档 | `logs/archive/` |

#### 2. 备份时机

- **手动备份**：重要任务完成后
- **自动备份**：生产环境建议配置外部存储

---

### 九、监控和告警

#### 1. 文件系统监控

**监控指标**：
- 磁盘使用率
- 文件数量
- 目录大小
- 清理任务执行情况

**告警阈值**：
- 磁盘使用率 > 80%：警告
- 磁盘使用率 > 90%：严重警告，拒绝新任务
- 清理任务失败：告警

#### 2. 文件操作监控

**记录事件**：
- 文件创建
- 文件删除
- 文件访问
- 清理任务执行

---

### 十、实施建议

#### 阶段 1：立即实施（高优先级）

1. **统一文件命名**
   - 修改 `run_tracking` 使用 `task_id` 命名
   - 更新 `track.py` 支持自定义输出文件名

2. **清理旧文件**
   - 清理 `outputs/` 中超过 30 天的文件
   - 清理 `demo_out/` 中的演示文件
   - 清理 `tmp/` 中的测试文件

3. **完善清理机制**
   - 添加开发/演示文件清理
   - 添加日志文件清理
   - 添加测试文件清理

#### 阶段 2：短期优化（中优先级）

1. **文件关联优化**
   - 实现文件映射表
   - 优化文件查找逻辑

2. **磁盘空间管理**
   - 添加磁盘使用率监控
   - 添加空间不足告警

3. **文件访问优化**
   - 添加中间文件下载接口
   - 添加文件列表接口

#### 阶段 3：长期优化（低优先级）

1. **外部存储集成**
   - S3/MinIO 支持
   - 文件自动归档

2. **文件压缩**
   - 中间文件压缩存储
   - 历史文件归档压缩

3. **分布式存储**
   - 多节点文件同步
   - 文件访问负载均衡

---

## 📋 检查清单

### 当前状态

- [x] API 任务自动清理（3天）
- [x] 文件删除逻辑
- [x] .gitignore 配置
- [ ] 开发/演示文件清理
- [ ] 日志文件清理
- [ ] 文件命名统一（tracking 使用 task_id）
- [ ] 磁盘空间监控
- [ ] 文件访问控制
- [ ] 备份策略

### 建议优先级

1. **P0（立即）**：统一文件命名、清理旧文件
2. **P1（短期）**：完善清理机制、磁盘监控
3. **P2（长期）**：外部存储、文件压缩

---

## 📝 总结

### 核心问题
1. 文件命名不一致（tracking 使用 video_name）
2. 开发/演示文件无清理机制
3. 旧文件占用空间（331MB+）

### 解决方案
1. 统一使用 `task_id` 命名所有文件
2. 实现分层清理策略（API 任务 + 开发文件）
3. 添加磁盘空间监控和告警

### 预期效果
- 文件管理清晰有序
- 磁盘空间可控
- 文件关联明确
- 清理自动化

---

**文档版本**: 1.0  
**创建时间**: 2025-11-13  
**最后更新**: 2025-11-13

