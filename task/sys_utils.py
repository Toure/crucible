__author__ = 'toure'


import platform
import os
from paramiko import SSHClient
from paramiko import AutoAddPolicy
try:
    from scpclient import closing, Read, Write
except ImportError:
    from subprocess import call
    call('pip', 'install', 'scpclient')


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

    def rmt_copy(self, hostname, username='root', password='qum5net', get=False,
                 send=False, fname=None, remote_path=None, local_path=None):
        """Remote copy function retrieves files from specified host.

        :param hostname: host name or ip address
        :param username: user which will have privalege to copy files to and from system.
        :param password: password for defined user.
        :param get: flag to receive files
        :type  get: bool
        :param send: flag to send files
        :type  send: bool
        :param fname: file name which to transport
        :param remote_path: where to place the file on the other end.
        """
        if send is get:
            raise ValueError('Please set the direction for file copy.')
        ssh = SSHClient()
        ssh.set_missing_host_key_policy(AutoAddPolicy())
        ssh.connect(hostname, username=username, password=password)
        if get:
            with closing(Read(ssh.get_transport(), remote_path)) as scp:
                scp.receive_file(fname)
        elif send:
            with closing(Write(ssh.get_transport(), remote_path)) as scp:
                scp.send_file(fname, send)

    def rmt_exec(self, hostname, cmd, username='root', password='qum5net'):
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

        return ssh_stdoutput, ssh_stderror

    def adj_val(self, token, value, o_file, n_file):
        """Change the value of the token in a given config file.

        :param token: key within the config file
        :param value: value for token
        :param o_file: current configuration file which to read data.
        :param n_file: new configuration file which to write out data.
        """
        r = open(o_file, 'r')
        w = open(n_file, 'w')
        lines = r.readlines()
        for line in lines:
            if token in line:
                if '=' in line:
                    delimiter = '='
                elif ':' in line:
                    delimiter = ':'
                else:
                    continue
            else:
                w.write(line)
                continue
            line = line.split(delimiter)
            if token in line[0]:
                if line[0].startswith('#'):
                    line[0] = line[0].replace('#', '')
                line[1] = value
            w.write('='.join(line[0:2]))
        w.close()
        r.close()

    def gen_file(self, filename, value, nfs_export=False):

        """gen_file will create a new file according to the input provided.

        :param filename: output name for the configuration file to be written.
        :param value: is a list of data to be written to the given config file.
        :param nfs_export: flag which determines to format output for /etc/exports
        """
        try:
            fh = open(filename, 'w')
        except IOError as e:
            print "Couldn't create {0}: {1}".format(filename, e.strerror)
            print e.message

        if nfs_export:
            value[1:3] = [''.join(value[1:3])]

        for i in value:
            fh.write('%s   ' % i)

        try:
            if fh.close():
                return filename
        except IOError as ie:
            print "Couldn't close {0} do to: {1}".format(filename, ie.strerror)
            raise ie

    def renamer(self, file_path='.'):

        """rename is a function responsible for taking the original configuration files and swapping them
        with the newly altered configuration file.

        :param file_path: directory path in which to find files. default: to present working directory.
        """
        file_ext = {'conf': '.conf.org', 'conf.new': '.conf', 'txt': '.txt.org',
                    'txt.new': '.txt', '': '_org', 'new': ''}
        for _file in os.listdir(file_path):
            for ext in file_ext.items():
                if _file.endswith(ext[0]):
                    _file_new = _file.split('.')
                    try:
                        os.chdir(file_path)
                        os.rename(_file, _file_new[0] + file_ext[ext[0]])
                    except IOError as ie:
                        print ie.message
        return 1



