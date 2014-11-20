__author__ = 'stoner'

from subprocess import Popen, PIPE, STDOUT
from paramiko import SSHClient, AutoAddPolicy
from functools import wraps


def require_remote(progname, valid=None):
    """
    Decorator that validates some system command exists on the remote system.  The wrapped function
    must contain a kwargs dictionary with the following keys:

    host: The ip address of the machine we are executing remote command on
    username: the user of the remote machine we wish to run command on
    password: the password for that user

    :param progname: program name to check (passed to which)

    :return:
    """
    if valid is None:
        valid = [0]

    def outer(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            cmd = "which {0}".format(progname)
            client = SSHClient()
            client.set_missing_host_key_policy(AutoAddPolicy())

            ip = kwargs["host"]
            user = kwargs["username"]
            pw = kwargs["password"]

            client.connect(ip, username=user, password=pw, port=22)
            out, err, inp = client.exec_command(cmd)
            if out.channel.recv_exit_status() not in valid:
                # Try to install
                cmd = "yum install {0}".format(progname)
                out, err, inp = client.exec_command(cmd)
                if out.channel.recv_exit_status() not in valid:
                    raise Exception("{0} is not on the remote machine".format(progname))
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
                raise Exception("{0} is not on this machine".format(progname))
            return fn(*args, **kwargs)
        return inner
    return outer