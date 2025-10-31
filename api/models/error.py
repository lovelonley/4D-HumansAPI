"""错误响应模型"""
from typing import Optional
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """错误响应"""
    error_code: str
    error_message: str
    error_details: Optional[str] = None

