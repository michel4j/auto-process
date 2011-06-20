

class InvalidOptions(Exception):
    """Invalid command line parameters"""
    pass
    
class DatasetError(Exception):
    """Problem initializing a Dataset"""
    pass

class FilesystemError(Exception):
    """Can not write to filesystem"""
    pass
