__author__ = 'toure'

from task.live_migrate import Config
import logging
import argparse

LEVELS = {
    'debug':logging.DEBUG,
    'info':logging.INFO,
    'warning':logging.WARNING,
    'error':logging.ERROR,
    'critical':logging.CRITICAL,
}

config = Config()

LIVE_Migrate = [
    config.system_setup, config.firewall_setup, config.libvirtd_setup,
    config.nova_setup, config.nfs_server_setup, config.nfs_client_setup
]

parser = argparse.ArgumentParser(description='Live Migration Setup Util.')
parser.add_argument('-l', '--log-level', choices=LEVELS, dest='logging', required=True,
                    help="Logging level to use ('debug', 'info', 'warning', 'error', 'critical')")

args = parser.parse_args()
level_name = args.logging
level = LEVELS.get(level_name, logging.NOTSET)
logging.basicConfig(level=level)
logger = logging.getLogger('RHOS_Transmigration')
formatter = logging.Formatter('[%(levelname)s]: %(date)s %(message)s')
handler = logging.StreamHandler()
handler.format(formatter)
logger.addHandler(handler)

if level_name:
    for fn in LIVE_Migrate:
        if fn():
            continue
        else:
            raise Exception("Time to call it quits as {} didn't"
                            " complete its task.".format(fn))
