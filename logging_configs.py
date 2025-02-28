import logging
import sys
from functools import wraps
import time

"""
    - This script creates a ColoredFormatter to format log messages with colors based on their severity.
    - It applies the formatter to a StreamHandler that logs messages to the console.
    - The logger supports different levels (DEBUG, INFO, WARNING, ERROR, CRITICAL) and applies ANSI color
    codes for better visibility in the terminal.

"""

class ColoredFormatter(logging.Formatter):
    """Custom formatter for colored logs"""

    COLORS = {
        "DEBUG": "\033[34m",  # blue
        "INFO": "\033[0m",  # Default
        "WARNING": "\033[93m",  # Yellow
        "ERROR": "\033[91m",  # Red
        "CRITICAL": "\033[0m",  # System default (can be bold red in some terminals)
    }
    RESET = "\033[0m"

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.msg = f"{log_color}{record.msg}{self.RESET}"
        return super().format(record)

# Setup logger
logger = logging.getLogger("InteractivePrompt")
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(ColoredFormatter("%(message)s"))
logger.addHandler(console_handler)



def log(func):
    """
    A decorator that tracks how long a function takes to run and logs errors if the function fails.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            stime = time.time()
            # call the function
            result = func(*args, **kwargs)
            # logs how long the function took to execute
            logger.debug(
                f"Agent '{func.__name__}' run time: {time.time() - stime:.2f} seconds."
            )
        except Exception as e:
            logger.exception(f"Error in agent '{func.__name__}': {e}")
            raise
        return result

    return wrapper