#!/usr/bin/env python

__author__ = 'Toure Dunnon'

from task.live_migrate import Config



config = Config()

LIVE_Migrate = [
    config.system_setup,
    config.firewall_setup,
    config.libvirtd_setup,
    config.nova_setup,
    config.nfs_server_setup,
    config.nfs_client_setup,
    config.finalize_services
]

#parser = argparse.ArgumentParser(description='Live Migration Setup Util.')
#parser.add_argument('-l', '--log-level', choices=LEVELS, dest='logging', required=True,
#help = "Logging level to use")

#args = parser.parse_args()
#level_name = args.logging
#level = LEVELS.get(level_name, logging.NOTSET)
#logging.basicConfig(level=level)

#if level_name:
for fn in LIVE_Migrate:
    ret = fn()
    if ret:
        continue
    else:
        raise Exception("Time to call it quits as {} didn't"
                        " complete its task.".format(fn))