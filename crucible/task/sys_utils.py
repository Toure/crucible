__author__ = 'Toure Dunnon'
__credits__ = ['Toure Dunnon', 'Sean Toner']
__license__ = 'GPL'
__version__ = '2.1.0'
import platform
import os
import re
import logging

from paramiko import SSHClient
from paramiko import AutoAddPolicy

from scpclient import closing
from scpclient import Read
from scpclient import Write
from crucible.task.utils.logger import glob_logger as LOGGER


TRACE = logging.DEBUG


class Utils(object):

    def system_version(self):
        """
        :return: RHEL release version number.
        """
        distro_name = platform.linux_distribution()
        version = float(distro_name[1])
        if version >= 7.0:
            return 7
        elif version <= 6.9:
            return 6
        else:
            print('This is an unsupported distribution version: %s' % distro_name)
            exit()

    def rmt_copy(self, hostname, username=None, password=None, send=False,
                 fname=None, remote_path=None):
        """Remote copy function retrieves files from specified host.

        :param hostname: host name or ip address
        :param username: user which will have privalege to copy files to and from system.
        :param password: password for defined user.
        :param send: flag to send files. by default copy from remote (send=false)
        :type  send: bool
        :param fname: file name which to transport
        :param remote_path: where to place the file on the other end.
        """
        ssh = SSHClient()
        ssh.set_missing_host_key_policy(AutoAddPolicy())
        ssh.connect(hostname, username=username, password=password)

        if not send:
            with closing(Read(ssh.get_transport(), remote_path)) as scp:
                scp.receive_file(fname)
        else:
            with closing(Write(ssh.get_transport(), remote_path)) as scp:
                scp.send_file(fname, send)

    def rmt_exec(self, hostname, cmd, username=None, password=None):
        """Remote execution function to run defined commands.

        :param hostname: server hostname in which to run command.
        :param cmd: system command which will be ran from a remote shell.
        :param username: user with sufficient privilege to execute defined command.
        :param password: password for user.
        :return: list that contains standard shell information.
         ei. rmt_exec('localhost', 'date') ==> ['Fri Sep  5 12:16:58 EDT 2014\n']
        """
        ssh = SSHClient()
        ssh.set_missing_host_key_policy(AutoAddPolicy())
        ssh.connect(hostname, port=22, username=username, password=password)
        ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(cmd)

        ssh_stdoutput = ssh_stdout.readlines()
        ssh_stderror = ssh_stderr.readlines()

        try:
            LOGGER.debug("Issued cmd: {0}".format(cmd))
            LOGGER.debug("stdout: {0}".format("".join(ssh_stdoutput)))
            LOGGER.debug("stderr: {0}".format("".join(ssh_stderror)))
        except:
            pass
        finally:
            return ssh_stdoutput, ssh_stderror

    @staticmethod
    def make_backup_file(orig_f, backup_f, o_file):
        pristine_name = o_file + ".orig"
        try:
            if not os.path.exists(pristine_name):
                pristine_f = open(pristine_name, "w")
                pristine_f.write(orig_f.read())
                pristine_f.close()
                orig_f.seek(0, 0)

            txt = orig_f.read()
            backup_f.write(txt)
            backup_f.close()
            orig_f.close()
        except IOError:
            raise "Could not create requested file: {0}".format(orig_f)

    def adj_val(self, token, value, o_file, b_file, not_found="ignore", delim=None):
        """Change the value of the token in a given config file.

        :param token: key within the config file
        :param value: value for token
        :param o_file: current configuration file which to read data.
        :param b_file: backup configuration file which to write out original data
            before changing the original file.
        :param not_found: can be one of 'ignore', 'append', or 'fail'.  If ignore, if no match is found by the end
            of the file, ignore just doesn't write, append will append at the end of the file, and fail will throw
            an exception
        :param delimiter: If specified, use delim as the delimiter instead of what is found from the regex.
        """

        #Write a backup before changing the original.
        di = os.getcwd()
        LOGGER.log(TRACE, "Trying to set {0} to {1} in file {2}".format(token, value, o_file))
        org_file = open(o_file, 'r')
        backup_file = open(b_file, 'w')
        self.make_backup_file(org_file, backup_file, o_file)

        try:
            new_file = open(o_file, 'w')  # here is where we overwrite the
                                          # original file after creating a backup.
            backup_file = open(b_file, 'r')
            new_lines = backup_file.readlines()

            # This is a regex to read a line, and see if we have a match.  If it
            # matches, match.groups() will return 4 capturing groups: a comment
            # key, delimiter, and value
            s = r"(#\s*)*\s*({0})(\s*[=: ]\s*)(.*)".format(token)
            patt = re.compile(s)

            found = []
            matched = False
            for line in new_lines:
                m = patt.search(line)
                if m:
                    comment, key, delimiter, val = m.groups()
                    if delim == "strip":
                        delimiter = delimiter.strip()
                    else:
                        delimiter = delim if delim is not None else delimiter
                    # If we've already found the token, skip it
                    if key in found:
                        LOGGER.log(TRACE, "Already found {0} in {1}".format(token, line))
                        if comment is None:
                            continue   # don't write out the line, since we already wrote it out
                    else:
                        line = "{0}{1}{2}\n".format(token, delimiter, value)
                        LOGGER.log(TRACE, "Matched {0} to {1}, writing out {2}".format(token, key, line))
                        found.append(key)
                        matched = True
                new_file.write(line)

            if not matched:
                if not_found == "fail":
                    raise Exception("Could not find {0} in file {1}".format(token, o_file))
                elif not_found == "append":
                    line = "{0}{1}{2}\n".format(token, delim, value)
                    LOGGER.log(TRACE, "{0} was not found in {1}. Appending {2}".format(token, o_file, line))
                    new_file.write(line)

            new_file.close()
            backup_file.close()
        except IOError:
            print("Could complete requested file modification on: "
                  "{0} and {1}".format(o_file, b_file))
            exit()

    def gen_file(self, filename, value):

        """gen_file will create a new file according to the input provided.

        :param filename: output name for the configuration file to be written.
        :param value: is a list of data to be written to the given config file.
        """
        try:
            fh = open(filename, 'w')
        except IOError as e:
            print "Couldn't create {0}: {1}".format(filename, e.strerror)
            print e.message

        for i in value:
            fh.write('%s   ' % i)

        try:
            fh.close()
            return filename
        except IOError as ie:
            print "Couldn't close {0} do to: {1}".format(filename, ie.strerror)
            print ie.message

