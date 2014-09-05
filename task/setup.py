from task.sys_utils import Utils

__author__ = 'toure'

import os
import ConfigParser

try:
    from packstack.installer import run_setup
except ImportError as IE:
    print IE.message


class Base(object):
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


class Setup(Base, Utils):
    def __init__(self):
        super(Setup, self).__init__()
        self.rhel_ver = self.system_version()

    def system_setup(self):
        """
        System setup will determine RHEL version and configure the correct services per release info.
        """
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

        return 0

    def firewall_setup(self):
        """


        :return:
        """
        self.firewall_config = self.make_config_obj('firewall', '../configs/firewall')
        nfs_tcp = self.config_gettr(self.firewall_config, 'nfs rules')['tcp_ports']
        nfs_udp = self.config_gettr(self.firewall_config, 'nfs rules')['udp_ports']
        libvirtd_tcp = self.config_gettr(self.firewall_config, 'libvirtd rules')['tcp_ports']

        for host in self.nova_hosts:
            for ports in [nfs_tcp, nfs_udp, libvirtd_tcp]:
                cmd = "iptables -A INPUT -p tcp --dport {0:s} -j ACCEPT".format(ports)
                stdout = self.rmt_exec(host, cmd)
                if len(stdout[1]) == 0:
                    continue
                else:
                    raise EnvironmentError('The remote command failed {}'.format(stdout[1]))
        return 0

    def libvirtd_setup(self):
        """


        :return:
        """
        self.libvirtd_config = self.make_config_obj('libvirtd', '../configs/libvirtd')
        _libvirtd_conf = dict(self.libvirtd_config.items('libvirtd_conf'))
        _libvirtd_sysconf = dict(self.libvirtd_config.items('libvirtd_sysconfig'))

        for _dict_obj in [_libvirtd_conf, _libvirtd_sysconf]:
            self.rmt_copy(self.nova_hosts[0], get=True, fname=_dict_obj['filename'])

        for name, value in _libvirtd_conf:
            self.adj_val(name, value, o_file='libvirtd.conf', n_file='libvirtd.conf.new')
        self.adj_val('LIBVIRTD_ARGS', 'listen', o_file='libvirtd', n_file='libvirtd.new')

        self.renamer('/tmp')

        for host in self.nova_hosts:
            for _obj in [_libvirtd_conf, _libvirtd_sysconf]:
                file = _obj['filename']
                file = file.split('/')
                file_path = ('/'.join(file[1:3])) + '/'   # todo figure out a better format.
                self.rmt_copy(host, send=True, fname=file[3], remote_path=file_path)

        return 0

    def nova_setup(self):
        """Nova setup will configure all necessary files for nova to enable live migration."""

        self.nova_config = self.make_config_obj('nova', '../configs/nova')
        _nova_conf = dict(self.nova_config.items('nova_conf'))

        if self.rhel_ver >= 7:
            _nova_api_service = dict(self.nova_config.item('nova_api_service'))
            _nova_cert_service = dict(self.nova_config.item('nova_cert_service'))
            _nova_compute_service = dict(self.nova_config.item('nova_compute_service'))
            nova_config_list = [_nova_conf, _nova_api_service, _nova_cert_service, _nova_compute_service]
        else:
            nova_config_list = [_nova_conf]

        for conf in nova_config_list:
            self.rmt_copy(self.nova_hosts[0], get=True, fname=conf['filename'])
        for name, value in _nova_conf:
            self.adj_val(name, value, o_file='nova.conf', n_file='nova.conf.new')

    def nfs_server_setup(self):
        """


        """
        self.share_storage_config = self.make_config_obj('nfs_server', '../configs/share_storage')
        _nfs_export = self.config_gettr(self.share_storage_config, 'nfs_export')['export']
        _nfs_export_attribute = self.config_gettr(self.share_storage_config, 'nfs_export')['attribute']
        _nfs_export_net = self.config_gettr(self.share_storage_config, 'nfs_export')['network']
        _nfs_server_ip = self.config_gettr(self.share_storage_config, 'nfs_export')['nfs_server']
        _nfs_export_filename = self.config_gettr(self.share_storage_config, 'nfs_export')['filename']

        if self.rhel_ver >= 7:
            _nfs_idmapd_filename = self.config_gettr(self.share_storage_config, 'nfs_idmapd')['filename']
            _nfs_idmapd_domain = self.config_gettr(self.share_storage_config, 'nfs_idmapd')['domain']

        for file in [_nfs_export_filename, _nfs_idmapd_filename]:
            self.rmt_copy(_nfs_server_ip, get=True, fname=file)




        pass

    def nfs_client_setup(self):
        """


        """
        pass