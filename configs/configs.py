import os


def get_path(key):
    path = os.path.abspath(__file__)
    dir_path = os.path.dirname(path)
    return dir_path + '/' + key
