import logging
import os


def get_log_level():
    """
    Determines the logging level for the application based on environment variables. The function first checks for
    a 'DEBUG_MODE' environment variable, and if it is set to 'true', the logging level is set to DEBUG. If 'DEBUG_MODE'
    is not 'true' or not set, the function then checks the 'LOG_LEVEL' environment variable to set the appropriate
    logging level.

    The 'LOG_LEVEL' environment variable can be one of 'DEBUG', 'INFO', 'WARNING', 'ERROR', or 'CRITICAL'. If 'LOG_LEVEL'
    is not set or if it is set to a value outside of these options, the logging level defaults to 'INFO'.

    :return: A logging level from the logging module corresponding to the determined log level.

    Note: This function utilizes the `os` module to access environment variables and the `logging` module to define
    log levels. It ensures that the application logs at an appropriate level based on environmental configurations,
    enhancing the flexibility and debuggability of the application.
    """
    if os.environ.get('DEBUG_MODE', 'False').lower() == 'true':
        return logging.DEBUG

    log_level = os.environ.get('LOG_LEVEL', 'INFO')
    if log_level not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
        log_level = 'INFO'
    return getattr(logging, log_level)


def get_image_name(team_id):
    return f"traefik/whoami"
