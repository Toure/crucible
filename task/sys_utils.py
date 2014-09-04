__author__ = 'toure'

import platform
import os
from paramiko import SSHClient
from scp import SCPClient


class Utils(object):

    @staticmethod
    def system_version():
        """
        :return: Version of RHEL to determine configuration logic.
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

    @staticmethod
    def rmt_copy(hostname, get=False, send=False, fname=None, remote_path=None):
        """Remote copy function retrieves files from specified host.
        :param remote_path: where to place the file on the other end.
        :param hostname: host name or ip address
        :param get: flag to receive files
        :param send: flag to send files
        :param fname: file name which to transport
        """
        ssh = SSHClient()
        ssh.load_system_host_keys()
        ssh.connect(hostname)
        scp = SCPClient(ssh.get_transport())
        if get:
            os.chdir('/tmp')
            scp.get(fname)
        elif send:
            scp.put(fname, remote_path=remote_path)

    @staticmethod
    def rmt_exec(hostname, cmd):
        ssh = SSHClient()
        ssh.connect(hostname)
        ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(cmd)
        return ssh_stdin, ssh_stdout, ssh_stderr

    @staticmethod
    def adj_val(token, value, o_file, n_file):
        """Change the value of the token in a given config file.
        :param token: key within the config file
        :param value: value for token
        :param o_file: current configuration file which to read data.
        :param n_file: new configuration file which to write out data.
        """
        if o_file == None:
            w = open(n_file, 'w')

        r = open(o_file, 'r')
        w = open(n_file, 'w')
        lines = r.readlines()
        for line in lines:
            line.split('=')
            if token in line[0]:
                if line[0].startswith('#'):
                    line[0] = line[0].replace('#', '')
                line[1] = value
            w.write('='.join(line))