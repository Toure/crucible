RHOS-Transmigration
===================
This utility is a post installation script for RHEL and Fedora deployment of OpenStack with LiveMigration.

USAGE: Edit configuration files located in configs package.
 
#> python run_me.py

Prerequisite: pip, paramiko, scpclient, openstack-packstack, epel repo.


RHEL7: http://download-i2.fedoraproject.org/pub/epel/7/x86_64/e/epel-release-7-2.noarch.rpm
RHEL6: http://download-i2.fedoraproject.org/pub/epel/6/i386/epel-release-6-8.noarch.rpm

Installation: All prereq can be installed via yum with the exception of scpclient which pip 
is needed to install.

TODO: Logging (DEBUG and INFO), System subscription.