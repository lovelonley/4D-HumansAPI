"""API 常量定义"""


class TaskStatus:
    """任务状态"""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessStep:
    """处理步骤"""
    VIDEO_UPLOAD = "video_upload"
    TRACKING = "tracking"
    TRACK_EXTRACTION = "track_extraction"
    SMOOTHING = "smoothing"
    FBX_EXPORT = "fbx_export"
    PACKAGING = "packaging"


# 处理步骤列表（按顺序）
PROCESS_STEPS = [
    ProcessStep.VIDEO_UPLOAD,
    ProcessStep.TRACKING,
    ProcessStep.TRACK_EXTRACTION,
    ProcessStep.SMOOTHING,
    ProcessStep.FBX_EXPORT,
    ProcessStep.PACKAGING,
]


# 每个步骤的预估时间（秒）
STEP_ESTIMATED_TIME = {
    ProcessStep.VIDEO_UPLOAD: 5,
    ProcessStep.TRACKING: 180,  # 3分钟（取决于视频长度）
    ProcessStep.TRACK_EXTRACTION: 10,
    ProcessStep.SMOOTHING: 30,
    ProcessStep.FBX_EXPORT: 20,
    ProcessStep.PACKAGING: 5,
}


class ErrorCode:
    """错误码"""
    # 通用错误
    INTERNAL_ERROR = "INTERNAL_ERROR"
    INVALID_REQUEST = "INVALID_REQUEST"
    
    # 文件相关
    INVALID_FILE_FORMAT = "INVALID_FILE_FORMAT"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    VIDEO_TOO_LONG = "VIDEO_TOO_LONG"
    VIDEO_RESOLUTION_TOO_HIGH = "VIDEO_RESOLUTION_TOO_HIGH"
    
    # 任务相关
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
    TASK_TIMEOUT = "TASK_TIMEOUT"
    QUEUE_FULL = "QUEUE_FULL"
    
    # 处理步骤错误
    TRACKING_FAILED = "TRACKING_FAILED"
    TRACK_EXTRACTION_FAILED = "TRACK_EXTRACTION_FAILED"
    NO_TRACKS_FOUND = "NO_TRACKS_FOUND"
    SMOOTHING_FAILED = "SMOOTHING_FAILED"
    FBX_EXPORT_FAILED = "FBX_EXPORT_FAILED"
    MERGE_FAILED = "MERGE_FAILED"
    
    # 资源错误
    GPU_OUT_OF_MEMORY = "GPU_OUT_OF_MEMORY"
    DISK_FULL = "DISK_FULL"
    
    # 依赖错误
    BLENDER_NOT_FOUND = "BLENDER_NOT_FOUND"
    SMOOTHNET_NOT_AVAILABLE = "SMOOTHNET_NOT_AVAILABLE"

