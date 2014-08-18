__author__ = 'toure'
import platform


class OSVer(object):

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
