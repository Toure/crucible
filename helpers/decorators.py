__author__ = 'stoner'

from subprocess import Popen, PIPE, STDOUT
from paramiko import SSHClient, AutoAddPolicy
from functools import wraps


def require_remote(progname, ip, user, pw, valid=[0]):
    """
    Decorator that validates some system command exists on the remote system

    :param progname: program name to check (passed to which)
    :param ip: The ip address of the remote system
    :param: user
    :return:
    """
    def outer(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            cmd = "which {}".format(progname)
            client = SSHClient()
            client.set_missing_host_key_policy(AutoAddPolicy())
            client.connect(ip, username=user, password=pw, port=22)
            out, err, inp = client.exec_command(cmd)
            if out.recv_exit_status() not in valid:
                raise Exception("{} is not on the remote machine")
            return fn(*args, **kwargs)
        return wrapper
    return outer


def require_local(progname, valid=[0]):
    """
    Checks that a command exists on the local system
    :param progname:
    :param valid:
    :return:
    """
    def outer(fn):
        @wraps(fn)
        def inner(*args, **kwargs):
            cmd = "which {}".format(progname)
            proc = Popen(cmd, shell=True, stdout=PIPE, stderr=STDOUT)
            out, _ = proc.communicate()
            if proc.returncode not in valid:
                raise Exception("{} is not on this machine".format(progname))
            return fn(*args, **kwargs)
        return inner
    return outer