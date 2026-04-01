"""
自定义异常模块
"""
from fastapi import HTTPException, status


class AppException(Exception):
    """应用异常基类"""

    def __init__(
        self,
        code: int = 1000,
        message: str = "未知错误",
        status_code: int = status.HTTP_400_BAD_REQUEST
    ):
        self.code = code
        self.message = message
        self.status_code = status_code


class UnauthorizedException(AppException):
    """认证失败异常"""

    def __init__(self, message: str = "认证失败"):
        super().__init__(
            code=1002,
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED
        )


class TokenExpiredException(AppException):
    """Token过期异常"""

    def __init__(self, message: str = "Token已过期"):
        super().__init__(
            code=1003,
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED
        )


class ForbiddenException(AppException):
    """权限不足异常"""

    def __init__(self, message: str = "权限不足"):
        super().__init__(
            code=1004,
            message=message,
            status_code=status.HTTP_403_FORBIDDEN
        )


class NotFoundException(AppException):
    """资源不存在异常"""

    def __init__(self, message: str = "资源不存在"):
        super().__init__(
            code=1005,
            message=message,
            status_code=status.HTTP_404_NOT_FOUND
        )


class UserExistsException(AppException):
    """用户已存在异常"""

    def __init__(self, message: str = "用户已存在"):
        super().__init__(
            code=2001,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST
        )


class PasswordErrorException(AppException):
    """密码错误异常"""

    def __init__(self, message: str = "密码错误"):
        super().__init__(
            code=2002,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST
        )


class RSSInvalidException(AppException):
    """RSS链接无效异常"""

    def __init__(self, message: str = "RSS链接无效"):
        super().__init__(
            code=3001,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST
        )


class CrawlFailedException(AppException):
    """爬取失败异常"""

    def __init__(self, message: str = "爬取失败"):
        super().__init__(
            code=3002,
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def raise_http_exception(exc: AppException):
    """抛出HTTP异常"""
    raise HTTPException(
        status_code=exc.status_code,
        detail={
            "code": exc.code,
            "message": exc.message,
            "data": None
        }
    )
