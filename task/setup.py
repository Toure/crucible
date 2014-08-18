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
        self.config = ConfigParser.ConfigParser()
        self.firewall_config = self.config.read('../configs/firewall')
        self.libvirtd_config = self.config.read('../configs/libvirtd')
        self.nova_config = self.config.read('../configs/nova')
        self.share_storage_config = self.config.read('../configs/share_storage')
        self.system_info_config = self.config.read('../configs/system_info')

    def config_mapper(self, config_reader, section):
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
        answerfile_path = self.config_mapper(self.system_info_config, 'packstack')['path']
        run_setup.generateAnswerFile(answerfile_path)

        if os.path.isfile(answerfile_path):
            answerfile = self.config.read(answerfile_path)
            answerfile.

    def network_setup(self):
        pass

    def libvirtd_setup(self):
        pass

    def nova_setup(self):
        pass
