class ErrorWithResponse(Exception):
    def __init__(self, message="Exception"):
        self.message = message


class DuplicatedError(ErrorWithResponse):
    pass


class InvalidCredentials(ErrorWithResponse):
    pass


class Invalid2FA(ErrorWithResponse):
    pass


class MissingConfig(ErrorWithResponse):
    pass


class NotFound(ErrorWithResponse):
    pass


class RequestError(ErrorWithResponse):
    pass


class ExpiredLicense(Exception):
    pass

class HostNotFoundError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)
