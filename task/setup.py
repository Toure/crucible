from task.os_info import OSVer

__author__ = 'toure'

import os
import sys
import readline
import ConfigParser
from paramiko import SSHClient
from scp import SCPClient

try:
    from packstack.installer import run_setup
except ImportError as IE:
    print IE.message


class Base(OSVer):
    """
    Base class for system configuration
    """
    def __init__(self):
        self.firewall_config = None
        self.libvirtd_config = None
        self.nova_config = None
        self.share_storage_config = None
        self.system_info_config = None
        self.nova_hosts = None

    def make_config_obj(self, cfgname, path):
        """
        helper function to allow for dynamic instances of configparser.
        :param cfgname: ini file config object.
        :param path: ini file path for configparser to read.
        :return: configparser object for self.cfgname
        """
        try:
            setattr(self, cfgname, ConfigParser.ConfigParser())
            obj = getattr(self, cfgname)
            obj.read(path)
            return obj
        except AttributeError as AE:
            print AE.message

    def config_gettr(self, config_reader, section):
        """
        helper function to decipher the config file values.
        :param config_reader: ConfigParser read object
        :param section: the location inside the config file where keys and values are stored
        """
        bucket = {}
        for value in config_reader.options(section):
            try:
                bucket[value] = config_reader.get(section, value)
                if bucket[value] == -1:
                    print('No value found %s' % value)
            except KeyError:
                print("exception on %s!" % value)
                bucket[value] = None
        return value

    def rmt_copy(self, hostname, get=False, send=False, fname=None, remote_path=None):
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

    def rmt_exec(self, hostname, cmd):
        ssh = SSHClient()
        ssh.connect(hostname)
        ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(cmd)
        return ssh_stdin, ssh_stdout, ssh_stderr

    def adj_val(self, token, value, oldfile=None, newfile=None):
        """Change the value of the token in a given config file.
        :param token: key within the config file
        :param value: value for token
        :param filename: specified config file
        """
        r = open(oldfile, 'r')
        w = open(newfile, 'w')
        lines = r.readlines()
        for line in lines:
            line.split('=')
            if token in line[0]:
                if line[0].startswith('#'):
                    line[0] = line[0].replace('#', '')
                line[1] = value
            w.write('='.join(line))

    def system_setup(self):
        """
        System setup will determine RHEL version and configure the correct services per release info.
        """
        #rhel_ver = {6: "upstart", 7: "systemd"}
        #rhel_env = rhel_ver[OSVer.system_version()]
        self.system_info_config = self.make_config_obj('sys_info', '../configs/system_info')
        answerfile = self.config_gettr(self.system_info_config, 'packstack')['filename']
        run_setup.generateAnswerFile(answerfile)

        if os.path.exists(answerfile):
            self.nova_hosts = self.config_gettr(self.system_info_config, 'nova')['NOVA_COMPUTE_HOSTS']
            answer_file = self.make_config_obj('packstack_ans', answerfile)
            try:
                answer_file.set('general', 'CONFIG_COMPUTE_HOSTS', self.nova_hosts)
            except IOError as e:
                print e.message
            run_setup._main(configFile=answerfile)
        else:
            print("Couldn't find packstack answer file")
            exit()

    def firewall_setup(self):
        self.firewall_config = self.make_config_obj('firewall_rules', '../configs/firewall')
        nfs_tcp = self.config_gettr(self.firewall_config, 'nfs rules')['tcp_ports']
        nfs_udp = self.config_gettr(self.firewall_config, 'nfs rules')['udp_ports']
        libvirtd_tcp = self.config_gettr(self.firewall_config, 'libvirtd rules')['tcp_ports']

        for host in self.nova_hosts:
            for ports in [nfs_tcp, nfs_udp, libvirtd_tcp]:
                cmd = u"iptables -A INPUT -p tcp --dport {0:s} -j ACCEPT".format(ports)
                self.rmt_exec(host, cmd)

    def libvirtd_setup(self):
        self.libvirtd_config = self.make_config_obj('libvirt_conf', '../configs/libvirtd')
        _libvirtd_conf = dict(self.libvirtd_config.items('libvirtd_conf'))
        _libvirtd_sysconf = dict(self.libvirtd_config.items('libvirtd_sysconfig'))

        for _dict_obj in [_libvirtd_conf, _libvirtd_sysconf]:
            self.rmt_copy(self.nova_hosts[0], get=True, fname=_dict_obj['filename'])

        for name, value in _libvirtd_conf:
            self.adj_val(name, value, oldfile='libvirtd.conf', newfile='libvirtd.conf.new')
        self.adj_val('LIBVIRTD_ARGS', 'listen', oldfile='libvirtd', newfile='libvirtd.new')

        try:
            os.rename('libvirtd.conf', 'libvirtd.conf.org')
            os.rename('libvirtd', 'libvirtd.org')
        except IOError as ie:
            print ie.message
            exit()

        try:
            os.rename('libvirtd.conf.new', 'libvirtd.conf')
            os.rename('libvirtd.new', 'libvirtd')
        except IOError as ie:
            print ie.message
            exit()

        for host in self.nova_hosts:
            for _obj in [_libvirtd_conf, _libvirtd_sysconf]:
                file = _obj['filename']
                file = file.split('/')
                file_path = ('/'.join(file[1:3]))
                self.rmt_copy(host, send=True, fname=file[3], remote_path=file_path)



    def nova_setup(self):
        pass
