#!/usr/bin/env python
__author__ = 'Toure Dunnon'
__credits__ = ['Toure Dunnon', 'Sean Toner']
__license__ = 'GPL'
__version__ = '2.1.0'

from crucible.task.live_migrate import Config

# Because we have to be backwards compatible with python 2.6 (ugghhhhh), we'll import either
# argparse or optparse.  We have to limit our usage of the parser object to optparse functionality
# Note also that the command line options will override anything in the config files.  Therefore no
# arguments are necessary, as the config files will use the defaults
#
# TODO: RHOS-Transmigration should be able to work from any laptop.  Right now, you could run this on
# a machine other than the controller other than the controller or compute node, but the machine would
# have to be identical

config = Config()


LIVE_Migrate = [
    config.system_setup,
    config.firewall_setup,
    config.libvirtd_setup,
    config.nova_setup,
    config.nfs_server_setup,
    config.nfs_client_setup,
    config.configure_etc_hosts,
    config.finalize_services
]

successes = []
for fn in LIVE_Migrate:
    print "Running {0}".format(fn.__name__)
    ret = fn()
    successes.append(fn.__name__)
    if ret:
        continue
    else:
        raise Exception("Time to call it quits as {} didn't"
                        " complete its task.".format(fn.__name__))