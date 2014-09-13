import logging


def get_stream_handler(log_level=None):
    """Returns a formatted stream handler.

    log_level:  An optional parameter to set the log level.

    """
    stream_handler = logging.StreamHandler()
    if log_level:
        stream_handler.setLevel(log_level)
    stream_handler.setFormatter(get_default_formatter())
    return stream_handler


def get_default_formatter():
    """Returns the default formatter."""
    return logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)s | %(message)s', '%Y-%m-%d %H:%M:%S')


def setup_root_logger(level=logging.DEBUG):
    """Convenience function to set up the root logger."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(get_stream_handler())
