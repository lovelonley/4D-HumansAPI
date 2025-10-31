#!/usr/bin/env python3
"""API 测试脚本"""
import argparse
import requests
import time
import sys
from pathlib import Path


API_BASE = "http://localhost:8000"


def create_task(video_path: str, **kwargs):
    """创建任务"""
    print(f"📤 Uploading video: {video_path}")
    
    with open(video_path, 'rb') as f:
        files = {'video': f}
        data = {k: v for k, v in kwargs.items() if v is not None}
        
        response = requests.post(
            f"{API_BASE}/api/v1/mocap/tasks",
            files=files,
            data=data
        )
    
    if response.status_code == 200:
        task = response.json()
        print(f"✅ Task created: {task['task_id']}")
        print(f"   Status: {task['status']}")
        return task['task_id']
    else:
        print(f"❌ Failed to create task: {response.status_code}")
        print(response.json())
        return None


def get_task_status(task_id: str):
    """查询任务状态"""
    response = requests.get(f"{API_BASE}/api/v1/mocap/tasks/{task_id}")
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ Failed to get task status: {response.status_code}")
        return None


def wait_for_completion(task_id: str, poll_interval: int = 5):
    """等待任务完成"""
    print(f"⏳ Waiting for task {task_id} to complete...")
    
    while True:
        task = get_task_status(task_id)
        
        if not task:
            return False
        
        status = task['status']
        progress = task['progress']
        current_step = task.get('current_step', 'unknown')
        
        print(f"   Status: {status} | Progress: {progress}% | Step: {current_step}")
        
        if status == 'completed':
            print(f"✅ Task completed!")
            print(f"   Processing time: {task.get('processing_time', 0):.2f}s")
            print(f"   FBX URL: {task.get('fbx_url')}")
            return True
        elif status == 'failed':
            print(f"❌ Task failed!")
            print(f"   Error: {task.get('error_message')}")
            print(f"   Error code: {task.get('error_code')}")
            return False
        
        time.sleep(poll_interval)


def download_fbx(task_id: str, output_path: str = None):
    """下载 FBX 文件"""
    if output_path is None:
        output_path = f"{task_id}.fbx"
    
    print(f"📥 Downloading FBX to: {output_path}")
    
    response = requests.get(
        f"{API_BASE}/api/v1/mocap/tasks/{task_id}/download",
        stream=True
    )
    
    if response.status_code == 200:
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"✅ Downloaded: {output_path}")
        return True
    else:
        print(f"❌ Failed to download FBX: {response.status_code}")
        return False


def list_tasks():
    """列出所有任务"""
    response = requests.get(f"{API_BASE}/api/v1/mocap/tasks")
    
    if response.status_code == 200:
        data = response.json()
        tasks = data['tasks']
        
        print(f"📋 Total tasks: {data['total']}")
        print()
        
        for task in tasks:
            print(f"Task ID: {task['task_id']}")
            print(f"  Status: {task['status']}")
            print(f"  Progress: {task['progress']}%")
            print(f"  Created: {task['created_at']}")
            if task.get('fbx_url'):
                print(f"  FBX URL: {task['fbx_url']}")
            print()
        
        return True
    else:
        print(f"❌ Failed to list tasks: {response.status_code}")
        return False


def get_health():
    """获取健康状态"""
    response = requests.get(f"{API_BASE}/api/v1/admin/health")
    
    if response.status_code == 200:
        health = response.json()
        
        print("🏥 Health Status")
        print(f"  Status: {health['status']}")
        print(f"  Version: {health['version']}")
        print(f"  Uptime: {health['uptime']}s")
        print()
        
        print("💾 Disk")
        disk = health['disk']
        print(f"  Total: {disk['total_gb']}GB")
        print(f"  Used: {disk['used_gb']}GB")
        print(f"  Usage: {disk['usage_percent']}%")
        print()
        
        if health.get('gpu'):
            print("🎮 GPU")
            gpu = health['gpu']
            print(f"  Name: {gpu['name']}")
            print(f"  Utilization: {gpu['utilization']}%")
            print(f"  Memory: {gpu['memory_used']}MB / {gpu['memory_total']}MB")
            print(f"  Temperature: {gpu['temperature']}°C")
            print()
        
        print("📊 Queue")
        queue = health['queue']
        print(f"  Size: {queue['queue_size']} / {queue['max_queue_size']}")
        if queue.get('current_task'):
            current = queue['current_task']
            print(f"  Current: {current['task_id']} ({current['progress']}%)")
        print()
        
        print("📈 Stats")
        stats = health['stats']
        print(f"  Total tasks: {stats['total_tasks']}")
        print(f"  Completed: {stats['completed_tasks']}")
        print(f"  Failed: {stats['failed_tasks']}")
        print(f"  Success rate: {stats['success_rate']*100:.1f}%")
        print(f"  Avg processing time: {stats['average_processing_time']:.2f}s")
        
        return True
    else:
        print(f"❌ Failed to get health: {response.status_code}")
        return False


def main():
    parser = argparse.ArgumentParser(description="4D-Humans MoCap API Test Script")
    
    parser.add_argument('video', nargs='?', help="Video file to upload")
    parser.add_argument('--task-id', help="Task ID to query")
    parser.add_argument('--list', action='store_true', help="List all tasks")
    parser.add_argument('--health', action='store_true', help="Get health status")
    parser.add_argument('--download', help="Download FBX for task ID")
    parser.add_argument('--output', help="Output path for downloaded FBX")
    parser.add_argument('--wait', action='store_true', help="Wait for task completion")
    parser.add_argument('--api-base', default="http://localhost:8000", help="API base URL")
    
    # Task parameters
    parser.add_argument('--track-id', type=int, help="Track ID to extract")
    parser.add_argument('--fps', type=int, help="Output FPS")
    parser.add_argument('--with-root-motion', type=bool, help="Include root motion")
    parser.add_argument('--cam-scale', type=float, help="Camera scale")
    parser.add_argument('--smoothing-strength', type=float, help="Smoothing strength")
    parser.add_argument('--smoothing-window', type=int, help="Smoothing window size")
    parser.add_argument('--smoothing-ema', type=float, help="Smoothing EMA")
    
    args = parser.parse_args()
    
    global API_BASE
    API_BASE = args.api_base
    
    # List tasks
    if args.list:
        list_tasks()
        return
    
    # Health check
    if args.health:
        get_health()
        return
    
    # Download FBX
    if args.download:
        download_fbx(args.download, args.output)
        return
    
    # Query task status
    if args.task_id:
        task = get_task_status(args.task_id)
        if task:
            print(f"Task ID: {task['task_id']}")
            print(f"Status: {task['status']}")
            print(f"Progress: {task['progress']}%")
            print(f"Current step: {task.get('current_step')}")
            print(f"Created: {task['created_at']}")
            if task.get('started_at'):
                print(f"Started: {task['started_at']}")
            if task.get('completed_at'):
                print(f"Completed: {task['completed_at']}")
            if task.get('fbx_url'):
                print(f"FBX URL: {task['fbx_url']}")
            if task.get('error_message'):
                print(f"Error: {task['error_message']}")
        return
    
    # Upload video
    if args.video:
        if not Path(args.video).exists():
            print(f"❌ Video file not found: {args.video}")
            sys.exit(1)
        
        task_params = {
            'track_id': args.track_id,
            'fps': args.fps,
            'with_root_motion': args.with_root_motion,
            'cam_scale': args.cam_scale,
            'smoothing_strength': args.smoothing_strength,
            'smoothing_window': args.smoothing_window,
            'smoothing_ema': args.smoothing_ema
        }
        
        task_id = create_task(args.video, **task_params)
        
        if task_id and args.wait:
            if wait_for_completion(task_id):
                # Auto download
                download_fbx(task_id)
        
        return
    
    # No action specified
    parser.print_help()


if __name__ == "__main__":
    main()

