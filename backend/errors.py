"""
统一业务错误异常。

业务代码中直接 raise AppError(...)；main.py 中的全局异常处理器负责
将其包装成第六部分约定的错误响应结构：
{"request_id": "...", "error": {"code": ..., "message": ..., "stage": ...}}
"""


class AppError(Exception):
    def __init__(self, code: str, message: str, stage: str, status_code: int):
        self.code = code
        self.message = message
        self.stage = stage
        self.status_code = status_code
        super().__init__(message)
