from task.os_info import OSVer

__author__ = 'toure'

import os
import sys
import readline
import ConfigParser

try:
    from packstack.installer import run_setup
except ImportError:
    print('packstack isn\'t installed')


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

    def system_setup(self):
        """
        System setup will determine RHEL version and configure the correct services per release info.
        """
        #rhel_ver = {6: "upstart", 7: "systemd"}
        #rhel_env = rhel_ver[OSVer.system_version()]
        self.system_info_config = self.make_config('sys_info', '../configs/system_info')
        answerfile = self.config_gettr(self.system_info_config, 'packstack')['filename']
        run_setup.generateAnswerFile(answerfile)

        if os.path.exists(answerfile):
            nova_compute_hosts = self.config_gettr(self.system_info_config, 'nova')['NOVA_COMPUTE_HOSTS']
            answer_file = self.make_config_obj('packstack_ans', answerfile)
            try:
                answer_file.set('general', 'CONFIG_COMPUTE_HOSTS', nova_compute_hosts)
            except IOError as e:
                print e.message
            run_setup._main(configFile=answerfile)

        else:
            print("Couldn't find packstack answer file")
            exit()


    def network_setup(self):
        pass

    def libvirtd_setup(self):
        pass

    def nova_setup(self):
        pass
