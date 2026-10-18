"""Stable public errors: messages never contain external exception text."""


class AppError(Exception):
    def __init__(self, code, message, status=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status

    def as_dict(self):
        error = {'code': self.code, 'message': self.message}
        if self.status is not None:
            error['status'] = self.status
        return error
