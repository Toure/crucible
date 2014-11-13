import os


def get_path(key):
    """Get_Path helper function to return a relative path to the configurations file.

    :param key: configuration filename.
    :return: path to the configuration file
    :usage: e.i. get_path('firewall') ==> $basedir/configs/firewall
    """
    path = os.path.abspath(__file__)
    dir_path = os.path.dirname(path)
    return dir_path + '/' + key
