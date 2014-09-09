__author__ = 'toure'

from task.live_migrate import Config
import logging
import sys

LEVELS = {
    'debug':logging.DEBUG,
    'info':logging.INFO,
    'warning':logging.WARNING,
    'error':logging.ERROR,
    'critical':logging.CRITICAL,
}

config = Config()

LIVE_Migrate = [
    config.system_setup(), config.firewall_setup(), config.libvirtd_setup(),
    config.nova_setup(), config.nfs_server_setup(), config.nfs_client_setup()
]

#TODO determine how to read cli for log level_name = sys.argv[1]
if len(sys.argv[1]) > 1:
    level_name = sys.argv[1]
    level = LEVELS.get(level_name, logging.NOTSET)
    logging.basicConfig(level=level)
    logger = logging.getLogger('RHOS_Transmigration')
    formatter = logging.Formatter('[%(levelname)s]: %(date)s %(message)s')
    handler = logging.StreamHandler()
    handler.format(formatter)
    logger.addHandler(handler)
