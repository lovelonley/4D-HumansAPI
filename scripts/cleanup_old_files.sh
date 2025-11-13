#!/bin/bash
# 清理旧文件脚本（一次性清理）

echo "=== 清理旧文件 ==="
echo ""

# 清理 outputs/ 中的旧文件（超过30天）
echo "1. 清理 outputs/ 中的旧文件（超过30天）..."
find outputs/ -type f -mtime +30 -name "PHALP_*.mp4" -delete 2>/dev/null
find outputs/_DEMO/ -type f -mtime +30 -delete 2>/dev/null
find outputs/_DEMO/ -type d -empty -delete 2>/dev/null
echo "✅ outputs/ 清理完成"

# 清理 demo_out/ 中的文件（超过7天）
echo "2. 清理 demo_out/ 中的文件（超过7天）..."
find demo_out/ -type f -mtime +7 -delete 2>/dev/null
echo "✅ demo_out/ 清理完成"

# 清理 tmp/ 中的测试文件（超过7天）
echo "3. 清理 tmp/ 中的测试文件（超过7天）..."
find tmp/ -type f -mtime +7 -name "test_*" -delete 2>/dev/null
echo "✅ tmp/ 清理完成"

# 清理 logs/ 中的旧日志（超过7天）
echo "4. 清理 logs/ 中的旧日志（超过7天）..."
find logs/ -type f -mtime +7 -name "*.log" -delete 2>/dev/null
echo "✅ logs/ 清理完成"

echo ""
echo "=== 清理完成 ==="
