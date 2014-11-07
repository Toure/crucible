#!/usr/bin/env python

__author__ = 'Toure Dunnon'

import platform
import shutil
from task.live_migrate import Config

# Because we have to be backwards compatible with python 2.6 (ugghhhhh), we'll import either
# argparse or optparse.  We have to limit our usage of the parser object to optparse functionality
# Note also that the command line options will override anything in the config files.  Therefore no
# arguments are necessary, as the config files will use the defaults
if 0:
    major, minor, micro = platform.python_version_tuple()
    if minor == '6':
        import optparse.OptionParser as Parser
        parser = Parser(description='Live Migration Setup Util.')
        add_opt = parser.add_option
        parse_args = lambda x: x.parse_args()[0]
    else:
        import argparse.ArgumentParser as Parser
        parser = Parser(description='Live Migration Setup Util.')
        add_opt = parser.add_argument
        parse_args = lambda x: x.parse_args()

    add_opt("--controller", help="IP address of the controller/compute 1 node")
    add_opt("--compute-two", help="IP address of the 2nd compute node")
    add_opt("--nfs-ver", help="The version of nfs to use (3 or 4)")
    args = parse_args(parser)


config = Config()


def edit_hosts(args, conf):
    fname = "../configs/"
    conf.rmt_copy(host, fname=fname, remote_path=fpath, username=self.ssh_uid, password=self.ssh_pass)
    shutil.copyfile(fname, fname + ".bak")
    # Edit the files based on the values from share_storage config file
    for k, v in vals.items():
        self.adj_val(k, v, fname, fname + ".bak", not_found="append")

    # Send the modified files back to the original hosts
    self.rmt_copy(host, username=self.ssh_uid, password=self.ssh_pass, send=True, fname=fname,
                  remote_path=fpath)

LIVE_Migrate = [
    config.system_setup,
    config.firewall_setup,
    config.libvirtd_setup,
    config.nova_setup,
    config.nfs_server_setup,
    config.nfs_client_setup,
    config.finalize_services
]


#parser.add_argument('-l', '--log-level', choices=LEVELS, dest='logging', required=True,
#help = "Logging level to use")

#args = parser.parse_args()
#level_name = args.logging
#level = LEVELS.get(level_name, logging.NOTSET)
#logging.basicConfig(level=level)

successes = []
for fn in LIVE_Migrate:
    ret = fn()
    successes.append(fn.__name__)
    if ret:
        continue
    else:
        raise Exception("Time to call it quits as {} didn't"
                        " complete its task.".format(fn.__name__))