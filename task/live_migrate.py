from task.sys_utils import Utils

__author__ = 'toure'

import os
import ConfigParser
from configs.configs import get_path
from subprocess import call
from threading import RLock

from task.utils.logger import glob_logger as LOGGER
from task.utils.logger import banner


class Base(object):
    """
    Base class for system configuration
    """
    def __init__(self, logger=LOGGER):
        self.firewall_config_obj = None
        self.libvirtd_config_obj = None
        self.nova_config_obj = None
        self.share_storage_config_obj = None
        self.system_info_obj = None
        self.nova_hosts_value = None
        self.rlock = RLock()
        self.logger = logger

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
            obj.optionxform = str
            obj.read(path)
            return obj
        except AttributeError:
            raise AttributeError("Could not create instance object with current info: cfgname {0}, path {1}".format(cfgname, path))

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
            except ValueError:
                print("exception on %s!" % value)
                bucket[value] = None
        return bucket


class Config(Base, Utils):
    def __init__(self, logger=LOGGER):
        super(Config, self).__init__(logger=logger)
        self.rhel_ver = self.system_version()
        self.ssh_creds_obj = self.make_config_obj('ssh_creds', get_path('system_info'))
        self.system_info_obj = self.make_config_obj('sys_info', get_path('system_info'))
        self.firewall_config_obj = self.make_config_obj('firewall', get_path('firewall'))
        self.libvirtd_config_obj = self.make_config_obj('libvirtd', get_path('libvirtd'))
        self.nova_config_obj = self.make_config_obj('nova', get_path('nova'))
        self.nova_hosts_value = self.config_gettr(self.system_info_obj, 'nova')['nova_compute_hosts']
        self.nova_hosts_list = str(self.nova_hosts_value).split(',')
        self.share_storage_config_obj = self.make_config_obj('nfs_server', get_path('share_storage'))
        self.ssh_uid = self.config_gettr(self.ssh_creds_obj, 'ssh_creds')['username']
        self.ssh_pass = self.config_gettr(self.ssh_creds_obj, 'ssh_creds')['password']

    def system_setup(self):
        """System setup will determine RHEL version and configure the correct services per release info.
        """
        banner(self.logger, ["Checking to see if Packstack will be run..."])
        to_install = self.config_gettr(self.system_info_obj, 'install')['install']
        if 'n' in to_install:
            return True

        answerfile = self.config_gettr(self.system_info_obj, 'packstack')['filename']
        call(['packstack', '--gen-answer-file', answerfile])

        if os.path.exists(answerfile) and os.stat(answerfile)[6] != 0:
            #check to see if the file exist and its not empty.
            self.logger.debug("Creating backup file for answerfile")
            try:
                self.adj_val('CONFIG_COMPUTE_HOSTS', self.nova_hosts_value, answerfile, answerfile + '.bak')
            except IOError:
                raise IOError("Couldn't rename {0}".format(answerfile))

            banner(self.logger, ["Running packstack installer, using {0} file".format(answerfile)])
            call(['packstack', '--answer-file', answerfile])
        else:
            self.logger.error("Couldn't find packstack answer file: {0}".format(answerfile))
            exit()

        return True

    def firewall_setup(self):
        """Firewall setup will open necessary ports on all compute nodes to allow libvirtd, nfs_server to
        communicate with their clients.

        :return: upon success zero is returned if not an exception is raised.
        """
        nfs_tcp = self.config_gettr(self.firewall_config_obj, 'nfs rules')['tcp_ports']
        nfs_udp = self.config_gettr(self.firewall_config_obj, 'nfs rules')['udp_ports']
        libvirtd_tcp = self.config_gettr(self.firewall_config_obj, 'libvirtd rules')['tcp_ports']

        self.logger.info("=" * 20)
        self.logger.info("Setting up firewall rules")
        for host in self.nova_hosts_list:
            for proto, ports in [("tcp", nfs_tcp), ("udp", nfs_udp), ("tcp", libvirtd_tcp)]:
                cmd = "iptables -A INPUT -m multiport -p {0} --dport {1:s} -j ACCEPT".format(proto, ports)
                ret = self.rmt_exec(str(host), cmd, username=self.ssh_uid, password=self.ssh_pass)
                self.logger.info("Issued: {0}, ret={1}".format(cmd, ret))
                if len(ret[1]) == 0:
                    continue
                else:
                    raise EnvironmentError('The remote command failed {0}'.format(ret[1]))

            ipsave_cmd = "service iptables save"
            self.rmt_exec(str(host), ipsave_cmd, username=self.ssh_uid, password=self.ssh_pass)
        self.logger.info("+" * 20)
        return True

    def libvirtd_setup(self):
        """ libvirtd setup will configure libvirtd to listen on the external network interface.

        :return: upon success zero is returned if not an exception is raised.
        """
        if os.path.isdir('/tmp/libvirtd_conf'):
            os.chdir('/tmp/libvirtd_conf')
        else:
            os.mkdir('/tmp/libvirtd_conf')
            os.chdir('/tmp/libvirtd_conf')

        _libvirtd_conf = dict(self.libvirtd_config_obj.items('libvirtd_conf'))
        _libvirtd_sysconf = dict(self.libvirtd_config_obj.items('libvirtd_sysconfig'))
        banner(self.logger, ["_libvirtd_conf: {0}".format(_libvirtd_conf),
                             "_libvirtd_sysconf: {0}".format(_libvirtd_sysconf)])

        for _dict_obj in [_libvirtd_conf, _libvirtd_sysconf]:
            self.rmt_copy(self.nova_hosts_list[0], username=self.ssh_uid, password=self.ssh_pass,
                          fname=_dict_obj['filename'], remote_path=_dict_obj['filepath'])

        for name, value in _libvirtd_conf.items():
            self.adj_val(name, value, 'libvirtd.conf', 'libvirtd.conf.bak')
        self.adj_val('LIBVIRTD_ARGS', '--listen', 'libvirtd', 'libvirtd.bak')

        for host in self.nova_hosts_list:
            for _obj in [_libvirtd_conf, _libvirtd_sysconf]:
                self.rmt_copy(host, username=self.ssh_uid, password=self.ssh_pass,
                              send=True, fname=_obj['filename'], remote_path=_obj['filepath'])

            self.rmt_exec(host, "systemctl enable libvirtd.service", username=self.ssh_uid, password=self.ssh_pass)

        return True

    def nova_setup(self):
        """Nova setup will configure all necessary files for nova to enable live migration."""

        if os.path.isdir('/tmp/nova_conf'):
            os.chdir('/tmp/nova_conf')
        else:
            os.mkdir('/tmp/nova_conf')
            os.chdir('/tmp/nova_conf')

        banner(self.logger, ["Doing nova.conf configuration"])

        def nova_adjust(nova_config_list):
            for _conf in nova_config_list:
                self.logger.info("Copying {0} to {1}".format(_conf['filename'], _conf['filepath']))
                self.rmt_copy(self.nova_hosts_list[0], username=self.ssh_uid, password=self.ssh_pass,
                              fname=_conf['filename'], remote_path=_conf['filepath'])
                for name, value in _conf.items():
                    self.adj_val(name, value, _conf['filename'], _conf['filename'] + '.bak')

            return True

        _nova_conf = dict(self.nova_config_obj.items('nova_conf'))
        cmd = "mkdir {0}".format(_nova_conf['state_path'])

        if self.rhel_ver >= 7:
            self.logger.info("Doing nova setup for RHEL 7")
            _nova_api_service = dict(self.nova_config_obj.items('nova_api_service'))
            _nova_cert_service = dict(self.nova_config_obj.items('nova_cert_service'))
            _nova_compute_service = dict(self.nova_config_obj.items('nova_compute_service'))
            _nova_config_list = [_nova_conf, _nova_api_service, _nova_cert_service, _nova_compute_service]

            nova_adjust(_nova_config_list)

        else:
            self.logger.info("Doing nova setup for RHEL 6")
            _nova_config_list = [_nova_conf]
            nova_adjust(_nova_config_list)

        for host in self.nova_hosts_list:
            for conf in _nova_config_list:
                self.rmt_copy(host, username=self.ssh_uid, password=self.ssh_pass,
                              send=True, fname=conf['filename'], remote_path=conf['filepath'])
            self.rmt_exec(host, cmd, username=self.ssh_uid, password=self.ssh_pass)

        return True

    def nfs_server_setup(self):
        """ NFS_Server setup will create an export file and copy this file to the nfs server, it will also
        determine the release of RHEL and configure version 3 or 4 nfs service.

        """
        if os.path.isdir('/tmp/nfs_conf'):
            os.chdir('/tmp/nfs_conf')
        else:
            os.mkdir('/tmp/nfs_conf')
            os.chdir('/tmp/nfs_conf')

        _nfs_export = self.config_gettr(self.share_storage_config_obj, 'nfs_export')['export']
        _nfs_export_attribute = self.config_gettr(self.share_storage_config_obj, 'nfs_export')['attribute']
        _nfs_export_net = self.config_gettr(self.share_storage_config_obj, 'nfs_export')['network']
        _nfs_server_ip = self.config_gettr(self.share_storage_config_obj, 'nfs_export')['nfs_server']
        _nfs_export_obj = dict(self.share_storage_config_obj.items('nfs_export'))

        banner(self.logger, ["Doing NFS server setup"])

        if self.rhel_ver >= 7:
            _nfs_idmapd_obj = dict(self.share_storage_config_obj.items('nfs_idmapd'))
            _nfs_idmapd_domain = self.config_gettr(self.share_storage_config_obj, 'nfs_idmapd')['domain']
            self.rmt_copy(_nfs_server_ip, get=True, fname=_nfs_idmapd_obj['filename'],
                          remote_path=_nfs_idmapd_obj['filepath'])
            self.adj_val('Domain', _nfs_idmapd_domain, _nfs_idmapd_obj['filename'],
                         _nfs_idmapd_obj['filename'] + '.bak')
            self.rmt_copy(_nfs_server_ip, username=self.ssh_uid, password=self.ssh_pass,
                          send=True, fname=_nfs_idmapd_obj['filename'], remote_path=_nfs_idmapd_obj['filepath'])

        nfs_exports_info = [_nfs_export, _nfs_export_net + _nfs_export_attribute]
        export_fn = self.gen_file(_nfs_export_obj['filename'], nfs_exports_info)
        self.rmt_copy(_nfs_server_ip, username=self.ssh_uid, password=self.ssh_pass,
                      send=True, fname=export_fn, remote_path=_nfs_export_obj['filepath'])

        return True

    def nfs_client_setup(self):
        """NFS client function will append mount option for live migration to the compute nodes fstab file.

        """
        if os.path.isdir('/tmp/nfs_conf'):
            os.chdir('/tmp/nfs_conf')
        else:
            os.mkdir('/tmp/nfs_conf')
            os.chdir('/tmp/nfs_conf')

        banner(self.logger, ["Doing NFS client setup"])
        _fstab_filename = self.config_gettr(self.system_info_obj, 'fstab')['filename']
        _nfs_server = self.config_gettr(self.system_info_obj, 'fstab')['nfs_server']
        _nfs_mount_pt = self.config_gettr(self.system_info_obj, 'fstab')['nfs_client_mount']
        _nfs_fstype = self.config_gettr(self.system_info_obj, 'fstab')['fstype']
        _mnt_opts = self.config_gettr(self.system_info_obj, 'fstab')['attribute']
        _fsck_opt = self.config_gettr(self.system_info_obj, 'fstab')['fsck']

        fstab_entry = [_nfs_server, _nfs_mount_pt, _nfs_fstype, _mnt_opts, _fsck_opt]
        fstab_entry = "    ".join(fstab_entry)

        system_util = '/usr/bin/echo '

        system_util_operator = ' >> '

        cmd = [system_util, fstab_entry, system_util_operator, _fstab_filename]
        rmt_cmd = " ".join(cmd)

        for host in self.nova_hosts_list:
            ret = self.rmt_exec(str(host), rmt_cmd, username=self.ssh_uid, password=self.ssh_pass)
            if len(ret[1]) == 0:
                continue
            else:
                raise EnvironmentError('The remote command failed {0}'.format(ret[1]))

        return True
