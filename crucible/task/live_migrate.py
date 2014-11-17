from crucible.task.sys_utils import Utils

__author__ = 'Toure Dunnon'
__credits__ = ['Toure Dunnon', 'Sean Toner']
__license__ = 'GPL'
__version__ = '2.1.0'

import os
import ConfigParser
from crucible.configs.configs import get_path
from subprocess import call
from threading import RLock
import sys
import re
import shutil
import platform


from crucible.utils.logger import glob_logger as LOGGER
from crucible.utils.logger import banner


def get_args(args=None):
    major, minor, micro = platform.python_version_tuple()
    if minor == '6':
        from optparse import OptionParser as Parser
        parser = Parser(description='Live Migration Setup Util.  All of the command line options are optional, and'
                                    'if none are used, then the files in the config folder will be used.  If any'
                                    'options are given on the command line, they will override the config files, and'
                                    'those settings will be used instead')
        add_opt = parser.add_option
        parse_args = lambda x: x.parse_args(args)[0]
    else:
        from argparse import ArgumentParser as Parser
        parser = Parser(description='Live Migration Setup Util.')
        add_opt = parser.add_argument
        parse_args = lambda x: x.parse_args(args)

    add_opt("--controller", help="IP address of the controller/compute 1 node")
    add_opt("--compute2", help="IP address of the 2nd compute node")
    add_opt("--gen-sys-info", help="generate a new system_info config")
    add_opt("--gen-storage", help="Generate a new share_storage config file")
    add_opt("--gen-only", help="Only generate the new config file(s) the quit", action="store_true", default=False)
    add_opt("--no-packstack", help="Dont install packstack. (default is false)", action="store_true", default=False)
    add_opt("--no-save", help="Dont write the overridden settings to config file", action="store_true", default=False)
    add_opt("--password", help="Password for root on both nodes")
    args = parse_args(parser)
    return args


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
    def __init__(self, args=None, logger=LOGGER):
        """
        FIXME: There's a lot of ugly version checking for RHEL 6 vs RHEL 7.  This should be an abstract base class
        and depending on the version override the implementation

        :param args: Result from argument parser
        :param logger:
        """
        super(Config, self).__init__(logger=logger)
        self.args = get_args(args=args)
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
        self.nfs_server = self.config_gettr(self.share_storage_config_obj, 'nfs_export')['nfs_server']
        self.fstab_section = self.config_gettr(self.system_info_obj, "fstab")
        self.nfs_ver = self.fstab_section["fstype"]
        self.controller = self.nfs_server
        temp = set(self.nova_hosts_list)
        temp.remove(self.controller)
        self.compute2 = temp.pop()
        self.distro_type = None  # will get filled in by args_override()
        self.args_override()

    def configure_nfs(self):
        """
        This ensures
        :return:
        """
        if self.nfs_ver == "nfs":
            self.system_info_obj.set("fstab", "nfs_server", self.nfs_server + ":/var/lib/nova")
            self.system_info_obj.set("fstab", "fstype", self.nfs_ver)
            for x in ["nfs", "rpcbind", "libvirtd"]:
                self.system_info_obj.set("services", x, "on,restart")
            attr = 'defaults,nfsvers=3,context="system_u:object_r:nova_var_lib_t:s0"'
        else:
            self.system_info_obj.set("fstab", "nfs_server", self.nfs_server + ":/")
            self.system_info_obj.set("fstab", "fstype", self.nfs_ver)
            for x in ["nfs", "rpcbind", "libvirtd"]:
                self.system_info_obj.set("services", x, "enable,restart")
            attr = 'defaults,context="system_u:object_r:nova_var_lib_t:s0"'
        self.system_info_obj.set("fstab", "attribute", attr)

    def args_override(self):
        if self.args is None:
            return

        # Determine if we will override installing packstack
        if self.args.no_packstack:
            self.system_info_obj.set("install", "install", "n")

        if self.args.password is not None:
            self.ssh_pass = self.args.password

        # Edit any place in the config files where we need the value of the controller
        if self.args.controller is not None:
            self.controller = self.args.controller
            self.nova_hosts_list[0] = self.args.controller
            self.nfs_server = self.args.controller
            self.nova_hosts_value = ",".join(self.nova_hosts_list)
            self.system_info_obj.set("fstab", "nfs_server", self.nfs_server + ":/")
            self.share_storage_config_obj.set("nfs_export", "nfs_server", self.nfs_server)

        # Edit any place in the config files where we need the value of the 2nd compute node
        if self.args.compute2 is not None:
            self.compute2 = self.args.compute2
            self.nova_hosts_list[1] = self.args.compute2
            self.nova_hosts_value = ",".join(self.nova_hosts_list)

        # Set the values in the config object
        if self.args.compute2 is not None or self.args.controller is not None:
            self.system_info_obj.set("nova", "nova_compute_hosts", self.nova_hosts_value)

        # Set the nfs type appropriately for the distro
        self.distro_type = self.system_version(self.controller, self.ssh_uid, self.ssh_pass)
        self.nfs_ver = self.distro_type.nfs_ver
        self.configure_nfs()

        def gen_file(arg_file, config_obj):
            if arg_file is not None:
                with open(arg_file, "w") as gen_file:
                    config_obj.write(gen_file)

        # Save the files
        if not self.args.no_save:
            gen_file(self.args.gen_sys_info, self.system_info_obj)
            gen_file(self.args.gen_storage, self.share_storage_config_obj)

        # It may be useful to only generate the config files so we can inspect them before running, and replace
        # the built in config files
        if self.args.gen_only:
            if self.args.no_save:
                self.logger.error("Can't have both --gen-only and --no-save at the same time")
                sys.exit(1)
            self.logger.info("Done generating config files....quitting")
            sys.exit(0)

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

    def remote_setup(self, install=True):
        banner(self.logger, ["Checking to see if Packstack will be run remotely..."])
        to_install = self.config_gettr(self.system_info_obj, 'install')['install']
        if 'n' in to_install:
            return True

        answer = self.config_gettr(self.system_info_obj, 'packstack')['filename']
        answerfile = os.path.basename(answer)
        answerpath = os.path.dirname(answer)

        # FIXME: Figure out a way to tell if this command was successful
        self.rmt_exec(self.controller, "packstack --gen-answer-file={}".format(answer), username=self.ssh_uid,
                      password=self.ssh_pass)
        self.rmt_copy(self.controller, username=self.ssh_uid, password=self.ssh_pass, fname=answerfile,
                      remote_path=answerpath)

        if os.path.exists(answerfile) and os.stat(answerfile)[6] != 0:
            #check to see if the file exist and its not empty.
            self.logger.debug("Creating backup file for answerfile")
            try:
                self.adj_val('CONFIG_COMPUTE_HOSTS', self.nova_hosts_value, answerfile, answerfile + '.bak')
            except IOError:
                raise IOError("Couldn't rename {0}".format(answerfile))

            banner(self.logger, ["Running packstack installer, using {0} file".format(answerfile)])
            self.rmt_copy(self.controller, username=self.ssh_uid, password=self.ssh_pass, fname=answerfile,
                          remote_path=answerpath, send=True)
            if install:
                out, err = self.rmt_exec(self.controller, 'packstack --answer-file {0}'.format(answer),
                                         username=self.ssh_uid, password=self.ssh_pass,
                                         input=[self.ssh_pass + "\n", self.ssh_pass + "\n"])

            return True
        else:
            self.logger.error("Couldn't find packstack answer file: {0}".format(answer))
            exit()

    def firewall_setup(self):
        """Firewall setup will open necessary ports on all compute nodes to allow libvirtd, nfs_server to
        communicate with their clients.

        FIXME: this function should be idempotent

        :return: upon success zero is returned if not an exception is raised.
        """
        nfs_tcp = self.config_gettr(self.firewall_config_obj, 'nfs rules')['tcp_ports']
        nfs_udp = self.config_gettr(self.firewall_config_obj, 'nfs rules')['udp_ports']
        libvirtd_tcp = self.config_gettr(self.firewall_config_obj, 'libvirtd rules')['tcp_ports']

        # In iptables, find where the first REJECT rule is.  We need to insert at this line number. If the
        # REJECT rule doesn't exist, just start at the last line in the INPUT chain
        def get_line(host):
            out, err = self.rmt_exec(str(host), "iptables -L INPUT --line-numbers",
                                     username=self.ssh_uid, password=self.ssh_pass)
            out = out.readlines()

            patt = re.compile(r"(\d+)\s+(\w+)")
            for i, lineout in enumerate(out, -1):
                m = patt.search(lineout)
                if not m:
                    continue
                line, chain = m.groups()
                self.logger.info("line = {0}, chain = {1}, i={2}".format(line, chain, i))
                if chain == "REJECT":
                    # this line needs to be deleted.
                    out, err = self.rmt_exec(str(host), "iptables -D INPUT {0}".format(i), username=self.ssh_uid,
                                             password=self.ssh_pass)
                    line = i - 1
                    break
            else:
                line = i

            self.logger.info("Final line = {0}".format(line))
            return line

        host = self.nfs_server
        self.logger.info("=" * 20)
        self.logger.info("Setting up firewall rules on {0}".format(host))

        line = int(get_line(host))
        for proto, ports in [("tcp", nfs_tcp), ("udp", nfs_udp), ("tcp", libvirtd_tcp)]:
            for port in ports.split(','):
                cmd = "iptables -I INPUT {0} -m state --state NEW -m {1} -p {1}" \
                      " --dport {2:s} -j ACCEPT".format(line, proto, port)
                line += 1
                ret = self.rmt_exec(str(host), cmd, username=self.ssh_uid, password=self.ssh_pass)
                errlines = ret[1].readlines()
                self.logger.info("Issued: {0}".format(cmd))
                if len(errlines) == 0:
                    continue
                else:
                    raise EnvironmentError('The remote command failed {0}'.format(errlines))

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

        # Edit the libvirtd
        for name, value in _libvirtd_conf.items():
            self.adj_val(name, value, 'libvirtd.conf', 'libvirtd.conf.bak')

        for name, value in _libvirtd_sysconf.items():
            self.adj_val(name, value, 'libvirtd', 'libvirtd.bak')

        for host in self.nova_hosts_list:
            for _obj in [_libvirtd_conf, _libvirtd_sysconf]:
                self.rmt_copy(host, username=self.ssh_uid, password=self.ssh_pass,
                              send=True, fname=_obj['filename'], remote_path=_obj['filepath'])

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
                    self.adj_val(name, value, _conf['filename'], _conf['filename'] + '.bak', delim="=")

            return True

        _nova_conf = dict(self.nova_config_obj.items('nova_conf'))
        cmd = "mkdir -p {0}".format(_nova_conf['state_path'])

        if self.distro_type.family in ["RHEL", "Centos"] and self.distro_type.version >= 7:
            self.logger.info("Doing nova setup for {} {}".format(self.distro_type.family, self.distro_type.version))
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
        _nfs_export_obj = dict(self.share_storage_config_obj.items('nfs_export'))

        vals = dict(self.config_gettr(self.share_storage_config_obj, 'nfs_ports'))
        fname, fpath = map(vals.pop, ("filename", "filepath"))  # pop them so we dont iterate on them later

        banner(self.logger, ["Doing NFS server setup"])

        # Copy the originals to our local machine.  we will use this for editing
        self.rmt_copy(self.nfs_server, fname=fname, remote_path=fpath, username=self.ssh_uid, password=self.ssh_pass)
        shutil.copyfile(fname, fname + ".bak")

        # Edit the files based on the values from share_storage config file
        for k, v in vals.items():
            self.adj_val(k, v, fname, fname + ".bak", not_found="append", delim="=")

        # Send the modified files back to the original host
        self.rmt_copy(self.nfs_server, username=self.ssh_uid, password=self.ssh_pass, send=True, fname=fname,
                      remote_path=fpath)

        if self.distro_type.family in ["RHEL", "Centos"] and self.distro_type.version >= 7:
            _nfs_idmapd_obj = dict(self.share_storage_config_obj.items('nfs_idmapd'))
            _nfs_idmapd_domain = self.config_gettr(self.share_storage_config_obj, 'nfs_idmapd')['domain']
            self.rmt_copy(self.nfs_server, fname=_nfs_idmapd_obj['filename'], username=self.ssh_uid,
                          password=self.ssh_pass, remote_path=_nfs_idmapd_obj['filepath'])
            self.adj_val('Domain', _nfs_idmapd_domain, _nfs_idmapd_obj['filename'],
                         _nfs_idmapd_obj['filename'] + '.bak')
            self.rmt_copy(self.nfs_server, username=self.ssh_uid, password=self.ssh_pass,
                          send=True, fname=_nfs_idmapd_obj['filename'], remote_path=_nfs_idmapd_obj['filepath'])

        nfs_exports_info = [_nfs_export, _nfs_export_net + _nfs_export_attribute]
        export_fn = self.gen_file(_nfs_export_obj['filename'], nfs_exports_info)
        self.rmt_copy(self.nfs_server, username=self.ssh_uid, password=self.ssh_pass,
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

        system_util = 'echo '

        system_util_operator = ' >> '

        cmd = [system_util, fstab_entry, system_util_operator, _fstab_filename]
        rmt_cmd = " ".join(cmd)

        for host in self.nova_hosts_list:
            ret = self.rmt_exec(str(host), rmt_cmd, username=self.ssh_uid, password=self.ssh_pass)
            if ret[0].channel.recv_exit_status() == 0:
                continue
            else:
                raise EnvironmentError('The remote command failed {0}'.format(ret[1].readlines()))

        return True

    def finalize_services(self):
        """Looks at the [services] section of system_info, and performs any necessary operations"""
        banner(self.logger, ["Finalizing services"])

        keys = ["nfs", "rpcbind", "libvirtd", "setenforce"]
        vals = dict(self.system_info_obj.items('services'))
        _nfs, _rpcbind, _libvirt, _setenforce = map(lambda x: vals[x], keys)

        # do the command for nfs
        def set_service(host, cmd, service_name, val):
            srv_cmd = {"command": val, "name": service_name}
            cmd = cmd.format(**srv_cmd)
            self.logger.info("Issuing {0} on host {1}".format(cmd, host))
            return self.rmt_exec(str(host), cmd, username=self.ssh_uid, password=self.ssh_pass)

        # Ughh, this is ugly.  This should be made polymorphic
        for host in self.nova_hosts_list:
            # NFS server
            srv_name = "nfs-server" if self.distro_type.nfs_ver == "nfs4" else "nfs"
            if host == self.nfs_server:
                for i in _rpcbind.split(","):
                    cmd = self.distro_type.service_enable if i in ["on", "enable"] else self.distro_type.service_cmd
                    set_service(host, cmd, "rpcbind", i)
                for i in _nfs.split(","):
                    cmd = self.distro_type.service_enable if i in ["on", "enable"] else self.distro_type.service_cmd
                    set_service(host, cmd, srv_name, i)

            for i in _libvirt.split(","):
                cmd = self.distro_type.service_enable if i in ["on", "enable"] else self.distro_type.service_cmd
                set_service(host, cmd, "libvirtd", i)

            # FIXME: this is a temporary workaround
            self.rmt_exec(str(host), "setenforce {0}".format(_setenforce), username=self.ssh_uid,
                          password=self.ssh_pass)
            self.logger.info("Calling setenforce {0}".format(_setenforce))
            out, _ = self.rmt_exec(str(host), "getenforce", username=self.ssh_uid, password=self.ssh_pass)
            self.logger.info("getenforce: {0}".format("".join(out)))

        return True

    def configure_etc_hosts(self):
        """Sets the /etc/hosts file on both the controller and compute2 nodes

        It copies the /etc/hosts file locally, edits it, then copies the edited file back.  The function
        will also run the hostname command remotely in order to get the hostname from the nodes.  It
        compares this with the cdomain name from the nfs_idmapd section.  If there is a discrepancy or
        it can't retrieve the hostname, it will raise an error

        Returns a tuple of the short hostname and the full hostname
        """
        # Get the /etc/hosts file from the remote machine
        getattr = lambda x: self.system_info_obj.get("etc_hosts", x)
        fname, fpath = map(getattr, ["filename", "filepath"])

        # Get the domain from the share_storage config file
        domain = dict(self.config_gettr(self.share_storage_config_obj, "nfs_idmapd"))
        domain_name = domain["domain"]

        # Helper to retrieve the short and long names.
        def get_host_names(host, domain):
            out, _ = self.rmt_exec(host, "hostname", username=self.ssh_uid, password=self.ssh_pass)
            try:
                hostname = out.readlines()[0].strip()
            except Exception as e:
                self.logger.error("Unable to get the hostname from {0}".format(host))
                raise e

            ind = hostname.find(domain)
            if ind == -1:
                msg = "On host {0}, discrepancy between found domain name: {1}, " \
                      "and domain in config file: {2}".format(host, hostname, domain)
                self.logger.error(msg)
                raise Exception(msg)

            short = hostname[:ind]
            if any(map(short.endswith, [".", "-", "_"])):
                short = short[:-1]  # remove the .,- or _

            return short, hostname

        # Copy the originals to our local machine.  we will use this for editing
        compute1_entry = "{0} {1}".format(*get_host_names(self.controller, domain_name))
        compute2_entry = "{0} {1}".format(*get_host_names(self.compute2, domain_name))
        entries = [(self.controller, compute1_entry), (self.compute2, compute2_entry)]
        for host in self.nova_hosts_list:
            self.rmt_copy(host, fname=fname, remote_path=fpath, username=self.ssh_uid, password=self.ssh_pass)
            for h, v in entries:
                self.adj_val(h, v, fname, fname + ".bak", not_found="append", delim=" ")
            self.rmt_copy(host, username=self.ssh_uid, password=self.ssh_pass, send=True, fname=fname,
                          remote_path=fpath)
        return True
