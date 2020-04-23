class InvalidOption(Exception):
    """Invalid command line parameters"""
    pass


class DatasetError(Exception):
    """Problem initializing a Dataset(s)"""
    pass


class FilesystemError(Exception):
    """Can not write to filesystem"""
    pass


class ProcessError(Exception):
    """External program exit status is not 0"""
    pass


class ParserError(Exception):
    """External program exit status is not 0"""
    pass
