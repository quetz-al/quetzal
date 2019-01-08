class DataAPIException(Exception):
    pass


class InvalidTransitionException(DataAPIException):
    pass


class WorkerException(DataAPIException):
    pass
