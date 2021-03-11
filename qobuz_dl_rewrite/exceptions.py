class AuthenticationError(Exception):
    pass


class IneligibleError(Exception):
    pass


class InvalidAppIdError(Exception):
    pass


class InvalidAppSecretError(Exception):
    pass


class InvalidQuality(Exception):
    pass


class NonStreamable(Exception):
    pass


class InvalidFormatError(Exception):
    def __init__(self, given_value, message='Invalid format "{}"'):
        super().__init__(message.format(given_value))
