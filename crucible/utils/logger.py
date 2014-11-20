"""
Simple logging helper class

Author: Sean Toner
"""

import logging
import time
import sys
import os


def make_timestamp():
    """
    Returns the localtime year-month-day-hr-min-sec as a string
    """
    timevals = time.localtime()[:-3]
    return "-".join(str(x) for x in timevals)


def make_timestamped_filename(prefix, dir="/tmp", postfix=".txt"):
    """
    Returns a string containing prefix-timestamp-postfix
    """
    base = os.path.join(dir, prefix)
    return "-".join([base, make_timestamp()]) + postfix


def make_logger(loggername, handlers=None, loglevel=logging.DEBUG):
    if handlers is None:
        handlers = []
    logr = logging.getLogger(loggername)
    logr.setLevel(loglevel)

    for hdlr in handlers:
        logr.addHandler(hdlr)

    return logr


def make_stream_handler(fmt, stream=sys.stdout, loglevel=logging.INFO):
    ## Handle a stupid 2.6 to 2.7 rename
    try:
        strm_handler = logging.StreamHandler(strm=stream)
    except:
        strm_handler = logging.StreamHandler(stream=stream)

    strm_handler.setFormatter(fmt)
    strm_handler.setLevel(loglevel)
    return strm_handler


def make_file_handler(fmt, filename, loglevel=logging.DEBUG):
    """
    """
    file_handler = logging.FileHandler(filename)
    file_handler.setFormatter(fmt)
    file_handler.setLevel(loglevel)
    return file_handler


def make_formatter(format_str="", date_format="%H:%M:%S"):
    if not format_str:
        format_str = "%(created)s-%(name)s-%(levelname)s: \t%(message)s"

    return logging.Formatter(fmt=format_str, datefmt=date_format)


def get_simple_logger(logname, filename, loglvl=logging.DEBUG):
    """
    Simple wrapper around the other functions to create a basic logger.  This is
    useful as a module level debugger
    """
    ## Do the stream handler and formatter
    stream_fmt = make_formatter()
    sh = make_stream_handler(stream_fmt)

    ## Make the filename, file handler and formatter
    fname = make_timestamped_filename(filename, postfix=".log")
    file_fmt = make_formatter()
    fh = make_file_handler(file_fmt, fname)

    ## get the actual logger
    logr =  make_logger(logname, (sh, fh))
    logr.setLevel(loglvl)
    return logr


def banner(logger, msgs, loglevel=logging.INFO,  highlight="=", length=20):
    logger.log(loglevel, highlight * length)
    for msg in msgs:
        logger.log(loglevel, msg)
    logger.log(loglevel, highlight * length)


glob_logger = get_simple_logger(__name__, __name__)