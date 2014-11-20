# Crucible

This utility is a post installation script for RHEL and Fedora deployment of OpenStack with LiveMigration using
NFS for shared storage

# Rationale

There should be an automated way to set up all the necessary bits to do live migration because there is too much to
do manually, and differences between RHEL6 and RHEL7 can make setup trickier

# Prerequisites

* 2 VMs.  One will be the controller/compute1 the other will be compute2
* All the software repositories set up appropriately for your distro/rhos version
  - Currently has been tested on RHEL 6.6 Icehouse(RHOS) and RHEL 7 Juno(RDO) and Icehouse(RHOS)
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

### share_storage

This file defines the NFS options.  It may eventually support ceph/RBD shared storage, but that will come later.  This
is a standard python INI type file that can be read in, parsed and written to by the ConfigParser module.

    [nfs_exports]- This section describes key: value pairs for the /etc/exports file
    filename: the exports file
    filepath: path to the exports file (but not including the file itself)
    nfs_server: the ip address of your nfs sever node (usually your controller node)
    export: the path of the folder that NFS will export (typically /var/lib/nova)
    attribute: These are the various options that can be passed for the nfs mounting
    network: what host(s) can mount to this server (usually *)

    [nfs_idmapd]- This section descibes key: value pairs for the /etc/idmapd file
    filename: idmapd.conf
    filepath: /etc
    domain: In nfs4, we use idmapd for configuration.  We use lab.eng.rdu2.redhat.com, but choose your own that works for
            your network

    [nfs_ports]- Describes the ports that must be setup for /etc/sysconfig/nfs.  We edit this file with these ports
    filename: nfs
    filepath: /etc/sysconfig
    LOCKD_TCPPORT: 32803
    LOCKD_UDPPORT:32769
    MOUNTD_PORT: 892
    RQUOTAD_PORT: 875
    STATD_PORT: 662
    STATD_OUTGOING_PORT: 2020


### system_info

This configuration file is mostly used for packstack setup, but it also involves services that need to be enabled or
started, as well as a few other system-wide settings.  I will only cover sections that are pertinent.  Many of the
sections just modify the answer file so we can tell it which openstack services to install.  However, they should
normally be left as-is

    [packstack]
    # Where the packstack answer file will be.  IE The script runs packstack --gen-answer-file=/tmp/rhos_live_migration.txt
    filename: /tmp/rhos_live_migration.txt

    [install]
    # Whether to perform a packstack install or not.  You can set this to n if you do not wish to run packstack
    install: y

    [nova]
    nova_install: y
    #config_nova_compute_hosts key will take a comma separated list: 192.168.0.10, 172.16.1.10.  Note that the script
    # currently only supports 2 entries
    nova_compute_hosts:10.8.30.141,10.8.30.200

    [ssh_creds]
    #make sure all systems have the same credentials. user should be root normally, and change the password
    username: root
    password: none

    [selinux]- This section describes any selinux settings that we need to allow through
    setsebool: nfs_export_all_rw

    [fstab] - The script now detects which version of nfs your system has, and will overwrite these settings.
    # Change nfs_server appropriately
    # For NFS4
    # fstype: nfs4
    #
    # For NFS3
    # nfs_server: xxx.xxx.xxx.xxx:/var/lib/nova
    # fstype: nfs
    # attribute: defaults,nfsvers=3,context="system_u:object_r:nova_var_lib_t:s0"
    #
    filename: /etc/fstab
    nfs_server: 10.8.30.141:/
    nfs_client_mount: /openstack
    fstype: nfs4
    attribute: defaults,context="system_u:object_r:nova_var_lib_t:s0"
    fsck: 0 0

    [services]- These are services that we need to enable and restart for live migration to work
    nfs: enable,stop,start
    rpcbind: enable,stop,start
    libvirtd: enable,stop,start
    setenforce: This is a temporary workaround until the new selinux policy is enabled

    [etc_hosts]- We configure the system to add the two compute nodes.  Live migration only works with hostnames
    filename: hosts
    filepath: /etc

### firewall

When originally writing the script, iptables was a major bane.  The crucible project will now programmatically find
where it should start inserting new stateful rules on the INPUT chain.  It uses the tcp and udp ports listed in this
section to know what ports to open up.

    [nfs rules]
    tcp_ports: 111,662,875,892,2049,32803,32769
    udp_ports: 111,662,875,892,2049,32803,32769


    [libvirtd rules]
    tcp_ports: 16509


### libvirtd

A common mistake when trying to setup live migration is to forget to properly configure the /etc/libvirt/libvirtd.conf
and /etc/sysconfig/libvirtd files.  The former tells the libvirtd daemon that it needs to listen over tcp.  You could,
if you have a proper CA cert setup, set listen_tls: 1.  Crucible doesn't do this however.  It's also necessary to
set the auth_* properties correctly (and the quotes around "none" are necessary).  Similarly, for the libvirtd config,
the quotes around "--listen" are also required:

    [libvirtd_conf]
    filename: libvirtd.conf
    filepath: /etc/libvirt
    listen_tls: 0
    listen_tcp: 1
    auth_unix_ro: "none"
    auth_unix_rw: "none"
    auth_tcp: "none"
    auth_tls: "none"

    [libvirtd_sysconfig]
    filename: libvirtd
    filepath: /etc/sysconfig
    LIBVIRTD_ARGS: "--listen"

### nova

This configuration file contains the information necessary to setup the openstack nova services.  As we discovered,
there can be no spaces around the key=value pair (sort of like bash variable definitions).  The state_path key is
where nova (actually libvirt) will look for all the instance state information.

In RHEL 7 that has systemd, the nova_*_service sections are required, and in RHEL 6 they are ignored.  These sections
give information to systemd for service dependency information.  If this is not given, you will have problems when
starting or restarting openstack-nova-service:

    [nova_conf]
    filename: nova.conf
    filepath: /etc/nova
    state_path: /openstack
    live_migration_flag: VIR_MIGRATE_UNDEFINE_SOURCE, VIR_MIGRATE_PEER2PEER, VIR_MIGRATE_LIVE

    [nova_api_service]
    filename: openstack-nova-api.service
    filepath: /usr/lib/systemd/system
    After: syslog.target network.target nfs-mountd.service nfs-server.service openstack.mount

    [nova_cert_service]
    filename: openstack-nova-cert.service
    filepath: /usr/lib/systemd/system
    After: syslog.target network.target openstack.mount

    [nova_compute_service]
    filename: openstack-nova-compute.service
    filepath: /usr/lib/systemd/system
    After: syslog.target network.target openstack.mount

# Known limitations/workarounds/TODO

- FIXME: After the script runs, it is currently still necessary to reboot the system.  Despite all the services running,
  both the main controller node and the compute2 node need to be rebooted
- FIXME: A setenforce 0 is required for the time being until selinux is properly configured (there is a BZ for this)
  - Since the script does not edit the /etc/selinux/config file, you must remember to setenforce 0 after rebooting
- TODO: The script only uses 2 nodes.  If you wished to have more nodes than this, it does not do this
- TODO: It only currently works with NFS shared storage.  It does not yet support other shared storage systems like
  ceph/rbd,iscsi, etc
- TODO: The eventual plan is to convert the setup functions from live_migrate.py to be Ansible modules which will be
  useful for automated provisioning
- FIXME: Most of crucible is idempotent, with the exception of the firewall rules.  If you have to run the run_me.py
  script more than once, be careful about removing the iptables rules that were added.  These should be cleaned up
- TODO: is to be able to install packstack remotely
  - This may not be possible with paramiko, as programmatically copying the ssh public keys always gives a return of -1
  - This may be a limitation of paramiko.  I have a clojure implementation that works successfully however
- TODO: there is a clojure project that can automate the software repository setup for a node.  There is currently no
  REST API or web GUI front end in order for python to call into it
  - https://github.com/rarebreed/depender