# Crucible

This utility is a post installation script for RHEL and Fedora deployment of OpenStack with LiveMigration.

# Prerequisites

* 2 VMs.  One will be the controller/compute1 the other will be compute2
* All the software repositories set up appropriately for your distro/rhos version
  - Currently has been tested on RHEL 6.6 Icehouse(RHOS) and RHEL 7 Juno(RDO) and Icehouse(RHOS)
  - There is a work-in-progress software repo web service
* openstack-packstack must be installed on the controller node
* EPEL
  - RHEL7: http://download-i2.fedoraproject.org/pub/epel/7/x86_64/e/epel-release-7-2.noarch.rpm
  - RHEL6: http://download-i2.fedoraproject.org/pub/epel/6/i386/epel-release-6-8.noarch.rpm
* python-paramiko, python-pip and scpclient must be installed on the controller
  - paramiko and pip may already be installed.  scpclient can be installed with pip install scpclient


# Overview

Crucible serves 2 main purposes:

- To install packstack with the appropriate settings to do a live migration
- To set all the system configuration in order to perform live migration

The latter part is what the bulk of the project does.  In order to do live migration, the following must be configured
properly

- iptables must be configured appropriately
  - Must allow NFS, RPCBIND, and libvirtd packets
- NFS must be configured
  - /etc/sysconfig/nfs must be edited to allow the appropriate ports to be setup (or you may get a connection refused
    error message
  - the necessary services for nfs and rpcbind must be enabled and started
  - Differences between nfs version 3 and 4 must be accounted for
- The /etc/hosts file must be configured
  - The nova live-migration command does not allow IP addresses to be used, it must be the hostname
- The /etc/fstab must be configured to mount the NFS share
- The /etc/nova/nova.conf file must be edited to allow live-migration
- The /etc/libvirt/libvirtd.conf must be properly edited
- On RHEL 7, systemd openstack service files must be configured to bring up the services in the proper order

# Usage

First, you have to install Crucible to the controller node.  One can either git clone from the repository

     git clone https://github.com/Toure/crucible.git


Or if you have it locally, you can scp -r it to the controller node.

Crucible will read in config files from the config file directory in order to know how to setup the
system.  These settings can be overridden on the command line, and one can even generate a new system_info or
shared_storage file.  Most of the file does not need to be edited, and it might be easier for a newcomer to just
use the command line

## Command line

Once you are inside the folder, you will see a run_me.py script.  By running::

    python run_me.py --help

It will print out a help message.  In general, if this is your first time running Crucible, a good idea
will be to do this::

    python run_me.py --controller=xxx.xxx.xxx.xxx --compute2=yyy.yyy.yyy.yyy --gen-only --gen-sys-info=sysinfo --gen-storage=storage
    # Replace xxx.xxx.xxx.xxx with the ip address of your controller node, and yyy.yyy.yyy.yyy with compute2

By running this, you will not actually run anything.  It will instead generate the config files sysinfo and storage
in your current directory.  This allows you to inspect the files to make sure they are good before continuing.

Once you are satisfied, you can run the script like this::

    python run_me.py --controller=xxx.xxx.xxx.xxx --compute2=yyy.yyy.yyy.yyy --password=*********


Remember that command line args will always override the config files.

## Config files

For more advanced usage, you may want or need to hand edit the config files.

TODO: Explain all the various options
