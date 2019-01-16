from connexion.exceptions import ProblemException


class APIException(ProblemException):
    """Exception for API-related problems

    Use this class when a route function fails but the API should respond
    with an appropriate error response
    """
    pass
