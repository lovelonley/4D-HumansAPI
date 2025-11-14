# 远程部署指南

## 前提条件

1. **SSH 访问权限**
   - 已配置 SSH 密钥或密码
   - 可以连接到远程 Ubuntu 服务器

2. **远程服务器环境**
   - Ubuntu 系统
   - Python 3.10+
   - Git
   - CUDA/GPU（如果使用 GPU）

## 使用方法

### 方式 1: 使用部署脚本

```bash
# 设置环境变量
export SSH_HOST="user@your-server.com"
export SSH_PORT="22"  # 可选，默认 22
export DEPLOY_PATH="/opt/4d-humans-api"  # 可选

# 执行部署
./scripts/deploy_remote.sh $SSH_HOST $DEPLOY_PATH
```

### 方式 2: 手动 SSH 执行

```bash
# 1. 推送代码
git push api main

# 2. SSH 连接到服务器
ssh user@your-server.com

# 3. 在服务器上执行
cd /opt/4d-humans-api
git pull api main
git submodule update --init --recursive
pip install -r requirements-api.txt
sudo systemctl restart 4d-humans-api
```

### 方式 3: 使用 AI 助手执行

提供以下信息，我可以帮你执行：

```bash
SSH_HOST="user@hostname"
DEPLOY_PATH="/opt/4d-humans-api"
API_URL="http://your-server.com:8000"
```

然后我可以：
- 测试 SSH 连接
- 执行部署命令
- 运行测试
- 检查服务状态

## 远程测试

```bash
# 使用测试脚本
./scripts/test_remote.sh $SSH_HOST $API_URL

# 或手动测试
ssh $SSH_HOST "curl http://localhost:8000/health"
```

## Systemd 服务配置

### 服务名称
`4d-humans-api`

### 创建服务文件

创建 `/etc/systemd/system/4d-humans-api.service`：

```ini
[Unit]
Description=4D-Humans MoCap API Service
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/4D-Humans
Environment="PATH=/path/to/conda/envs/4D-humans/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/path/to/conda/envs/4D-humans/bin/python -m api.main
Restart=always
RestartSec=10
StandardOutput=append:/path/to/4D-Humans/logs/4d-humans-api.log
StandardError=append:/path/to/4D-Humans/logs/4d-humans-api-error.log

LimitNOFILE=65536
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

**重要**: 替换以下路径：
- `User`: 运行服务的用户（如 `zgx`）
- `WorkingDirectory`: 项目目录（如 `/home/zgx/4D-Humans`）
- `Environment PATH`: Conda 环境路径（如 `/home/zgx/miniconda3/envs/4D-humans/bin`）
- `ExecStart`: Python 可执行文件路径
- `StandardOutput/StandardError`: 日志文件路径

### 启用和启动服务

```bash
# 复制服务文件（如果使用项目中的模板）
sudo cp deploy/4d-humans-api.service /etc/systemd/system/

# 编辑服务文件，修改路径
sudo nano /etc/systemd/system/4d-humans-api.service

# 重载 systemd
sudo systemctl daemon-reload

# 启用自启动
sudo systemctl enable 4d-humans-api

# 启动服务
sudo systemctl start 4d-humans-api

# 检查状态
sudo systemctl status 4d-humans-api

# 查看日志
sudo journalctl -u 4d-humans-api -f
```

### 服务管理命令

```bash
# 启动服务
sudo systemctl start 4d-humans-api

# 停止服务
sudo systemctl stop 4d-humans-api

# 重启服务
sudo systemctl restart 4d-humans-api

# 查看状态
sudo systemctl status 4d-humans-api

# 查看日志
sudo journalctl -u 4d-humans-api -n 50
sudo journalctl -u 4d-humans-api -f
```

## 注意事项

1. **Submodules**: 
   - PHALP 和 SmoothNet 已配置为 Git Submodules
   - 确保远程服务器可以访问 GitHub（用于拉取 submodules）
   - 目录名使用小写：`phalp/`、`smoothnet/`
2. **权限**: 某些操作可能需要 sudo 权限
3. **服务管理**: 使用 systemd 服务管理（服务名：`4d-humans-api`）
4. **环境变量**: 确保远程服务器有正确的环境变量配置
   - `SMOOTHNET_CHECKPOINT=smoothnet/data/checkpoints/pw3d_spin_3D/checkpoint_8.pth.tar`
5. **文件管理**: 部署后会自动清理旧文件（配置在 `.env` 中）

## 故障排除

### SSH 连接失败
```bash
# 测试连接
ssh -v user@hostname

# 检查 SSH 密钥
ssh-add -l
```

### Submodules 拉取失败
```bash
# 手动初始化
ssh $SSH_HOST "cd $DEPLOY_PATH && git submodule update --init --recursive"
```

### 服务无法启动
```bash
# 查看服务状态
ssh $SSH_HOST "sudo systemctl status 4d-humans-api"

# 查看日志
ssh $SSH_HOST "sudo journalctl -u 4d-humans-api -n 50"

# 检查服务文件配置
ssh $SSH_HOST "cat /etc/systemd/system/4d-humans-api.service"

# 检查 Python 环境
ssh $SSH_HOST "which python"
ssh $SSH_HOST "python --version"
```

