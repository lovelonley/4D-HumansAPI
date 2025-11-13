# 工作流安全性和稳定性分析

**分析时间**: 2025-11-13  
**项目定位**: 工具型项目，单次独立任务（10-15分钟），无需持久化

**核心关注点**:
- ✅ **资源泄露**（GPU、磁盘、进程）- 最高优先级
- ✅ **明确失败结果** - 确保用户知道任务失败
- ⚠️ **状态不一致** - 崩溃丢失状态可接受，但需避免影响后续任务

---

## 📊 工作流概览

```
1. 视频上传 → 2. 文件验证 → 3. 任务创建 → 4. 任务排队
    ↓
5. Worker 获取任务 → 6. Pipeline 执行
    ├─ 6.1 PHALP 追踪
    ├─ 6.2 轨迹提取
    ├─ 6.3 SmoothNet 平滑
    └─ 6.4 Blender FBX 导出
    ↓
7. 任务完成/失败 → 8. 文件清理
```

---

## 🔴 严重隐患（P0 - 立即修复）

### 1. 子进程超时后未强制终止 ⚠️⚠️⚠️ **资源泄露**

**位置**: `api/services/pipeline.py:98-105`

**问题**:
```python
result = subprocess.run(
    cmd,
    timeout=timeout,
    ...
)
```

当 `subprocess.run()` 超时时，虽然会抛出 `TimeoutExpired` 异常，但**子进程可能仍在运行**，特别是：
- PHALP 追踪（GPU 密集型，可能占用 GPU 很长时间）
- Blender 进程（可能卡住不退出）

**影响**:
- 🔴 **GPU 资源泄漏** - 最严重，影响后续所有任务
- 🔴 **磁盘空间占用** - 中间文件残留
- 🔴 **进程泄漏** - 系统资源耗尽

**加固方案**:
```python
try:
    result = subprocess.run(
        cmd,
        timeout=timeout,
        ...
    )
except subprocess.TimeoutExpired as e:
    # 强制终止进程（关键！）
    if e.process:
        e.process.kill()
        e.process.wait(timeout=5)  # 等待进程完全退出
    raise
```

---

### 2. 任务创建失败时文件清理不完整 ⚠️⚠️ **资源泄露**

**位置**: `api/routers/mocap.py:100-159`

**问题**:
```python
# 创建任务（先创建以获取 task_id）
task = task_manager.create_task(...)

try:
    # 保存上传的视频
    video_path, _ = await FileHandler.save_upload_file(video, task.task_id)
    
    # 验证视频
    if not is_valid:
        task_manager.delete_task(task.task_id)  # 只删除任务记录
        # ⚠️ 视频文件可能没有被删除！
```

**影响**:
- 🔴 **磁盘空间泄漏** - 验证失败时视频文件残留
- 🔴 **文件累积** - 大量失败任务导致磁盘满

**加固方案**:
```python
if not is_valid:
    # 删除任务和文件
    task_manager.delete_task(task.task_id)
    # 确保删除视频文件
    if Path(video_path).exists():
        FileHandler.delete_file(video_path)
```

---

### 3. Pipeline 失败时中间文件未清理 ⚠️⚠️ **资源泄露**

**位置**: `api/services/pipeline.py:504-622`

**问题**:
- Pipeline 失败时，已生成的中间文件（tracking_pkl, extracted_npz, smoothed_npz）没有被清理
- 失败任务会保留 3 天，中间文件也会保留 3 天

**影响**:
- 🔴 **磁盘空间占用** - 中间文件可能很大（特别是 tracking_pkl）
- 🔴 **资源浪费** - 失败任务的中间文件无意义

**加固方案**:
```python
def run_full_pipeline(...):
    generated_files = []  # 跟踪生成的文件
    
    try:
        # 追踪
        result = self.run_tracking(...)
        if result.success:
            generated_files.append(result.output_path)
        else:
            return {...}  # 失败，没有文件需要清理
        
        # ... 其他步骤
        
    except Exception as e:
        # 清理已生成的文件（关键！）
        for file_path in generated_files:
            if file_path and Path(file_path).exists():
                FileHandler.delete_file(file_path)
        raise
```

---

### 4. Worker 崩溃时 current_task_id 未重置 ⚠️ **状态不一致**

**位置**: `api/services/worker.py:65-147`

**问题**:
- Worker 异常退出时，`current_task_id` 不会被重置
- 服务重启后，该任务无法被重新处理（因为 `current_task_id` 不为 None）

**影响**:
- 🟡 **状态不一致** - 虽然崩溃丢失状态可接受，但会影响后续任务处理
- 🟡 **后续任务阻塞** - 无法处理新任务

**加固方案**（简化版，不需要任务恢复）:
```python
async def start(self):
    """启动工作器"""
    if self.running:
        return
    
    # 启动时重置 current_task_id（简单粗暴）
    self.task_manager.current_task_id = None
    
    self.running = True
    self.task = asyncio.create_task(self._process_loop())
    logger.info("Worker started")
```

---

## 🟡 中等隐患（P1 - 短期修复）

### 5. 文件路径安全性不足

**位置**: `api/services/pipeline.py:174-238`

**问题**:
- 没有验证文件路径是否在允许的目录内
- 可能存在路径遍历攻击（虽然概率低）

**影响**: 🟡 安全风险（低概率）

**加固方案**:
```python
def _validate_path(self, file_path: str, allowed_dir: Path) -> bool:
    """验证文件路径是否在允许的目录内"""
    try:
        resolved = Path(file_path).resolve()
        allowed = allowed_dir.resolve()
        return resolved.is_relative_to(allowed)
    except:
        return False
```

---

### 6. 并发安全问题（可选）

**位置**: `api/services/task_manager.py:19, 72-86`

**问题**:
- `current_task_id` 和 `queue` 操作没有锁保护
- 虽然当前是单 Worker，但如果未来扩展多 Worker，会有竞态条件

**影响**: 🟡 状态不一致（当前单 Worker 影响小）

**加固方案**（如果未来需要多 Worker）:
```python
import threading

class TaskManager:
    def __init__(self):
        self.lock = threading.Lock()
        ...
    
    def get_next_task(self) -> Optional[Task]:
        with self.lock:
            if not self.queue or self.current_task_id:
                return None
            ...
```

**注意**: 当前单 Worker 场景下，这个问题影响较小，可以暂缓。

---

### 7. 磁盘空间检查不充分

**位置**: `api/utils/file_handler.py:37-48`

**问题**:
- 只检查上传文件大小，没有考虑：
  - 中间文件（tracking_pkl, npz 文件）
  - PHALP 输出视频
  - FBX 文件

**影响**: 🟡 任务可能因磁盘满而失败（但会明确失败，可接受）

**加固方案**（可选）:
```python
def check_disk_space(file_size: int, required_multiplier: int = 5) -> bool:
    """检查磁盘空间（考虑中间文件）"""
    stat = shutil.disk_usage(settings.UPLOAD_DIR)
    required = file_size * required_multiplier  # 5倍空间
    return stat.free >= required
```

**注意**: 当前已有 3 倍空间检查，基本够用。如果频繁出现磁盘满错误，再优化。

---

## 🟢 低优先级隐患（P2 - 长期优化）

### 8. 进程组管理缺失

**问题**:
- 没有使用进程组（process group）
- 子进程的子进程（如 Blender 启动的脚本）可能无法被正确终止

**加固方案**:
```python
result = subprocess.run(
    cmd,
    preexec_fn=os.setsid,  # 创建新的进程组
    ...
)

# 超时时终止整个进程组
os.killpg(os.getpgid(e.process.pid), signal.SIGTERM)
```

---

### 9. 错误日志信息泄露

**位置**: `api/services/pipeline.py:111`

**问题**:
- 错误日志可能包含敏感信息（文件路径、系统信息）

**加固方案**:
- 生产环境限制错误日志详细程度
- 敏感信息脱敏

---

### 10. 任务状态查询无缓存

**位置**: `api/routers/mocap.py:169-202`

**问题**:
- 频繁查询任务状态可能导致性能问题（虽然当前是内存存储）

**加固方案**:
- 添加短期缓存（如 1 秒）
- 使用 Redis 等外部存储（未来扩展）

---

## 📋 加固优先级总结（按工具型项目定位）

### P0（立即修复 - 资源泄露）
1. ✅✅✅ **子进程超时后强制终止** - GPU/进程资源泄露
2. ✅✅ **任务创建失败时完整清理** - 磁盘资源泄露
3. ✅✅ **Pipeline 失败时中间文件清理** - 磁盘资源泄露
4. ✅ **Worker 启动时重置 current_task_id** - 状态不一致（简单修复）

### P1（短期修复 - 可选）
5. ⚠️ **文件路径安全性验证** - 安全风险（低概率）
6. ⚠️ **并发安全保护** - 状态不一致（当前单 Worker 影响小）
7. ⚠️ **磁盘空间检查增强** - 任务失败（已有基本检查）

### P2（长期优化 - 非必需）
8. 📝 **进程组管理** - 更彻底的进程清理
9. 📝 **错误日志脱敏** - 生产环境优化
10. 📝 **任务状态查询优化** - 性能优化

---

## 🔧 建议的修复顺序（按工具型项目定位）

### 第一阶段（立即 - 资源泄露修复）
1. ✅ **子进程超时后强制终止** - 防止 GPU/进程泄露
2. ✅ **任务创建失败时完整清理** - 防止磁盘泄露
3. ✅ **Pipeline 失败时中间文件清理** - 防止磁盘泄露
4. ✅ **Worker 启动时重置 current_task_id** - 防止状态卡死

### 第二阶段（可选 - 安全加固）
5. ⚠️ **文件路径安全性验证** - 如果担心安全风险
6. ⚠️ **并发安全保护** - 如果未来需要多 Worker

### 第三阶段（非必需）
7. 📝 **进程组管理** - 更彻底的进程清理（当前方案已足够）
8. 📝 **磁盘空间检查增强** - 如果频繁出现磁盘满错误
9. 📝 **其他优化** - 按需

---

## 📊 风险评估（按工具型项目定位）

| 隐患 | 严重性 | 可能性 | 影响 | 优先级 | 备注 |
|------|--------|--------|------|--------|------|
| 子进程未终止 | 🔴 高 | 中 | **GPU/进程泄漏** | P0 | **必须修复** |
| 文件清理不完整 | 🔴 高 | 高 | **磁盘泄漏** | P0 | **必须修复** |
| 中间文件未清理 | 🔴 高 | 高 | **磁盘占用** | P0 | **必须修复** |
| current_task_id 未重置 | 🟡 中 | 低 | 后续任务阻塞 | P0 | 简单修复 |
| 路径安全性 | 🟡 中 | 低 | 安全风险 | P1 | 可选 |
| 并发安全 | 🟡 中 | 低 | 状态不一致 | P1 | 单 Worker 影响小 |
| 磁盘空间检查 | 🟡 中 | 中 | 任务失败 | P1 | 已有基本检查 |

**关键原则**:
- ✅ **资源泄露** = 必须修复（P0）
- ✅ **明确失败结果** = 当前已满足（失败会明确返回错误）
- ⚠️ **状态不一致** = 简单修复即可（崩溃丢失状态可接受）

---

## ✅ 当前工作流的优点

1. ✅ **单队列设计**：避免 GPU 并发冲突
2. ✅ **超时机制**：防止任务无限运行
3. ✅ **错误分类**：详细的错误码和错误信息
4. ✅ **自动清理**：定期清理过期任务和文件
5. ✅ **进度追踪**：实时更新任务进度

---

**文档版本**: 1.0  
**创建时间**: 2025-11-13  
**最后更新**: 2025-11-13

