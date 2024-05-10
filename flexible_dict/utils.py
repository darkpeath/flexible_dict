class DataCopier(object):
    """
    A class to copy json object elements as built-in type.
    """
    def copy(self, obj):
        if isinstance(obj, dict):
            return self.copy_dict(obj)
        if isinstance(obj, list):
            return [self.copy_list(x) for x in obj]
        if isinstance(obj, tuple):
            return tuple(self.copy_tuple(x) for x in obj)
        return obj

    def copy_dict(self, obj: dict):
        return {k: self.copy(v) for k, v in obj.items()}

    def copy_list(self, obj: list):
        return [self.copy(x) for x in obj]

    def copy_tuple(self, obj: tuple):
        return tuple(self.copy(x) for x in obj)

def copy_as_builtin_json(obj, copier=DataCopier()):
    """
    copy a json object element as a built-in data
    """
    return copier.copy(obj)
