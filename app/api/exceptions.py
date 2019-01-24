from connexion.exceptions import ProblemException


class APIException(ProblemException):
    """Exception for API-related problems

    Use this class when a route function fails but the API should respond
    with an appropriate error response
    """
    pass


class ObjectNotFoundException(APIException):
    """Exception for cases when an object does not exist

    Typically, when a workspace or file does not exist
    """


class QuetzalException(Exception):
    """Represents an internal error in the data API

    Use for exceptions that don't need to be transmitted back as a response
    """
    pass


class InvalidTransitionException(QuetzalException):
    pass


class WorkerException(QuetzalException):
    pass

