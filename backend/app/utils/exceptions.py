class DomainError(Exception):
    def __init__(self, message: str, code: int = 2000):
        self.message = message
        self.code = code
        super().__init__(message)
