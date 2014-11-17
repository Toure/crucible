__author__ = "Sean Toner"

from subprocess import Popen, PIPE, STDOUT
import threading
import os
import shlex

from crucible.utils.logger import glob_logger as LOGGER


LOG_DIR = "logs"
if not os.path.exists("logs"):
    os.mkdir("logs")
os.environ["PYTHONUNBUFFERED"] = "1"


def freader(fobj, save=None):
    """
    Small function which can be thrown into a thread to read a long running
    subprocess

    Args:
      - fobj: a file like object that will be read from
      - interval: polling interval between reads
      - save(list): by default dont save, otherwise append output to this
    """
    do_print = True
    if save is not None:
        buff = []

    while not fobj.closed:
        line = fobj.readline()  # blocks when nothing in fobj buffer
        if line and do_print:
            LOGGER.info(line)
        if save is not None:
            buff.append(line)


def creader(cobj, interval=0.2, save=None):
    freader(cobj.proc.stdout, save=save)


class Result:
    """A simple way of declaring a result from an operation"""
    def __init__(self, rc, msg="", data=None):
        """
        Args:
          - rc(int): an integer value for the returncode
          - msg(str): a descriptive message
          - data(any): relevant data from the operation
        """
        self.result = rc
        self.description = msg
        if data is None:
            self.data = {}
        else:
            self.data = data


class ResultException(Exception):
    pass


class ProcessResult:
    """
    Represents the result of a subprocess.

    Because we might run the subprocess in a non-blocking manner (ie, not
    calling communicate), this class represents the current state of the
    process.  That means we may not have the returncode, stdout or stderr
    yet.

    This class models a "truthiness" value so a ProcessResult object can
    be used in truth value testing.  It also implements the == operator
    to make it easier to do return code checking.  This was done because
    subclassing from int made no sense if the subprocess was not complete
    since the result of popen_obj.poll() or popen_obj.returncode would be
    None, and int types must have an int value ('inf' and 'nan' are for
    float types)
    """
    def __init__(self, command=None, outp="", error="", meta=None, logger=LOGGER):
        """
        Args:
          - cmdobj(Command): the Command object
          - outp(str): a str used to hold output
          - error(str): a str used to hold error
          - logger(logging): logging object
        """
        if command is None or not isinstance(command, Command):
            raise ResultException("Must pass in a command object")

        self.logger = logger
        self.cmd = command
        self.proc = command.proc
        self._output = outp
        self._error = error
        self._rdr_thr = None
        self.returncode = self.proc.poll()

    def __nonzero__(self):
        """
        Allows the ProcessResult object to be used for truthiness

        example::

            result = ProcessResult(proc)
            if result:
                print result.output
        """
        if self.returncode is not None:
            return True
        return False

    def __eq__(self, other):
        """
        Allows the ProcessResult object to be used for int equality
        checking.

        Usage::

            result = ProcessResult(proc)
            if result == 0:
                print("subprocess was successful")

        """
        if self.returncode == other:
            return True
        else:
            return False

    def _check_filehandle(self, fh_name="stdout"):
        try:
            stdout = getattr(self.proc, fh_name)
            if not stdout.closed:
                return stdout
        except AttributeError as ae:
            # TODO: no self.proc.stdout, check if self.proc is a file handle
            raise ae

    @property
    def output(self):
        outp = self._check_filehandle()
        if self.proc.poll() is None:
            self.logger.warning("Process is not yet finished")
            lines = []
            rdr_thread = threading.Thread(target=freader, args=(outp,),
                                          kwargs={"save": lines})
            rdr_thread.start() 
            self._rdr_thr = rdr_thread
        elif not self._output:
            
            self._output = outp.read() # this will block

        return self._output

    @output.setter
    def output(self, val):
        self.logger.error("output is read-only. Not setting to {}".format(val))


class CommandException(Exception):
    def __init__(self, msg=""):
        super(CommandException, self).__init__()
        self.msg = msg


class Command(object):
    """
    A class to handle executing subprocesses.  

    The intention is to allow a simpler way to handle threading or multiprocessing 
    functionality.  This also allows the caller to chose to block (waiting for the 
    subprocess to return) or not.
    """
    def __init__(self, cmd=None, sudo=False, pw="", logr=None, stdin=PIPE,
                 stdout=PIPE, stderr=STDOUT, saveout=True):
        """
        *Args:*
            - cmd(str|list): The command to be executed, either in string or list format
            - logr(Logger): a logging.Logger instance. if None, use the module LOGGER
            - stdout(file-like): by default uses PIPE, but can be any file-like object
            - stderr(file-like): same as stdout
            - comb_err(bool): combine stderr to stdout
        """
        self.cmd = cmd
        self.out = stdout
        self.err = stderr
        self.inp = stdin
        self.fails = {}
        self.sudo = sudo
        self.pw = pw
        self.saveout = saveout
        if logr:
            self.logger = logr
        else:
            self.logger = LOGGER

    def __call__(self,
                 cmd=None,
                 showout=True,
                 showerr=True,
                 block=True,
                 checkresult=(True, 0),
                 **kwds):
        """
        This is a wrapper around subprocess.Popen constructor.  The **kwds
        takes the same keyword args as the Popen constructor does.  During
        initialization, by default PIPE will be used for the stdout and stderr,
        however, file-like objects may be passed in instead (for example to
        log)

        *Args:*
            - cmd(str|list): the command and arguments to run
            - showout(bool): whether to show output or not
            - showerr(bool): whether to show stderr or not
            - block(bool)-=: if false, return immediately, else wait for subprocess
            - checkresult((bool,int)): first element is to do checking,
                                       second is success return code
            - kwds: keyword arguments which will be passed through to the 
                    Popen() constructor

        *Return*
            A ProcessResult object
        """
        meta = {"cmd": cmd, "showout": showout, "showerr": showerr, 
                "block": block, "checkresult": checkresult, "kwds": kwds}
        if not cmd and not self.cmd:
            raise CommandException("Must have a command to execute")
        if cmd:
            self.cmd = cmd

        if isinstance(self.cmd, str):
            cmd_toks = shlex.split(self.cmd)
        else:
            cmd_toks = self.cmd

        if self.sudo:
            cmd_toks = ["sudo"] + cmd_toks

        kwds['stdout'] = self.out
        kwds['stderr'] = self.err
        kwds['stdin'] = self.inp

        ## Setup our return vals
        output = None
        err = None

        if block:
            proc = Popen(cmd_toks, **kwds)
            (output, err) = proc.communicate()  # FIXME: what about input?
            if showout and output:
                self.logger.info(output)
            if showerr and err:
                self.logger.error(err)
        else:
            proc = Popen(cmd_toks, **kwds)

        self.proc = proc
        result = (proc, output, err, meta)
        proc_res = {"command": self, 
                    "outp": output,
                    "error": err, 
                    "meta": meta,
                    "logger": LOGGER}

        if checkresult[0]:
            self.check_result(result, checkresult[1])
        return ProcessResult(**proc_res)

    def check_result(self, result, success=0, throws=False):
        """
        Simple checker for the return of a subprocess.

        *args*
            result(tuple)- same type as return from __call__()
            success(int)- the return code that indicates success
        """
        proc, output, err, _ = result
        returnval = proc.poll()
        if returnval == None:
            self.logger.warn("Process is still running")
            return None
        elif proc.returncode != success:
            self.logger.error("ReturnCode: {0}".format(returnval))
            self.logger.error("stderr: {0}".format(err))
            self._add_fail(result)
            if throws:
                raise CommandException("Command failed with return code {}".format(proc.returncode))
        else:
            self.logger.info("Process was successful")
        return returnval

    def _add_fail(self, result):
        proc, out, err = result
        self.fails[proc.pid] = {"returncode": proc.returncode,
                                "errmsg": err,
                                "command": self.cmd }

    def make_proxy(self, handler, *args, **kwds):
        """
        Spawns a thread so that we can read the stdout of a long running subprocess

        *Args:*
          - handler: the function that will be called in the new thread
          - args: the positional args to be passed to the handler
          - kwds: the keyword args to be passed to the handler

        *Return*
            The thread object which will monitor the stdout of the subprocess

        Usage::

            cmd = Command()
            result = cmd("python some_long_script.py --time=240", block=False)
            printer_thread = cmd.make_proxy(freader, result.proc.stdout)
            printer_thread.start()
            printer_thread.join()  ## only if your parent thread might finish before the thread

        PostCondition-
            When using this function, make sure that after calling start() on the
        thread, that the child thread may not outlive the parent thread.  This will
        result in undefined behavior.
        """

        class CommandProxy(threading.Thread):
            def __init__(self, hdl, *args, **kwds):
                super(CommandProxy, self).__init__()
                self.handler = hdl
                self.args = args
                self.kwds = kwds

            def run(self):
                self.handler(*self.args, **self.kwds)

        return CommandProxy(handler, *args, **kwds)



if __name__ == "__main__":
    cmd = Command("iostat -d 2 10 ")
    res = cmd(block=False)
    rdr_t = cmd.make_proxy(freader, res.proc.stdout)
    rdr_t.daemon = True
    rdr_t.start()
    import time

    while res.proc.poll() is None:
        time.sleep(1)
