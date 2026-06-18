class FileValidationError(Exception):
    pass


class FileTooLargeError(FileValidationError):
    pass


class InvalidFileTypeError(FileValidationError):
    pass


class InvalidFileVisibilityError(FileValidationError):
    pass


class ManagedFileNotFoundError(Exception):
    pass


class FileAccessDeniedError(Exception):
    pass


class InvalidFileAccessTokenError(Exception):
    pass
