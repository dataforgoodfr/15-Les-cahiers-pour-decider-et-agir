class AppException(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ApiException(Exception):
    def __init__(self, message: str, error_code: str, status_code: int) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code
        self.message = message


class DBException(AppException):
    def __init__(self, error_code: str) -> None:
        super().__init__(message="Database error")
