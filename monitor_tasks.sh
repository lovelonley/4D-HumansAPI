#!/bin/bash
API_BASE="http://192.168.2.5:8083"
TASK1="9192e919-5fd8-4f95-96f3-9249a0af32ed"
TASK2="7ec4b0ed-1b51-40bf-93c7-5cba2b23bcc0"

echo "🔍 Monitoring tasks..."
echo "Task 1: $TASK1"
echo "Task 2: $TASK2"
echo ""

while true; do
    clear
    echo "========================================"
    echo "📊 Task Status Monitor"
    echo "========================================"
    date
    echo ""
    
    echo "--- Task 1 (2222.mp4) ---"
    python scripts/test_api.py --task-id $TASK1 --api-base $API_BASE
    echo ""
    
    echo "--- Task 2 (3333.mp4) ---"
    python scripts/test_api.py --task-id $TASK2 --api-base $API_BASE
    echo ""
    
    echo "Press Ctrl+C to stop monitoring"
    sleep 10
done
