%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%{!?pyver: %define pyver %(%{__python} -c "import sys ; print sys.version[:3]" || echo 0)}

%define _binaries_in_noarch_packages_terminate_build 0
%global debug_package %{nil}
Summary: Boot server configurator
Name: cobbler
License: GPLv2+
AutoReq: no
Version: 2.4.0
Release: beta1%{?dist}
Source0: http://shenson.fedorapeople.org/cobbler/cobbler-%{version}.tar.gz
Group: Applications/System
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
BuildArch: noarch
Url: http://cobbler.github.com/

BuildRequires: redhat-rpm-config
BuildRequires: git
BuildRequires: PyYAML
BuildRequires: python-cheetah

Requires: python >= 2.3
Requires: httpd
Requires: tftp-server
Requires: mod_wsgi
Requires: createrepo
Requires: python-augeas
Requires: python-cheetah
Requires: python-netaddr
Requires: python-simplejson
Requires: python-urlgrabber
Requires: PyYAML
Requires: rsync

%if 0%{?fedora} >= 11 || 0%{?rhel} >= 6
Requires: python(abi) >= %{pyver}
Requires: genisoimage
%else
Requires: mkisofs
%endif
%if 0%{?fedora} >= 8
BuildRequires: python-setuptools-devel
%else
BuildRequires: python-setuptools
%endif
%if 0%{?fedora} >= 6 || 0%{?rhel} >= 5
Requires: yum-utils
%endif
%if 0%{?fedora} >= 16
BuildRequires: systemd-units
Requires(post): systemd-sysv
Requires(post): systemd-units
Requires(preun): systemd-units
Requires(postun): systemd-units
%else
Requires(post):  /sbin/chkconfig
Requires(preun): /sbin/chkconfig
Requires(preun): /sbin/service
%endif

%description

Cobbler is a network install server.  Cobbler supports PXE,
virtualized installs, and re-installing existing Linux machines.  The
last two modes use a helper tool, 'koan', that integrates with
cobbler.  There is also a web interface 'cobbler-web'.  Cobbler's
advanced features include importing distributions from DVDs and rsync
mirrors, kickstart templating, integrated yum mirroring, and built-in
DHCP/DNS Management.  Cobbler has a XMLRPC API for integration with
other applications.

%prep
%setup -q

%build
%{__python} setup.py build

%install
test "x$RPM_BUILD_ROOT" != "x" && rm -rf $RPM_BUILD_ROOT
%{__python} setup.py install --optimize=1 --root=$RPM_BUILD_ROOT $PREFIX
mkdir -p $RPM_BUILD_ROOT/etc/httpd/conf.d
mv config/cobbler.conf $RPM_BUILD_ROOT/etc/httpd/conf.d/
mv config/cobbler_web.conf $RPM_BUILD_ROOT/etc/httpd/conf.d/

mkdir -p $RPM_BUILD_ROOT/var/spool/koan

%if 0%{?fedora} >= 9 || 0%{?rhel} > 5
mkdir -p $RPM_BUILD_ROOT/var/lib/tftpboot/images
%else
mkdir -p $RPM_BUILD_ROOT/tftpboot/images
%endif

rm -f $RPM_BUILD_ROOT/etc/cobbler/cobblerd

%if 0%{?fedora} >= 16
rm -rf $RPM_BUILD_ROOT/etc/init.d
mkdir -p $RPM_BUILD_ROOT%{_unitdir}
install -m0644 config/cobblerd.service $RPM_BUILD_ROOT%{_unitdir}

%post
if [ $1 -eq 1 ] ; then 
    # Initial installation 
    /bin/systemctl daemon-reload >/dev/null 2>&1 || :
elif [ "$1" -ge "2" ]; then
    # backup config
    if [ -e /var/lib/cobbler/distros ]; then
        cp /var/lib/cobbler/distros*  /var/lib/cobbler/backup 2>/dev/null
        cp /var/lib/cobbler/profiles* /var/lib/cobbler/backup 2>/dev/null
        cp /var/lib/cobbler/systems*  /var/lib/cobbler/backup 2>/dev/null
        cp /var/lib/cobbler/repos*    /var/lib/cobbler/backup 2>/dev/null
        cp /var/lib/cobbler/networks* /var/lib/cobbler/backup 2>/dev/null
    fi
    if [ -e /var/lib/cobbler/config ]; then
        cp -a /var/lib/cobbler/config    /var/lib/cobbler/backup 2>/dev/null
    fi
    # upgrade older installs
    # move power and pxe-templates from /etc/cobbler, backup new templates to *.rpmnew
    for n in power pxe; do
      rm -f /etc/cobbler/$n*.rpmnew
      find /etc/cobbler -maxdepth 1 -name "$n*" -type f | while read f; do
        newf=/etc/cobbler/$n/`basename $f`
        [ -e $newf ] &&  mv $newf $newf.rpmnew
        mv $f $newf
      done
    done
    # upgrade older installs
    # copy kickstarts from /etc/cobbler to /var/lib/cobbler/kickstarts
    rm -f /etc/cobbler/*.ks.rpmnew
    find /etc/cobbler -maxdepth 1 -name "*.ks" -type f | while read f; do
      newf=/var/lib/cobbler/kickstarts/`basename $f`
      [ -e $newf ] &&  mv $newf $newf.rpmnew
      cp $f $newf
    done
    /bin/systemctl try-restart cobblerd.service >/dev/null 2>&1 || :
fi

%preun
if [ $1 -eq 0 ] ; then
    # Package removal, not upgrade
    /bin/systemctl --no-reload disable cobblerd.service > /dev/null 2>&1 || :
    /bin/systemctl stop cobblerd.service > /dev/null 2>&1 || :
fi

%postun
/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
    # Package upgrade, not uninstall
    /bin/systemctl try-restart cobblerd.service >/dev/null 2>&1 || :
fi

%triggerun -- cobbler < 2.0.11-3
# Save the current service runlevel info
# User must manually run systemd-sysv-convert --apply cobblerd
# to migrate them to systemd targets
/usr/bin/systemd-sysv-convert --save cobblerd >/dev/null 2>&1 ||:

# Run these because the SysV package being removed won't do them
/sbin/chkconfig --del cobblerd >/dev/null 2>&1 || :
/bin/systemctl try-restart cobblerd.service >/dev/null 2>&1 || :

%else

%post
if [ "$1" = "1" ];
then
    # This happens upon initial install. Upgrades will follow the next else
    /sbin/chkconfig --add cobblerd
elif [ "$1" -ge "2" ];
then
    # backup config
    if [ -e /var/lib/cobbler/distros ]; then
        cp /var/lib/cobbler/distros*  /var/lib/cobbler/backup 2>/dev/null
        cp /var/lib/cobbler/profiles* /var/lib/cobbler/backup 2>/dev/null
        cp /var/lib/cobbler/systems*  /var/lib/cobbler/backup 2>/dev/null
        cp /var/lib/cobbler/repos*    /var/lib/cobbler/backup 2>/dev/null
        cp /var/lib/cobbler/networks* /var/lib/cobbler/backup 2>/dev/null
    fi
    if [ -e /var/lib/cobbler/config ]; then
        cp -a /var/lib/cobbler/config    /var/lib/cobbler/backup 2>/dev/null
    fi
    # upgrade older installs
    # move power and pxe-templates from /etc/cobbler, backup new templates to *.rpmnew
    for n in power pxe; do
      rm -f /etc/cobbler/$n*.rpmnew
      find /etc/cobbler -maxdepth 1 -name "$n*" -type f | while read f; do
        newf=/etc/cobbler/$n/`basename $f`
        [ -e $newf ] &&  mv $newf $newf.rpmnew
        mv $f $newf
      done
    done
    # upgrade older installs
    # copy kickstarts from /etc/cobbler to /var/lib/cobbler/kickstarts
    rm -f /etc/cobbler/*.ks.rpmnew
    find /etc/cobbler -maxdepth 1 -name "*.ks" -type f | while read f; do
      newf=/var/lib/cobbler/kickstarts/`basename $f`
      [ -e $newf ] &&  mv $newf $newf.rpmnew
      cp $f $newf
    done
    # reserialize and restart
    # FIXIT: ?????
    #/usr/bin/cobbler reserialize
    /sbin/service cobblerd condrestart
fi

%preun
if [ $1 = 0 ]; then
    /sbin/service cobblerd stop >/dev/null 2>&1 || :
    chkconfig --del cobblerd || :
fi

%postun
if [ "$1" -ge "1" ]; then
    /sbin/service cobblerd condrestart >/dev/null 2>&1 || :
    /sbin/service httpd condrestart >/dev/null 2>&1 || :
fi

%endif

%clean
test "x$RPM_BUILD_ROOT" != "x" && rm -rf $RPM_BUILD_ROOT

%files

%defattr(-,root,root,-)

%{_bindir}/cobbler
%{_bindir}/cobbler-ext-nodes
%{_bindir}/cobblerd
%{_sbindir}/tftpd.py*

%config(noreplace) %{_sysconfdir}/cobbler
%if 0%{?fedora} >= 16
%{_unitdir}/cobblerd.service
%else
/etc/init.d/cobblerd
%endif

%{python_sitelib}/cobbler

%config(noreplace) /var/lib/cobbler
%exclude /var/lib/cobbler/webui_sessions

/var/log/cobbler
/var/www/cobbler

%{_mandir}/man1/cobbler.1.gz

%config(noreplace) /etc/httpd/conf.d/cobbler.conf

%if 0%{?fedora} >= 9 || 0%{?rhel} >= 5
%exclude %{python_sitelib}/cobbler/sub_process.py*
%endif
%if 0%{?fedora} >= 9 || 0%{?rhel} > 5
%{python_sitelib}/cobbler*.egg-info
/var/lib/tftpboot/images
%else
/tftpboot/images
%endif

/usr/share/augeas/lenses/cobblersettings.aug

%doc AUTHORS CHANGELOG README COPYING

%package -n koan

Summary: Helper tool that performs cobbler orders on remote machines
Group: Applications/System
Requires: python >= 2.0
%if 0%{?fedora} >= 11 || 0%{?rhel} >= 6
Requires: python(abi) >= %{pyver}
Requires: python-simplejson
Requires: python-virtinst
%endif


%description -n koan

Koan stands for kickstart-over-a-network and allows for both
network installation of new virtualized guests and reinstallation
of an existing system.  For use with a boot-server configured with Cobbler

%files -n koan
%defattr(-,root,root,-)
%dir /var/spool/koan
%dir /var/lib/koan/config
%{_bindir}/koan
%{_bindir}/ovz-install
%{_bindir}/cobbler-register
%{python_sitelib}/koan

%if 0%{?fedora} >= 9 || 0%{?rhel} >= 5
%exclude %{python_sitelib}/koan/sub_process.py*
%exclude %{python_sitelib}/koan/opt_parse.py*
%exclude %{python_sitelib}/koan/text_wrap.py*
%endif

%{_mandir}/man1/koan.1.gz
%{_mandir}/man1/cobbler-register.1.gz
%dir /var/log/koan
%doc AUTHORS COPYING CHANGELOG README


%package -n cobbler-web

Summary: Web interface for Cobbler
Group: Applications/System
Requires: cobbler
Requires: Django >= 1.1.2
Requires: mod_wsgi
Requires: mod_ssl
%if 0%{?fedora} >= 11 || 0%{?rhel} >= 6
Requires: python(abi) >= %{pyver}
%endif

%description -n cobbler-web

Web interface for Cobbler that allows visiting
http://server/cobbler_web to configure the install server.

%post -n cobbler-web
# Change the SECRET_KEY option in the Django settings.py file
# required for security reasons, should be unique on all systems
RAND_SECRET=$(openssl rand -base64 40 | sed 's/\//\\\//g')
sed -i -e "s/SECRET_KEY = ''/SECRET_KEY = \'$RAND_SECRET\'/" /usr/share/cobbler/web/settings.py

%files -n cobbler-web
%defattr(-,root,root,-)
%doc AUTHORS COPYING CHANGELOG README
%config(noreplace) /etc/httpd/conf.d/cobbler_web.conf
%defattr(-,apache,apache,-)
/usr/share/cobbler/web
%dir %attr(700,apache,root) /var/lib/cobbler/webui_sessions
/var/www/cobbler_webui_content/

%changelog
* Thu Oct 11 2012 James Cammarata <jimi@sngx.net> 2.4.0-beta1
- Beta Release 1 of 2.4.0
- BUGFIX - Issue #329 - Systems no longer allow an add with an image for a
  parent (jimi@sngx.net)
- BUGFIX - Issue #327 - revert 5afcff7 and fix in a more sane way
  (jimi@sngx.net)
- Removed some duplicates created by reapplying a patch (jimi@sngx.net)
- BUGFIX - Issue #267 - old python-virtinst does not support --boot
  (jimi@sngx.net)
- Revise install_post_puppet.py to use newer puppet syntax
  (stephen@esstec.co.uk)
- Get rid of deprecated Puppet syntax so that cobbler works with Puppet 3.0
  (stephen@esstec.co.uk)
- Added ubuntu to dist check for named.conf location
  (daniel.givens@rackspace.com)
- Expanded automatic determination of tftpboot path, isc dhcp and bind service
  names and config files based on distro. (daniel@givenstx.com)
- Make the service name for DHCP and DNS restarts configurable for better
  portable between distros. (daniel.givens@rackspace.com)
- Serial based on formatted date and revision number (alevy@mobitv.com)
- Correct undefined variable name (jbd@jbdenis.net)
- fix merge Issue #252 BUGFIX and #262 (daikame@gmail.com)
- Add check for valid driver_type before executing qemu-img (jimi@sngx.net)
- fix mistake remove import. (daikame@gmail.com)
- move exec method to utils.py, and catch unexpected exception.
  (daikame@gmail.com)
- not check driver type on create method. (daikame@gmail.com)
- BUGFIX - Issue #305 - Incorrect Kickstart file when gPXE enabled
  (jimi@sngx.net)
- BUGFIX - Issue #304 - Cobbler does not store values correctly for ksmeta
  Objects were getting flattened improperly, so it was losing escapes/quoting
  for values with spaces (jimi@sngx.net)
- add vmdk and raw file create support. (daikame@gmail.com)
- BUGFIX - Issue #267 - old python-virtinst does not support --boot
  (jimi@sngx.net)
- Modified spec version/release to be 2.4.0-beta-1 (jimi@sngx.net)
- Initial commit for mysql backend support (jimi@sngx.net)
- BUGFIX - Issue #277 - move webroot to /srv/www for debian/ubuntu
  (jimi@sngx.net)
- FEATURE - adding 'zonetype' variable for DNS zone rendering (jimi@sngx.net)
- BUGFIX - Issue #278 - cobbler import fails for ubuntu images due to rsync
  args (jimi@sngx.net)
- BUGFIX - Issue #285 - update cobbler man page for incorrect options
  (jimi@sngx.net)
- BUGFIX - Issue #241 - adding distro with blank name via XMLRPC should not
  work (jimi@sngx.net)
- BUGFIX - Issue #272 - allow anamon to log entries when building systems based
  on profiles (no corresponding system record) (jimi@sngx.net)
- BUGFIX - Issue #252 - fuzzy match on lvs name returns a false match
  preventing LV creation (jimi@sngx.net)
- BUGFIX - Issue #287 - patch to allow templar to work without a config, which
  was breaking the tftpd.py script (jimi@sngx.net)
- add qcow2 driver type (daikame@gmail.com)
- fix koan qemu-machine-type param test. (daikame@gmail.com)
- Only cosmetic cleanup - removed commands that were commented out, added
  spaces for more clear code (flaks@bnl.gov)
- Modified sample.seed to make use kickstart_start and kickstart_done snippets
  for debian. As a result the following cobbler features work for debian:   -
  prevent net boot looping   - cobbler status reflects debian installations   -
  preseed file is downloaded a nd saved on the installed system as
  /var/log/cobbler.seed Also made download_config_files_deb snippet, make use
  of late_command New post_run_deb snippet allows to execute post installation
  script. (flaks@bnl.gov)
- Some changes for testing (jimi@sngx.net)
- Minor fix for urlparse on older pythons (>2.5) (jimi@sngx.net)
- FEATURE - Issue #253 - Use PEERDNS=no for DHCP interfaces when name servers
  are specified (jimi@sngx.net)
- install-tree for debian/ubuntu modified to take tree= from meta data. http,
  ftp and nfs remote tree locations supported (flaks@bnl.gov)
- add support of custom logical volume name (daikame@gmail.com)
- Partial revert of 87acfc8b, and a minor change to bring the koan extra-args
  inline with the PXE args (jimi@sngx.net)
- New default preseed, and a few minor changes to make ubuntu auto install work
  better (jimi@sngx.net)
- Add support for qemu machine type to emulate (option --qemu-machine-type).
  (isaoshimizu@gmail.com)
- Modern x86 kernels have 2048 char limit and this is needed to support
  configurations with kickstart+NIC kernel params. Otherwise koan refuses to
  accept the param list. (oliver@cpan.org)
- Allow koan's -S option to work for SuSE breed. Also remove -S for breed=None,
  as I assume "Red Hat" is not a sane assumption for all Distros without a
  breed. (oliver@cpan.org)
- Only add a udev net rule for an interface if the MAC is set. This fixes
  behaviour whereby a dummy udev rule at eth0 forces the first NIC to get eth1
  post-install. (oliver@cpan.org)
- Make the domainname setting be the full eth0 DNS Name, minus the first dotted
  part (and not the FQDN). (oliver@cpan.org)
- BUGFIX - Issue #252 - fuzzy match on lvs name returns a false match
  preventing LV creation (jimi@sngx.net)
- Added back in the filesystem loader. (oliver@cpan.org)
- BUGFIX - Issue #247 - Reposync does not work from the web interface
  (jimi@sngx.net)
- BUGFIX - Issue #246 - CentOS 5.x install fence_tools to /sbin/
  (jimi@sngx.net)
- Fix post_report trigger typo (jimi@sngx.net)
- Some fixes for koan running with an old virt-install (jimi@sngx.net)
- Define pxe_menu_items variable when creating PXE files for systems
  (jthiltges2@unl.edu)
- Refactor PXE and GRUB menu item creation into a separate function
  (jthiltges2@unl.edu)
- django 1.4 and later have deprecated the old TEMPLATE_LOADERS and replaced
  them with a new app_directories.Loader (oliver@cpan.org)
- Add support for UEFI boot to the subnet, but not for defined systems yet.
  (erinn.looneytriggs@gmail.com)
- Fix redhat import whitelist for Fedora 17 (jimi@sngx.net)
- Fix unittest on the case of haven't virt-install libs. (daikame@gmail.com)
- os_version for debian should be similar to ubunty for virt-install to work
  changed tree in app.py so that I can use debian mirror different from cobbler
  server (flaks@bnl.gov)
- fedora 17 changed the output of ifconfig command. This will make IFNAME set
  in snippets again (flaks@bnl.gov)
- remove edit for now (flaks@bnl.gov)
- Fixed snippets for bonded_bridge_slave and a few other fixes for koan/web GUI
  (jimi@sngx.net)
- Initial support for bonded_bridge_slave type. TODO: modifying snippets to
  actually make it work... (jimi@sngx.net)
- The webui_sessions directory belongs only to cobbler-web
  (chutzimir@gmail.com)
- RPM: put cobbler*.conf files only in /etc/httpd/conf.d
  (cristian.ciupitu@yahoo.com)
- better fix for pull request #228 (jorgen.maas@gmail.com)
- make rpms failed because the misc/ directory containing the augeas lense
  could not be found. this simple diff fixes that. (jorgen.maas@gmail.com)
- Ubuntu actually requires auto=true in kopts See
  http://serverfault.com/a/144290/39018 (ekirpichov@gmail.com)
- Whitespace cleanup for the new openvz stuff (jimi@sngx.net)
- Remove dead code (useless imports) (cristian.ciupitu@yahoo.com)
- BUGFIX extra-args option problems (daikame@gmail.com)
- FIX koan virt-install tests. (daikame@gmail.com)
- added debian support to prevent net boot looping (flaks@bnl.gov)
- README.openvz: - added (nvrhood@gmail.com)
- scripts/ovz-install: - added support for "services" kickstart option -
  corrected repos and installation source processing (nvrhood@gmail.com)
- cobbler.spec, setup.py: - added scripts/ovz-install (nvrhood@gmail.com)
- koan/openvzcreate.py, scripts/ovz-install: - changes in copyright notice
  (nvrhood@gmail.com)
- koan/app.py: - bug in koan: size of freespace on VG expressed as float with
  comma, but need fload with point (nvrhood@gmail.com)
- koan/app.py: - added type "openvz" (nvrhood@gmail.com)
- cobbler/collection.py: - openvz containers doesn't need to boot from PXE, so
  we prevent PXE-menu creation for such profiles. (nvrhood@gmail.com)
- cobbler/item_profile.py, cobbler/utils.py: - added "openvz" virtualization
  type (nvrhood@gmail.com)
- cobbler/item_system.py: - added openvz for virt_type (nvrhood@gmail.com)
- [BUGFIX] template errors can hit an exception path that references an
  undefined variable (jimi@sngx.net)
- If the call to int() fails, inum has no value, thus the reference to inum in
  the except clause causes an UnboundLocalError when it tries to reference
  inum. (joshua@azariah.com)
- Add new ubuntu (alpha) version to codes.py (jorgen.maas@gmail.com)
- Not all remove current ifcfg- post_install_network_config (me@n0ts.org)
- Update systemctl script to resolve some issues (jimi@sngx.net)
- More spec fixes (jimi@sngx.net)
- Removing replicate_use_default_rsync_options setting and setting
  replicate_rsync_options to existing rsync default.  Issue #58
  (john@julienfamily.com)
- Commit for RFE: Expose rsync options during replication.  Issue #58
  (john@julienfamily.com)
- Yet more HTML/CSS fixes, cleaning up some overly large inputs caused by other
  CSS changes (jimi@sngx.net)
- More HTML/CSS improvements for new weblayout (jimi@sngx.net)
- CSS improvements for the tabbed layout (jimi@sngx.net)
- Fix for settings edit using the new tab format (jimi@sngx.net)
- Added a cancel button to replace the reset button (jimi@sngx.net)
- Fix saving of multiselect fields (jimi@sngx.net)
- Modification to generic_edit template to use tabs for categories plus some
  miscellaneous cleanup (jimi@sngx.net)
- Adding an example line for redhat imports to the whitelist file
  (jimi@sngx.net)
- Another minor fix for suse imports - fixing up name when using --available-as
  (already done in other import modules) - allowing multiple arch imports (also
  already done in other imports) (jimi@sngx.net)
- Some fixups for suse using --available-as (jimi@sngx.net)
- Fix for import when using --available-as - currently rsyncs full remote tree,
  changing that to only import files in a white list - some modifications to
  import modules to clean some things up and make available-as work better -
  fix in utils.py for path_tail, which was not working right and appending the
  full path (jimi@sngx.net)
- Run the same sed command on the default distributed config file to ensure
  consistent indentation (jimi@sngx.net)
- Add setting to enable/disable dynamic settings changes Adding
  cobblersettings.aug to distributed files, since we need a copy that doesn't
  insert tabs Added a "cobbler check" that checks if dynamic settings is
  enabled and prints a sed command to cleanup the settings file spacing/indents
  (jimi@sngx.net)
- Change cli command "settings" to "setting" to match other commands (which are
  not plurarlized) (jimi@sngx.net)
- Removing commented-out try/except block in config.py, didn't mean to commit
  this (jimi@sngx.net)
- Fixed/improved CLI reporting for settings (jimi@sngx.net)
- Added support for validating setting type when saving Also fixed up the
  augeas stuff to save lists and hashes correctly (jimi@sngx.net)
- Fix for incorrect redirect when login times out when looking at a setting
  edit (jimi@sngx.net)
- Dynamic settings edit support for the web GUI (jimi@sngx.net)
- Added ability to write settings file via augeas (jimi@sngx.net)
- Initial support for modifying settings live Changed settings do not survive a
  reboot and revert to what's in /etc/cobbler/settings TODO:  * report --name
  show a single setting  * validate settings based on type (string, list, bool,
  etc.)  * web support for editing  * persisting settings after change
  (jimi@sngx.net)
- Branch for 2.4.0, updated spec and setup.py (jimi@sngx.net)

* Sun Jun 17 2012 James Cammarata <jimi@sngx.net> 2.2.3-2
- [BUGFIX] re-enable writing of DHCP entries for non-pxeboot-enabled systems
  unless they're static (jimi@sngx.net)
* Tue Jun 05 2012 James Cammarata <jimi@sngx.net> 2.2.3-1
- [BUGFIX] add dns to kernel commandline when using static interface
  (frido@enu.zolder.org)
- [BUGFIX] issue #196 - repo environment variables bleed into other repos
  during sync process This patch has reposync cleanup/restore any environment
  variables that were changed during the process (jimi@sngx.net)
- BUGFIX quick dirty fix to work around an issue where cobbler would not log in ldap
  usernames which contain uppercase characters. at line 60 instead of "if user
  in data", "if user.lower() in data" is used. It would appear the parser puts
  the usernames in data[] in lowercase, and the comparison fails because "user"
  does hold capitalizations. (matthiasvandegaer@hotmail.com)
- [BUGFIX] simplify SELinux check reporting 
  * Remove calls to semanage, policy prevents apps from running that directly 
    (and speeds up check immensely) 
  * Point users at a wiki page which will contain details on ensuring cobbler
    works with SELinux properly (jimi@sngx.net)
- [BUGFIX] issue #117 - incorrect permissions on files in /var/lib/cobbler
  (j-nomura@ce.jp.nec.com)
- [BUGFIX] issue #183 - update objects mgmt classes field when a mgmt class is
  renamed (jimi@sngx.net)
- [BUGFIX] adding some untracked directories and the new augeas lense to the
  setup.py and cobbler.spec files (jimi@sngx.net)
- [FEATURE] Added ability to disable grubby --copy-default behavior for distros that may
  have problems with it (jimi@sngx.net)
- [SECURITY] Major changes to power commands: 
  * Fence options are now based on /usr/sbin/fence_* - so basically anything the 
    fence agents package provides.
  * Templates will now be sourced from /etc/cobbler/power/fence_<powertype>.template.  
    These templates are optional, and are only required if you want to do extra 
    options for a given command. - All options for the fence agent command are sent 
    over STDIN. 
  * Support for ipmitool is gone, use fence_ipmilan instead (which uses ipmitool 
    under the hood anyway). This may apply to other power types if they were provided 
    by a fence_ command. 
  * Modified labels for the power options to be more descriptive. (jimi@sngx.net)
- [BUGFIX] issue #136 - don't allow invalid characters in names when copying
  objects (jimi@sngx.net)
- [BUGFIX] issue #168 - change input_string_or_list to use shlex for split This
  function was using a regular string split, which did not allow quoted or
  escaped strings to be preserved. (jimi@sngx.net)
- [BUGFIX] Correct method to process the template file. This Fixes the previous issue
  and process the template. (charlesrg@gmail.com)
- [BUGFIX] issue #170 - koan now checks length of drivers list before indexing
  (daniel@defreez.com)
- [BUGFIX] Issue #153 - distro delete doesn't remove link from
  /var/www/cobbler/links Link was being created incorrectly during the import
  (jimi@sngx.net)
- [FEATURE] snippets: save/restore boot-device on ppc64 on fedora17 (nacc@us.ibm.com)
- [BUGFIX] Fixed typo in pre_anamon (brandor5@gmail.com)
- [BUGFIX] Added use of $http_port to server URL in pre_anamon and post_anamon
  (brandor5@gmail.com)
- [BUGFIX] Fixed dnsmasq issue regarding missing dhcp-host entries (cobbler@basjes.nl)
- [BUGFIX] in buildiso for RedHat based systems. The interface->ip resolution was
  broken when ksdevice=bootif (default) (jorgen.maas@gmail.com)
- [BUGFIX] rename failed for distros that did not live under ks_mirror
  (jimi@sngx.net)
- [BUGFIX] Partial revert of commit 3c81dd3081 - incorrectly removed the 'extends'
  template directive, breaking rendering in django (jimi@sngx.net)
- [BUGFIX] Reverting commit 1d6c53a97, which was breaking spacewalk Changed the web
  interface stuff to use the existing extended_version() remote call
  (jimi@sngx.net)
- [BUGFIX] Minor fix for serializer_pretty_json change, setting indent to 0 was still
  causing more formatted JSON to be output (jimi@sngx.net)
- [SECURITY] Adding PrivateTmp=yes to the cobblerd.service file for systemd
  (jimi@sngx.net)
- [FEATURE] add a config option to enable pretty JSON output (disabled by default)
  (aronparsons@gmail.com)
- [BUGFIX] issue #107 - creating xendomains link for autoboot fails Changing an
  exception to a printed warning, there's no need to completely bomb out on the
  process for this (jimi@sngx.net)
- [BUGFIX] issue #28 - Cobbler drops errors on the floor during a replicate
  Added additional logging to add_ functions to report an error if the add_item
  call returns False (jimi@sngx.net)
- [BUGFIX] add requirement for python-simplejson to koan's package
  (jimi@sngx.net)
- [BUGFIX] action_sync: fix sync_dhcp remote calls (nacc@us.ibm.com)
- [BUGFIX] Add support for KVM paravirt (justin@thespies.org)
- [BUGFIX] Makefile updates for debian/ubuntu systems (jimi@sngx.net)
- [BUGFIX] fix infinite netboot cycle with ppc64 systems (nacc@us.ibm.com)
- [BUGFIX] Don't allow Templar classes to be created without a valid config
  There are a LOT of places in the templar.py code that use self.settings
  without checking to make sure a valid config was passed in. This could cause
  random stack dumps when templating, so it's better to force a config to be
  passed in. Thankfully, there were only two pieces of code that actually did
  this, one of which was the tftpd management module which was fixed elsewhere.
  (jimi@sngx.net)
- [BUGFIX] instance of Templar() was being created without a config passed in
  This caused a stack dump when the manage_in_tftpd module tried to access the
  config settings (jimi@sngx.net)
- [BUGFIX] Fix for issue #17 - Make cobbler import be more squeaky when it doesn't
  import anything (jimi@sngx.net)
- [FEATURE] autoyast_sample: save and restore boot device order (nacc@us.ibm.com)
- [BUGFIX] Fix for issue #105 - buildiso fails Added a new option for buildiso:
  --mkisofs-opts, which allows specifying extra options to mkisofs TODO: add
  input box to web interface for this option (jimi@sngx.net)
- [BUGFIX] incorrect lower-casing of kickstart paths - regression from issue
  #43 (jimi@sngx.net)
- [FEATURE] Automatically detect and support bind chroot (orion@cora.nwra.com)
- [FEATURE] Add yumopts to kickstart repos (orion@cora.nwra.com)
- [BUGFIX] Fix issue with cobbler system reboot (nacc@us.ibm.com)
- [BUGFIX] fix stack trace in write_pxe_file if distro==None (smoser@brickies.net)
- [BUGFIX] Changed findkeys function to be consisten with keep_ssh_host_keys snippet
  (flaks@bnl.gov)
- [BUGFIX] Fix for issue #15 - cobbler image command does not recognize
  --image-type=memdisk (jimi@sngx.net)
- [BUGFIX] Issue #13 - reposync with --tries > 1 always repeats, even on
  success The success flag was being set when the reposync ran, but didn't
  break out of the retry loop - easy fix (jimi@sngx.net)
- [BUGFIX] Fix for issue #42 - kickstart not found error when path has leading
  space (jimi@sngx.net)
- [BUGFIX] Fix for issue #26 - Web Interface: Profile Edit
  * Added jquery UI stuff 
  * Added javascript to generic_edit template to make all selects in the 
    class "edit" resizeable
  (jimi@sngx.net)
- [BUGFIX] Fix for issue #53 - cobbler system add without --profile exits 0,
  but does nothing (jimi@sngx.net)
- [BUGFIX] Issue #73 - Broken symlinks on distro rename from web_gui
  (jimi@sngx.net)
- regular OS version maintenance (jorgen.maas@gmail.com)
- [BUGFIX] let koan not overwrite existing initrd+kernel (ug@suse.de)
- [FEATURE] koan: 
  * Port imagecreate to virt-install (crobinso@redhat.com)
  * Port qcreate to virt-install (crobinso@redhat.com)
  * Port xen creation to virt-install (crobinso@redhat.com)
- [FEATURE] new snippet allows for certificate-based RHN registration
  (jim.nachlin@gawker.com)
- [FEATURE] Have autoyast by default behave more like RHEL, regarding networking etc.
  (chorn@fluxcoil.net)
- [BUGFIX] sles patches (chorn@fluxcoil.net)
- [BUGFIX] Simple fix for issue where memtest entries were not getting created after
  installing memtest86+ and doing a cobbler sync (rharriso@redhat.com)
- [BUGFIX] REMOTE_ADDR was not being set in the arguments in calls to CobblerSvc
  instance causing ip address not to show up in install.log.
  (jweber@cofront.net)
- [BUGFIX] add missing import of shutil (aparsons@redhat.com)
- [BUGFIX] add a sample kickstart file for ESXi (aparsons@redhat.com)
- [BUGFIX] the ESXi installer allows two nameservers to be defined (aparsons@redhat.com)
- [BUGFIX] close file descriptors on backgrounded processes to avoid hanging %%pre
  (aparsons@redhat.com)
- [BUGFIX] rsync copies the repositories with --delete hence deleting everyhting local
  that isn't on the source server. The createrepo then creates (following the
  default settings) a cache directory ... which is deleted by the next rsync
  run. Putting the cache directory in the rsync exclude list avoids this
  deletion and speeds up running reposync dramatically. (niels@basjes.nl)
- [BUGFIX] Properly blame SELinux for httpd_can_network_connect type errors on initial
  setup. (michael.dehaan@gmail.com)
- fix install=... kernel parameter when importing a SUSE distro (ug@suse.de)
- [BUGFIX] Force Django to use the system's TIME_ZONE by default.
  (jorgen.maas@gmail.com)
- [FEATURE] Separated check for permissions from file existence check.
  (aaron.peschel@gmail.com)
- [BUGFIX] If the xendomain symlink already exists, a clearer error will be produced.
  (aaron.peschel@gmail.com)
- [FEATURE] Adding support for ESXi5, and fixing a few minor things (like not having a
  default kickstart for esxi4) Todos:   * The esxi*-ks.cfg files are empty, and
  need proper kickstart templates   * Import bug testing and general kickstart
  testing (jimi@sngx.net)
- [FEATURE] Adding basic support for gPXE (jimi@sngx.net)
- [FEATURE] Add arm as a valid architecture. (chuck.short@canonical.com)
- [SECURITY] Changes PYTHON_EGG_CACHE to a safer path owned just by the webserver.
  (chuck.short@canonical.com)
- [BUGFIX] koan: do not include ks_meta args when obtaining tree When obtaining the tree
  for Ubuntu machines, ensure that ks_meta args are not passed as part of the
  tree if they exist. (chuck.short@canonical.com)
- [FEATURE] koan: Use grub2 for --replace-self instead of grubby The koan option
  '--replace-self' uses grubby, which relies on grub1, to replace a local
  installation by installing the new kernel/initrd into grub menu entries.
  Ubuntu/Debian no longer uses it grub1. This patch adds the ability to use
  grub2 to add the kernel/initrd downloaded to a menuentry. On reboot, it will
  boot from the install kernel reinstalling the system. Fixes (LP: #766229)
  (chuck.short@canonical.com)
- [BUGFIX] Fix reposync missing env variable for debmirror  Fixes missing HOME env
  variable for debmirror by hardcoding the environment variable  to
  /var/lib/cobbler (chuck.short@canonical.com)
- [BUGFIX] Fix creation of repo mirror when importing iso. Fixes the creation of a
  disabled repo mirror when importing ISO's such as the mini.iso that does not
  contain any mirror/packages. Additionally, really enables 'apt' as possible
  repository. (chuck.short@canonical.com)
- [BUGFIX] adding default_template_type to settings.py, caused some issues with
  templar when the setting was not specified in the /etc/cobbler/settings
  (jimi@sngx.net)
- [BUGFIX] fix for following issue: can't save networking options of a system
  in cobbler web interface. (#8) (jimi@sngx.net)
- [BUGFIX] Add a new setting to force CLI commands to use the localhost for xmlrpc
  (chjohnst@gmail.com)
- [BUGFIX] Don't blow up on broken links under /var/www/cobbler/links
  (jeffschroeder@computer.org)
- [SECURITY] Making https the default for the cobbler web GUI. Also modifying the cobbler-
  web RPM build to require mod_ssl and mod_wsgi (missing wsgi was an oversight,
  just correcting it now) (jimi@sngx.net)
- [FEATURE] Adding authn_pam. This also creates a new setting - authn_pam_service, which
  allows the user to configure which PAM service they want to use for cobblerd.
  The default is the 'login' service (jimi@sngx.net)
- [SECURITY] Change in cobbler.spec to modify permissions on webui sessions directory to
  prevent non-privileged user acccess to the session keys (jimi@sngx.net)
- [SECURITY] Enabling CSRF protection for the web interface (jimi@sngx.net)
- [SECURITY] Convert all yaml loads to safe_loads for security/safety reasons.
  https://bugs.launchpad.net/ubuntu/+source/cobbler/+bug/858883 (jimi@sngx.net)
- [FEATURE] Added the setting 'default_template_type' to the settings file, and created
  logic to use that in Templar().render(). Also added an option to the same
  function to pass the template type in as an argument. (jimi@sngx.net)
- [FEATURE] Initial commit for adding support for other template languages, namely jinja2
  in this case (jimi@sngx.net)

* Tue Nov 15 2011 Scott Henson <shenson@redhat.com> 2.2.2-1
- Changelog update (shenson@redhat.com)
- Fixed indentation on closing tr tag (gregswift@gmail.com)
- Added leader column to the non-generic tables so that all tables have the
  same layout. It leaves room for a checkbox and multiple selects i nthese
  other tables as well. (gregswift@gmail.com)
- Added action class to the event log link to bring it inline with other table
  functions (gregswift@gmail.com)
- buildiso bugfix: overriding dns nameservers via the dns kopt now works.
  reported by Simon Woolsgrove <simon@woolsgrove.com> (jorgen.maas@gmail.com)
- Fix for pxegen, where an image without a distro could cause a stack dump on
  cobbler sync (jimi@sngx.net)
- Added initial support for specifying the on-disk format of virtual disks,
  currently supported for QEMU only when using koan (jimi@sngx.net)
- Add fedora16, rawhide, opensuse 11.2, 11.3, 11.4 and 12.1 to codes.py This
  should also fix ticket #611 (jorgen.maas@gmail.com)
- Use VALID_OS_VERSIONS from codes.py in the redhat importer.
  (jorgen.maas@gmail.com)
- Cleanup: use utils.subprocess_call in services.py (jorgen.maas@gmail.com)
- Cleanup: use utils.subprocess_call in remote.py. (jorgen.maas@gmail.com)
- Cleanup: use utils.subprocess_call in scm_track.py. Also document that 'hg'
  is a valid option in the settings file. (jorgen.maas@gmail.com)
- Dont import the sub_process module when it's not needed.
  (jorgen.maas@gmail.com)
- Fixes to import_tree() to actually copy files to a safe place when
  --available-as is specified. Also some cleanup to the debian/ubuntu import
  module for when --available-as is specified. (jimi@sngx.net)
- Modification to import processes so that rsync:// works as a path. These
  changes should also correct the incorrect linking issue where the link
  created in webdir/links/ pointed at a directory in ks_mirror without the arch
  specified, resulting in a broken link if --arch was specified on the command
  line Also removed the .old import modules for debian/ubuntu, which were
  replaced with the unified manage_import_debian_ubuntu.py (jimi@sngx.net)
- cleanup: use codes.VALID_OS_VERSIONS in the freebsd importer
  (jorgen.maas@gmail.com)
- cleanup: use codes.VALID_OS_VERSIONS in the debian/ubuntu importer
  (jorgen.maas@gmail.com)
- Bugfix: add the /var/www/cobbler/pub directory to setup.py. Calling buildiso
  from cobbler-web now works as expected. (jorgen.maas@gmail.com)
- BUGFIX: patch koan (xencreate) to correct the same issue that was broken for
  vmware regarding qemu_net_type (jimi@sngx.net)
- BUGFIX: fixed issue with saving objects in the webgui failing when it was the
  first of that object type saved. (jimi@sngx.net)
- Minor fix to the remote version to use the nicer extended version available
  (jimi@sngx.net)
- Fix a bug in buildiso when duplicate kopt keys are used. Reported and tested
  by Simon Woolsgrove <simon@woolsgrove.com> (jorgen.maas@gmail.com)
- Fix for koan, where vmwcreate.py was not updated to accept the network type,
  causing failures. (jimi@sngx.net)
- Added a %post section for the cobbler-web package, which replaces the
  SECRET_KEY field in the Django settings.py with a random string
  (jimi@sngx.net)
- BUGFIX: added sign_puppet_certs_automatically to settings.py. The fact that
  this was missing was causing failures in the the pre/post puppet install
  modules. (jimi@sngx.net)
- set the auto-boot option for a virtual machine (ug@suse.de)
- Correction for koan using the incorrect default port for connecting to
  cobblerd (jimi@sngx.net)
- config/settings: add "manage_tftpd: 1" (default setting)
  (cristian.ciupitu@yahoo.com)

* Wed Oct 05 2011 Scott Henson <shenson@redhat.com> 2.2.1-1
- Import changes for systemd from the fedora spec file (shenson@redhat.com)

* Wed Oct 05 2011 Scott Henson <shenson@redhat.com> 2.2.0-1
- Remove the version (shenson@redhat.com)
- New upstream 2.2.0 release (shenson@redhat.com)
- Add networking snippet for SuSE systems. (jorgen.maas@gmail.com)
- Add a /etc/hosts snippet for SuSE systems. (jorgen.maas@gmail.com)
- Add a proxy snippet for SuSE systems. (jorgen.maas@gmail.com)
- Buildiso: make use of the proxy field (SuSE, Debian/Ubuntu).
  (jorgen.maas@gmail.com)
- Rename buildiso.header to buildiso.template for consistency. Also restore the
  local LABEL in the template. (jorgen.maas@gmail.com)
- Bugfix: uppercase macaddresses used in buildiso netdevice= keyword cause the
  autoyast installer to not setup the network and thus fail.
  (jorgen.maas@gmail.com)
- Buildiso: minor cleanup diff. (jorgen.maas@gmail.com)
- Buildiso: behaviour changed after feedback from the community.
  (jorgen.maas@gmail.com)
- Build standalone ISO from the webinterface. (jorgen.maas@gmail.com)
- Fix standalone ISO building for SuSE, Debian and Ubuntu.
  (jorgen.maas@gmail.com)
- add proxy field to field_info.py (jorgen.maas@gmail.com)
- Remove FreeBSD from the unix breed as it has it's own now. Also, add freebsd7
  as it is supported until feb 2013. Minor version numbers don't make sense,
  also removed. (jorgen.maas@gmail.com)
- Add a proxy field to profile and system objects. This is useful for
  environments where systems are not allowed to make direct connections to the
  cobbler/repo servers. (jorgen.maas@gmail.com)
- Introduce a "status" field to system objects. Useful in environments where
  DTAP is required, the possible values for this field are: development,
  testing, acceptance, production (jorgen.maas@gmail.com)
- Buildiso: only process profiles for selected systems. (jorgen.maas@gmail.com)
- Buildiso: add batch action to build an iso for selected profiles.
  (jorgen.maas@gmail.com)
- Buildiso: use management interface feature. (jorgen.maas@gmail.com)
- Buildiso: get rid of some code duplication (ISO header).
  (jorgen.maas@gmail.com)
- Buildiso: add interface to macaddr resolution. (jorgen.maas@gmail.com)
- Buildiso: add Debian and Ubuntu support. (jorgen.maas@gmail.com)
- Buildiso: select systems from the webinterface. (jorgen.maas@gmail.com)
- Fix an exception when buildiso is called from the webinterface.
  (jorgen.maas@gmail.com)
- fix power_virsh template to check dom status before executing command.
  (bpeck@redhat.com)
- if hostname is not resolvable do not fail and use that hostname
  (msuchy@redhat.com)
- Removed action_import module and references to it in code to prevent future
  confusion. (jimi@sngx.net)
- Fixing redirects after a failed token validation. You should now be
  redirected back to the page you were viewing after having to log back in due
  to a forced login. (jimi@sngx.net)
- Use port to access cobbler (peter.vreman@acision.com)
- Stripping "g" from vgs output case-insensitive runs faster
  (mmello@redhat.com)
- Adding ability to create new sub-directories when saving snippets. Addresses
  trac #634 - save new snippet fails on non existing subdir (jimi@sngx.net)
- Fix traceback when executing "cobbler system reboot" with no system name
  specified Trac ticket #578 - missing check for name option with system reboot
  (jimi@sngx.net)
- bind zone template writing (jcallaway@squarespace.com)
- Removing the duplicate lines from importing re module (mmello@redhat.com)
- Merge remote-tracking branch 'jimi1283/bridge-interface' (shenson@redhat.com)
- Modification to allow DEPRECATED options to be added as options to optparse
  so they work as aliases (jimi@sngx.net)
- Re-adding the ability to generate a random mac from the webui. Trac #543
  (Generate random mac missing from 2.x webui) (jimi@sngx.net)
- Merge remote-tracking branch 'jsabo/fbsdreplication' (shenson@redhat.com)
- Tim Verhoeven <tim.verhoeven.be@gmail.com> (Tue. 08:35) (Cobbler attachment)
  Subject: [PATCH] Add support to koan to select type of network device to
  emulate To: cobbler development list <cobbler-devel@lists.fedorahosted.org>
  Date: Tue, 2 Aug 2011 14:35:21 +0200 (shenson@redhat.com)
- Hello, (shenson@redhat.com)
- scm_track: Add --all to git add options to handle deletions (tmz@pobox.com)
- Moved HEADER heredoc from action_buildiso.py to
  /etc/cobbler/iso/buildiso.header (gbailey@terremark.com)
- Enable replication for FreeBSD (jsabo@verisign.com)
- Merge branch 'master' into bridge-interface (jimi@sngx.net)
- Remove json settings from local_get_cobbler_xmlrpc_url() (jsabo@verisign.com)
- 1) Moving --subnet field to --netmask 2) Created DEPRECATED_FIELDS structure
  in field_info.py to deal with moves like this    * also applies to the
  bonding->interface_type move for bridged interface support (jimi@sngx.net)
- Merge remote-tracking branch 'jimi1283/bridge-interface' (shenson@redhat.com)
- Fixing up some serializer module stuff:  * detecting module load errors when
  trying to deserialize collections  * added a what() function to all the
  serializer modules for ID purposes  * error detection for mongo stuff,
  including pymongo import problems as well as connection issues
  (jimi@sngx.net)
- Cleanup of bonding stuff in all files, including webui and koan. Additional
  cleanup in the network config scripts, and re-added the modprobe.conf
  renaming code to the post install network config. (jimi@sngx.net)
- Initial rework to allow bridge/bridge slave interfaces Added static route
  configuration to pre_install_network_config Major cleanup/reworking of
  post_install_network_config script (jimi@sngx.net)
- Fix for bad commit of some json settings test (jimi@sngx.net)
- Merge remote-tracking branch 'jsabo/fbsdimport' (shenson@redhat.com)
- Adding initial support for FreeBSD media importing (jsabo@verisign.com)
- Setting TIME_ZONE to None in web/settings.py causes a 500 error on a RHEL5
  system with python 2.4 and django 1.1. Commenting out the config line has the
  same effect as setting it to None, and prevents the 500. (jimi@sngx.net)
- Fixes for importing RHEL6:  * path_tail() was previously moved to utils, a
  couple    places in the import modules still used self.path_tail    instead
  of utils.path_tail, causing a stack dump  * Fixed an issue in
  utils.path_tail(), which was using self.    still from when it was a member
  of the import class  * When mirror name was set on import and using
  --available-as,    it was appending a lot of junk instead of just using the
  specified    mirror name (jimi@sngx.net)
- Merge branch 'master' of git://git.fedorahosted.org/cobbler (jimi@sngx.net)
- Fix a quick error (shenson@redhat.com)
- Set the tftpboot dir for rhel6 hosts (jsabo@verisign.com)
- Fixed a typo (jorgen.maas@gmail.com)
- Added an extra field in the system/interface item. The field is called
  "management" and should be used to identify the management interface, this
  could be useful information for multihomed systems. (jorgen.maas@gmail.com)
- In the event log view the data/time field got wrapped which is very annoying.
  Fast fix for now, i'm pretty sure there are better ways to do this.
  (jorgen.maas@gmail.com)
- Event log soring on date reverted, let's sort on id instead. Reverse over
  events in the template. Convert gmtime in the template to localtime.
  (jorgen.maas@gmail.com)
- Sort the event log by date/time (jorgen.maas@gmail.com)
- Remove some unsupported OS versions from codes.py (jorgen.maas@gmail.com)
- Some changes in the generate_netboot_iso function/code: - Users had to supply
  all system names on the commandline which they wanted to include in the ISO
  boot menu. This patch changes that behaviour; all systems are included by
  default now. You can still provide an override with the --systems parameter,
  thus making this feature more consistent with what one might expect from
  reading the help. - While at it I tried to make the code more readable and
  removed some unneeded iterations. - Prevent some unneeded kernel/initrd
  copies. - You can now override ip/netmask/gateway/dns parameters with
  corresponding kernel_options. - Fixed a bug for SuSE systems where ksdevice
  should be netdevice. - If no ksdevice/netdevice (or equivalent) has been
  supplied via kernel_options try to guess the proper interface to use, but
  don't just use one if we can't be sure about it (e.g. for multihomed
  systems). (jorgen.maas@gmail.com)
- Add SLES 11 to codes.py (jorgen.maas@gmail.com)
- Add support for Fedora15 to codes.py (jorgen.maas@gmail.com)
- Django uses the timezone information from web/settings.py Changing the
  hardcoded value to None forces Django to use the systems timezone instead of
  this hardcoded value (jorgen.maas@gmail.com)
- Fix cobbler replication for non-RHEL hosts. The slicing used in the
  link_distro function didn't work for all distros. (jsabo@verisign.com)
- Fix vmware esx importing. It was setting the links dir to the dir the iso was
  mounted on import (jsabo@verisign.com)
- Merge remote-tracking branch 'jsabo/webuifun' (shenson@redhat.com)
- Fix bug with esxi replication. It wasn't rsyncing the distro over if the
  parentdir already existed. (jsabo@verisign.com)
- Merge branch 'master' of git://git.fedorahosted.org/cobbler (jimi@sngx.net)
- Initial commit for mongodb backend support and adding support for settings as
  json (jimi@sngx.net)
- Web UI patches from Greg Swift applied (jsabo@verisign.com)
- whitespace fix (dkilpatrick@verisign.com)
- Fix to fix to py_tftp change to sync in bootloaders
  (dkilpatrick@verisign.com)
- Fixing a bug reported by Jonathan Sabo. (dkilpatrick@verisign.com)
- Merge branch 'master' of git://git.fedorahosted.org/cobbler
  (dkilpatrick@verisign.com)
- Revert "Jonathan Sabo <jsabo@criminal.org> (June 09) (Cobbler)"
  (shenson@redhat.com)
- Unmount and deactivate all software raid devices after searching for ssh keys
  (jonathan.underwood@gmail.com)
- Merge remote-tracking branch 'ugansert/master' (shenson@redhat.com)
- Jonathan Sabo <jsabo@criminal.org> (June 09) (Cobbler) Subject: [PATCH] Fix
  issue with importing distro's on new cobbler box To: cobbler development list
  <cobbler-devel@lists.fedorahosted.org> Date: Thu, 9 Jun 2011 16:17:20 -0400
  (shenson@redhat.com)
- missing manage_rsync option from config/settings (jsabo@criminal.org)
- Remove left-over debugging log message (dkilpatrick@verisign.com)
- SUSE requires the correct arch to find kernel+initrd on the inst-source
  (ug@suse.de)
- added autoyast=... parameter to the ISO building code when breed=suse
  (ug@suse.de)
- calculate meta data in the XML file without cheetah variables now
  (ug@suse.de)
- render the cheetah template before passing the XML to the python XML parser
  (ug@suse.de)
- made the pathes flexible to avoid problem on other distros than fedora/redhat
  (ug@suse.de)
- bugfix (ug@suse.de)
- Merge patch from stable (cristian.ciupitu@yahoo.com)
- utils: initialize main_logger only when needed (cristian.ciupitu@yahoo.com)
- During refactor, failed to move templater initialization into
  write_boot_files_distro. (dkilpatrick@verisign.com)
- Fixed a couple of simple typos.  Made the boot_files support work (added
  template support for the key, defined the img_path attribute for that
  expansion) (dkilpatrick@verisign.com)
- Fixes to get to the "minimally tested" level.  Fixed two syntax errors in
  tftpd.py, and fixed refences to api and os.path in manage_in_tftpd.py
  (dkilpatrick@verisign.com)
- Rebasing commit, continued. (kilpatds@oppositelock.org)
- Change the vmware stuff to use 'boot_files' as the space to set files that
  need to be available to a tftp-booting process (dkilpatrick@verisign.com)
- Added 'boot_files' field for 'files that need to be put into tftpboot'
  (dkilpatrick@verisign.com)
- Merge conflict. (kilpatds@oppositelock.org)
- Add in a default for puppet_auto_setup, thanks to Camille Meulien
  <cmeulien@heliostech.fr> for finding it. (shenson@redhat.com)
- Add a directory remap feature to fetchable_files processing.    /foo/*=/bar/
  Client requests for "/foo/baz" will be turned into requests for /bar/baz.
  Target paths are evaluated against the root filesystem, not tftpboot.
  Template expansion is done on "bar/baz", so that would typically more
  usefully be something like         /boot/*=$distro_path/boot
  (dkilpatrick@verisign.com)
- Removed trailing whitespace causing git warnings (dkilpatrick@verisign.com)
- Fix a bug where tftpd.py would throw if a client requested '/'.
  (dkilpatrick@verisign.com)
- Allow slop in the config, not just the client.  modules: don't hardcode
  /tftpboot (dkilpatrick@verisign.com)
- Moved footer to actually float at the bottom of the page or visible section,
  whichever is further down. Unfortunately leaves a slightly larger margin pad
  on there.  Will have to see if it can be made cleaner (gregswift@gmail.com)
- Removed right padding on delete checkboxes (gregswift@gmail.com)
- Adjusted all the self closing tags to end eith a " />" instead of not having
  a space separating them (gregswift@gmail.com)
- Added "add" button to the filter bit (gregswift@gmail.com)
- Removed "Enabled" label on checkboxes, this can be added via css as part of
  the theme if people want it using :after { content: " Enabled" } Padded the
  context-tip off the checkboxes so that it lines up with most of the other
  context tips instead of being burring in the middle of the form
  (gregswift@gmail.com)
- Added bottom margin on text area so that it isn't as tight next to other form
  fields (gregswift@gmail.com)
- Added id tags to the forms for ks templates and snippets Set some margins for
  those two forms, they were a bit scrunched because they didn't have a
  sectionbody fieldset and legend Removed inline formatting of input sizes on
  those two pages Set the textareas in those two pages via css
  (gregswift@gmail.com)
- Made the tooltips get hiddent except for on hover, with a small image
  displayed in their place (gregswift@gmail.com)
- Added a top margin to the submit/reset buttons... looks cleaner having some
  space. (gregswift@gmail.com)
- Changed generic edit form to the following: - Made blocks into fieldsets
  again, converting the h2 to a legend.  I didn't mean to change this the first
  time through. - Pulled up a level, removing the wrapping div, making each
  fieldset contain an order list, instead of each line being an ordered list,
  which was silly of me. - Since it went up a level, un-indented all of the
  internal html tags 2 spaces - changed the place holder for the network
  widgets to spans so that they displayed cleanly (Don't like the spans either,
  but its for the javascript) In the stylesheet just changed the
  div.sectionbody to ol.sectionbody (gregswift@gmail.com)
- Fixed closing ul->div on multiselect section. Must have missed it a few
  commits ago. (gregswift@gmail.com)
- IE uses input styling such as borders even on checkboxes... was not intended,
  so has been cleared for checkboxes (gregswift@gmail.com)
- This is a change to the multiselect buttons view,  i didn't mean to commit
  the style sheet along with the spelling check fixes, but since I did might as
  well do the whole thing and then erevert it later if people dislike it
  (gregswift@gmail.com)
- Fixed another postition mispelling (gregswift@gmail.com)
- fixed typo postition should be position (gregswift@gmail.com)
- Returned the multiselect section to being div's, since its actually not a set
  of list items, it is a single list item. Re-arranged the multiselect so that
  the buttons are centered between the two sections Removed all of the line
  breaks form that section Made the select box headings actually labels moved
  the order of multiselect after sectionbody definition due to inheritence
  (gregswift@gmail.com)
- Restored select boxes to "default" styling since they are not as cleanly css-
  able Made visibly selected action from Batch Actions bold, mainly so by
  default Batch Action is bold. Moved text-area and multi-select sizing into
  stylesheet. re-alphabetized some of the tag styles Made the default login's
  text inputs centered, since everything else on that page is
  (gregswift@gmail.com)
- Added missing bracket from two commits ago in the stylesheet.
  (gregswift@gmail.com)
- Re-added the tool tips for when they exist in the edit forms and set a style
  on them. Removed an extraneous line break from textareas in edit form
  (gregswift@gmail.com)
- Fixed javascript where I had used teh wrong quotes, thus breaking the network
  interface widgets (gregswift@gmail.com)
- Added label and span to cleanup block (gregswift@gmail.com)
- Added version across all of the template loads so that the footer is
  populated with it (gregswift@gmail.com)
- all css: - set overall default font size of 1em - added missing tags to the
  cleanup css block - fixed button layout -- list line buttons are smaller font
  to keep lines smaller -- set action input button's size - set indentation and
  bolding of items in batch action - redid the list formatting -- removed zebra
  stripes, they share the standard background now -- hover is now the
  background color of the old darker zebra stripe -- selected lines now
  background of the older light zebra stripe - added webkit border radius
  (gregswift@gmail.com)
- generic_lists.tmpl - Removed force space on the checklists generic_lists.tmpl
  - Added javascript to allow for selected row highlighting
  (gregswift@gmail.com)
- Removed inline formatting from import.tmpl Made the context tips spans
  (gregswift@gmail.com)
- Made both filter-adder elements exist in the same li element
  (gregswift@gmail.com)
- Added default formatting for ordered lists Added formatting for the new
  multiselect unordered list Changed old div definitions for the multiselect to
  li Added label formatting for inside sectionbody to line up all the forms.
  (gregswift@gmail.com)
- Adjusted multiselect section to be an unordered list instead of a div
  (gregswift@gmail.com)
- Moved the close list tag inside the for loop, otherwise we generate lots of
  nasty nested lists (gregswift@gmail.com)
- Changed edit templates to use ol instead of ul, because it apparently helps
  out those using screen readers, and we should be making things accessible,
  yes? (gregswift@gmail.com)
- Re-structured the edit templates to be unordered lists. Standardized the
  tooltip/contextual data as context-tip class Redid the delete setup so that
  its Delete->Really? Instead of Delete:Yes->Really?  Same number of check
  boxes. Setup the delete bit so that Delete and Really are labels for the
  checkboxes and there isn't extraneous html input tags (gregswift@gmail.com)
- Added top margin on the filter adder (gregswift@gmail.com)
- Adjusted single action item buttons to be in the same list element, as it
  makes alignment cleaner, and more sense from a grouping standpoint Set
  submenubar default height to 26px Set submenubar's alignment to be as clean
  as I've been able to get so far. (gregswift@gmail.com)
- Set background color back to original (gregswift@gmail.com)
- Adjusted all buttons to hover invert from blue to-blackish, the inverse of
  the normal links (which go blackish to blue) but left the text color the
  same.  i'm not sure its as pretty, but dfinately more readable.  Plus the
  color change scheme is more consistant. Also made table buttons smaller than
  other buttons (gregswift@gmail.com)
- Fixed width on paginate select boxes to auto, instead of over 200px
  (gregswift@gmail.com)
- Removed margin around hr tag, waste of space, and looks closer to original
  now (gregswift@gmail.com)
- Removed extraneous body div by putting user div inside container.
  (gregswift@gmail.com)
- Adjuested style sheet to improve standardization of form fields, such as
  buttons, text input widths, and fontsizes in buttons vs drop downs.
  (gregswift@gmail.com)
- Some menu re-alignment on both menubar and submenubar (gregswift@gmail.com)
- Got the container and the user display into a  cleaner size alignment to
  display on the screen.  less chance of horiz scroll (gregswift@gmail.com)
- Fix to get login form a bit better placed without duplicate work
  (gregswift@gmail.com)
- pan.action not needed... .action takes care of it (gregswift@gmail.com)
- Removed padding on login screen (gregswift@gmail.com)
- Redid action and button classes to make them look like buttons.. still needs
  work. Resized pointer classes to make things a bit more level on that row
  (gregswift@gmail.com)
- New cleanup at the top negates the need for this table entry
  (gregswift@gmail.com)
- Removed the body height to 99%.  Was doing this for sticky footer, but
  current path says its not needed (gregswift@gmail.com)
- Added some windows and mac default fonts Made the body relative, supposed to
  help with the layout Set text color to slightly off black.. was told there is
  some odd optical reasoning behind this (gregswift@gmail.com)
- Made class settings for the table rows a touch more specific in the css
  (gregswift@gmail.com)
- Added "normalization" to clean up cross browser differences at top of
  style.css (gregswift@gmail.com)
- Added button class to all buttons, submit, and resets (gregswift@gmail.com)
- Fixed sectionheader to not be styled as actions... they are h2!
  (gregswift@gmail.com)
- Fixed container reference from class to id (gregswift@gmail.com)
- Added missing action class on the "Create new" links in generic_list.tmpl
  (gregswift@gmail.com)
- Revert part of 344969648c1ce1e753af because RHEL5's django doesn't support
  that (gregswift@gmail.com)
- removed underline on remaing links (gregswift@gmail.com)
- Fixed the way the logo was placed on the page and removed the excess
  background setting. (gregswift@gmail.com)
- Some cleanup to the style sheet along - removed fieldset since no more exist
  (not sure about this in long run.... we'll see) - cleaned up default style
  for ul cause it was causing override issues - got menubar and submenu bar
  mostly settled (gregswift@gmail.com)
- Fixed submenu bar ul to be identified by id not class (gregswift@gmail.com)
- Rebuilt primary css stylesheet - not complete yet (gregswift@gmail.com)
- Removed logout from cobbler meft hand menu (gregswift@gmail.com)
- Next step in redoing layout: - added current logged in user and logout button
  to a div element at top of page - fixed content div from class to id - added
  footer (version entry doesn't work for some reason) - links to cobbler
  website (gregswift@gmail.com)
- in generic_list.tmpl - set the edit link to class 'action' - merged the
  creation of the edit action 'View kickstart' for system and profile
  (gregswift@gmail.com)
- Replaced tool tip as div+em with a span classed as tooltip. tooltip class
  just adds italic. (gregswift@gmail.com)
- Fixed table header alignment to left (gregswift@gmail.com)
- Take the logo out of the html, making it a css element, but retain the
  location and basic feel of the placement. (gregswift@gmail.com)
- Step one of redoing the action list, pagination and filters. - split
  pagination and filters to two tmpl files - pagination can be called on its
  own (so it can live in top and bottom theoretically) - filter will eventually
  include pagination so its on the bottom - new submenubar includes pagination
  - new submenubar does age specific actiosn as links instead of drop downs
  cause there is usually 1, rarely 2, never more. (gregswift@gmail.com)
- Removed pagination from left hand column (gregswift@gmail.com)
- Removed an erroneous double quote from master.tmpl (gregswift@gmail.com)
- Went a bit overboard and re-adjusted whitespace in all the templates. Trying
  to do the code in deep blocks across templates can be a bit tedious and
  difficult to maintain. While the output is not perfect, at least the
  templates are more readable. (gregswift@gmail.com)
- Removed remaining vestige of action menu shading feature
  (gregswift@gmail.com)
- Removed header shade references completely from the lists and the code from
  master.tmpl (gregswift@gmail.com)
- Wrapped setting.tmpl error with the error class (gregswift@gmail.com)
- Changed h3 to h2 inside pages Made task_created's h4 into a h1 and
  standarized with the other pages (gregswift@gmail.com)
- Standardized header with a hr tag before the form tags (gregswift@gmail.com)
- Added base width on the multiple select boxes, primarily for when they are
  empty (gregswift@gmail.com)
- Removed fieldset wrappers and replaced legends with h1 and h2 depending on
  depth (gregswift@gmail.com)
- Adjusted logic for the legent to only change one word, instead of the full
  string (gregswift@gmail.com)
- Removed empty cell from table in generic_edit.tmpl (gregswift@gmail.com)
- Revert 8fed301e61f28f8eaf08e430869b5e5df6d02df0 because it was to many
  different changes (gregswift@gmail.com)
- Removed empty cell from table in generic_edit.tmpl (gregswift@gmail.com)
- Moved some cobbler admin and help menus to a separate menu in the menubar
  (gregswift@gmail.com)
- Added HTML5 autofocus attribute to login.tmpl.  Unsupported browsers just
  ignores this. (gregswift@gmail.com)
- Re-built login.tmpl: - logo isn't a link anymore back to the same page - logo
  is centered with the login form - fieldset has been removed - set a css class
  for the body of the login page, unused for now. And the css: - removed the
  black border from css - centered the login button as well
  (gregswift@gmail.com)
- Made the links and span.actions hover with the same color as used for the
  section headings (gregswift@gmail.com)
- Removed as much in-HTML placed formatting as possible and implemented them in
  css. The main bit remaining is the ul.li floats in paginate.tmpl
  (gregswift@gmail.com)
- Cleaned up single tag closing for several of the checkboxes
  (gregswift@gmail.com)
- removed a trailing forward slash that was creating an orphaned close span tag
  (gregswift@gmail.com)
- Relabeled cells in thead row from td tags to th (gregswift@gmail.com)
- Added tr wrapper inside thead of tables for markup validation
  (gregswift@gmail.com)
- Use :// as separator for virsh URIs (atodorov@otb.bg)
- Create more condensed s390 parm files (thardeck@suse.de)
- Add possibility to interrupt zPXE and to enter CMS (thardeck@suse.de)
- Cleanup the way that we download content  - Fixes a bug where we were only
  downloading grub-x86_64.efi (shenson@redhat.com)
- Port this config over as well (shenson@redhat.com)
- Only clear logs that exist. (bpeck@redhat.com)
- Pull in new configs from the obsoletes directory. (shenson@redhat.com)
- Removed extraneous close row tag from events.tmpl (gregswift@gmail.com)
- Fixed spelling of receive in enoaccess.tmpl (gregswift@gmail.com)
- Added missing close tags on a few menu unordered list items in master.tmpl
  (gregswift@gmail.com)
- Added missing "for" correlation tag for labels in generic_edit.tmpl
  (gregswift@gmail.com)
- Removed extraneous close divs from generic_edit.tmpl (gregswift@gmail.com)
- Removing old and unused template files (gregswift@gmail.com)
- Add support for Ubuntu distros. (andreserl@ubuntu.com)
- Koan install tree path for Ubuntu/Debian distros. (andreserl@ubuntu.com)
- Fixing hardlink bin path. (andreserl@ubuntu.com)
- Do not fail when yum python module is not present. (andreserl@ubuntu.com)
- Add Ubuntu/Debian support to koan utils for later use. (andreserl@ubuntu.com)
- typo in autoyast xml parsing (ug@suse.de)
- Minor change to validate a token before checking on a user. (jimi@sngx.net)
- get install tree from install=... parameter for SUSE (ug@suse.de)
- handle autoyast XML files (ug@suse.de)
- fixed support for SUSE in build-iso process. Fixed a typo (ug@suse.de)
- added SUSE breed to import-webui (ug@suse.de)
- Merge remote-tracking branch 'lanky/master' (shenson@redhat.com)
- Merge remote-tracking branch 'jimi1283/master' (shenson@redhat.com)
- added support for suse-distro import (ug@suse.de)
- Fix a sub_process Popen call that did not set close_fds to true. This causes
  issues with sync where dhcpd keeps the XMLRPC port open and prevents cobblerd
  from restarting (jimi@sngx.net)
- Cleanup of unneccsary widgets in distro/profile. These needed to be removed
  as part of the multiselect change. (jimi@sngx.net)
- Yet another change to multiselect editing. Multiselects are now presented as
  side-by-side add/delete boxes, where values can be moved back and forth and
  only appear in one of the two boxes. (jimi@sngx.net)
- Fix for django traceback when logging into the web interface with a bad
  username and/or password (jimi@sngx.net)
- Fix for snippet/kickstart editing via the web interface, where a 'tainted
  file path' error was thrown (jimi@sngx.net)
- added the single missed $idata.get() item (stuart@sjsears.com)
- updated post_install_network_config to use $idata.get(key, "") instead of
  $idata[key]. This stops rendering issues with the snippet when some keys are
  missing (for example after an upgrade from 2.0.X to 2.1.0, where a large
  number of new keys appear to have been added.) and prevents us from having to
  go through all system records and add default values for them.
  (stuart@sjsears.com)
- Take account of puppet_auto_setup in install_post_puppet.py
  (jonathan.underwood@gmail.com)
- Take account of puppet_auto_setup in install_pre_puppet.py
  (jonathan.underwood@gmail.com)
- Add puppet snippets to sample.ks (jonathan.underwood@gmail.com)
- Add puppet_auto_setup to settings file (jonathan.underwood@gmail.com)
- Add snippets/puppet_register_if_enabled (jonathan.underwood@gmail.com)
- Add snippets/puppet_install_if_enabled (jonathan.underwood@gmail.com)
- Add configuration of puppet pre/post modules to settings file
  (jonathan.underwood@gmail.com)
- Add install_post_puppet.py module (jonathan.underwood@gmail.com)
- Add install_pre_puppet.py module (jonathan.underwood@gmail.com)
- Apply a fix for importing red hat distros, thanks jsabo (shenson@redhat.com)
- Changes to action/batch actions at top of generic list pages * move logic
  into views, where it belongs * simplify template code * change actions/batch
  actions into drop down select lists * added/modified javascript to deal with
  above changes (jimi@sngx.net)
- Minor fixes to cobbler.conf, since the AliasMatch was conflicting with the
  WSGI script alias (jimi@sngx.net)
- Initial commit for form-based login and authentication (jimi@sngx.net)
- Convert webui to use WSGI instead of mod_python (jimi@sngx.net)
- Save field data in the django user session so the webui doesn't save things
  unnecessarily (jimi@sngx.net)
- Make use of --format in git and use the short hash. Thanks Todd Zullinger
  <tmz@pobox.com> (shenson@redhat.com)
- We need git. Thanks to Luc de Louw <luc@delouw.ch> (shenson@redhat.com)
- Start of the change log supplied by Michael MacDonald <mjmac@macdonald.cx>
  (shenson@redhat.com)
- Fix typo in cobbler man page entry for profile (jonathan.underwood@gmail.com)
- Fix cobbler man page entry for parent profile option
  (jonathan.underwood@gmail.com)
- Set SELinux context of host ssh keys correctly after reinstallation
  (jonathan.underwood@gmail.com)
- Fixing bug with img_path.  It was being used prior to being set if you have
  images. (jonathan.sabo@gmail.com)
- Add firstboot install trigger mode (jonathan.sabo@gmail.com)
- Fix old style shell triggers by checking for None prior to adding args to arg
  list and fix indentation (jonathan.sabo@gmail.com)
- Bugfix: restore --no-fail functionality to CLI reposync
  (icomfort@stanford.edu)
- Add the ability to replicate the new object types (mgmtclass,file,package).
  (jonathan.sabo@gmail.com)
- Add VMware ESX and ESXi replication. (jonathan.sabo@gmail.com)
- Add batch delete option for profiles and mgmtclasses
  (jonathan.sabo@gmail.com)
- Spelling fail (shenson@redhat.com)
- Remove deploy as a valid direct action (shenson@redhat.com)
- Trac Ticket #509: A fix that does not break everything else.
  (https://fedorahosted.org/cobbler/ticket/509) (andrew@eiknet.com)
- Only chown the file if it does not already exist (shenson@redhat.com)
- Modification to cobbler web interface, added a drop-down select box for
  management classes and some new javascript to add/remove items from the
  multi-select (jimi@sngx.net)
- Check if the cachedir exists before we run find on it. (shenson@redhat.com)
- Fix trac#574 memtest (shenson@redhat.com)
- Add network config snippets for esx and esxi network configuration
  $SNIPPET('network_config_esxi') renders to: (jonathan.sabo@gmail.com)
- Trac Ticket #510: Modified 'cobbler buildiso' to use
  /var/cache/cobbler/buildiso by default. Added a /etc/cobbler/settings value
  of 'buildisodir' to make it setable by the end user. --tempdir will still
  overwrite either setting on the command line. (andrew@eiknet.com)
- Add img_path to the metadata[] so that it's rendered out in the esxi pxe
  templates. Add os_version checks for esxi in kickstart_done so that it uses
  wget or curl depending on what's known to be available.
  (jonathan.sabo@gmail.com)
- Added --sync-all option to cobbler replicate which forces all systems,
  distros, profiles, repos and images to be synced without specifying each.
  (rrr67599@rtpuw027.corpnet2.com)
- Added manage_rsync option which defaults to 0. This will make cobbler not
  overwrite a local rsyncd.conf unless enabled.
  (rrr67599@rtpuw027.corpnet2.com)
- Added semicolon master template's placement of the arrow in the page heading
  (gregswift@gmail.com)
- Quick fix from jsabo (shenson@redhat.com)
- added hover line highlighting to table displays (gregswift@gmail.com)
- Modification to generic_edit template so that the name field is not a text
  box when editing. (jimi@sngx.net)
- Minor fixes for mgmt classes webui changes. - Bug when adding a new obj,
  since obj is None it was causing a django stack dump - Minor tweaks to
  javascript (jimi@sngx.net)
- Fixed error in which the json files for mgmtclasses was not being deleted
  when a mgmtclass was removed, meaning they showed back up the next time
  cobblerd was restarted (jimi@sngx.net)
- Fixed syntax error in clogger.py that was preventing cobblerd from starting
  (jimi@sngx.net)
- Supports an additional initrd from kernel_options. (bpeck@redhat.com)
- Remove a bogus self (shenson@redhat.com)
- Re-enable debmirror. (chuck.short@canonical.com)
- Extending the current Wake-on-Lan support for wider distro compatibility.
  Thanks to Dustin Kirkland. (chuck.short@canonical.com)
- Dont hardcode /etc/rc.d/init.d redhatism. (chuck.short@canonical.com)
- Newer (pxe|sys)linux's localboot value produces unreliable results when using
  documented options, -1 seems to provide the best supported value
  (chuck.short@canonical.com)
- Detect the webroot to be used based on the distro.
  (chuck.short@canonical.com)
- If the logfile path doesn't exist, don't attempt to create the log file.
  Mainly needed when cobbler is required to run inside the build env
  (cobbler4j). Thanks to Dave Walker <DaveWalker@ubuntu.com>
  (chuck.short@canonical.com)
- Implement system power status API method and CLI command (crosa@redhat.com)
- Update setup files to use proper apache configuration path
  (konrad.scherer@windriver.com)
- Debian has www-data user for web server file access instead of apache.
  (konrad.scherer@windriver.com)
- Update init script to work under debian. (konrad.scherer@windriver.com)
- Use lsb_release module to detect debian distributions. Debian release is
  returned as a string because it could be sid which will never have a version
  number. (konrad.scherer@windriver.com)
- Fix check for apache installation (konrad.scherer@windriver.com)
- Handle Cheetah version with more than 3 parts (konrad.scherer@windriver.com)
- Allow dlcontent to use proxy environment variables (shenson@redhat.com)
- Copy memtest to $bootloc/images/.  Fixes BZ#663307 (shenson@redhat.com)
- Merge remote branch 'jimi1283/master' (shenson@redhat.com)
- Turn the cheetah version numbers into integers while testing them so we don't
  always return true (shenson@redhat.com)
- Kill some whitespace (shenson@redhat.com)
- Fix for bug #587 - Un-escaped '$' in snippet silently fails to render
  (jimi@sngx.net)
- Fix for bug #587 - Un-escaped '$' in snippet silently fails to render
  (jimi@sngx.net)
- Merge branch 'master' of git://git.fedorahosted.org/cobbler (jimi@sngx.net)
- Don't use link caching in places it isn't needed (shenson@redhat.com)
- Better logging on subprocess calls (shenson@redhat.com)
- Fix for trac #541 - cobbler sync deletes /var/www/cobbler/pub (jimi@sngx.net)
- Merged work in the import-modules branch with the debian/ubuntu modules
  created by Chuck Short (jimi@sngx.net)
- Merge branch 'cshort' into import-modules (jimi@sngx.net)
- Finished up debian/ubuntu support for imports Tweaked redhat/vmware import
  modules logging output Added rsync function to utils to get it out of each
  module  - still need to fix the redhat/vmware modules to actually use this
  (jimi@sngx.net)
- Initial commit for the Debian import module. * tested against Debian squeeze.
  (chuck.short@canonical.com)
- Initial commit for the Ubuntu import module. * tested against Natty which
  imported successfully. (chuck.short@canonical.com)
- tftp-hpa users for both Ubuntu Debian use /var/lib/tftpboot.
  (chuck.short@canonical.com)
- Disable the checks that are not really valid for Ubuntu or Debian.
  (chuck.short@canonical.com)
- Add myself to the authors file. (chuck.short@canonical.com)
- Updates for debian/ubuntu support in import modules (jimi@sngx.net)
- Fix a problem with cheetah >= 2.4.2 where the snippets were causing errors,
  particularly on F14 due to its use of cheetah 2.4.3. (shenson@redhat.com)
- Initial commit of the Ubuntu import module (jimi@sngx.net)
- Merge remote branch 'jimi1283/import-modules' (shenson@redhat.com)
- Merge remote branch 'jimi1283/master' (shenson@redhat.com)
- Extended ESX/ESXi support * Fixed release detection for both ESX and ESXi *
  Added support to kickstart_finder() so that the fetchable_files list gets
  filled out when the distro is ESXi (jimi@sngx.net)
- Fixed distro_adder() in manage_import_vmware so ESXi gets imported properly
  (jimi@sngx.net)
- Initial commit for the VMWare import module * tested against esx4 update 1,
  which imported successfully (jimi@sngx.net)
- Minor style changes for web css * darken background slightly so the logo
  doesn't look washed out * make text input boxes wider (jimi@sngx.net)
- Fix for the generic_edit function for the web page. The choices field for
  management classes was not being set for distros/profiles - only systems,
  causing a django stack dump (jimi@sngx.net)
- modify keep_ssh_host_keys snippet to use old keys during OS installation
  (flaks@bnl.gov)
- Merge remote branch 'jimi1283/master' (shenson@redhat.com)
- Added replicate to list of DIRECT_ACTIONS, so it shows up in the --help
  output (jimi@sngx.net)
- Merge branch 'master' into import-modules (jimi@sngx.net)
- Merge branch 'master' of git://git.fedorahosted.org/cobbler (jimi@sngx.net)
- Some fixes to the manage_import_redhat module * stop using mirror_name for
  path stuff - using self.path instead * fixed rsync command to use self.path
  too, this should really be made a global somewhere else though
  (jimi@sngx.net)
- Add synopsis entries to man page to enable whatis command
  (kirkland@ubuntu.com)
- Add "ubuntu" as detected distribution. (clint@ubuntu.com)
- Fix for redhat import module.  Setting the kickstart file with a default
  value was causing some issues later on with the kickstart_finder() function,
  which assumes all new profiles don't have a kickstart file yet
  (jimi@sngx.net)
- Fix for non x86 arches, bug and fix by David Robinson <zxvdr.au@gmail.com>
  (shenson@redhat.com)
- Don't die when we find deltas, just don't use them (shenson@redhat.com)
- Merge remote branch 'khightower/khightower/enhanced-configuration-management'
  (shenson@redhat.com)
- By: Bill Peck <bpeck@redhat.com> exclude initrd.addrsize as well.  This
  affects s390 builds (shenson@redhat.com)
- Fix an issue where an item was getting handed to remove_item instead of the
  name of the item.  This would cause an exception further down in the stack
  when .lower() was called on the object (by the call to get_item).
  (shenson@redhat.com)
- Add a check to make sure system is in obj_types before removing it. Also
  remove an old FIXME that this previously fixed (shenson@redhat.com)
- Fix regression in 2.0.8 that dumped  into pxe cfg files (shenson@redhat.com)
- Initial commit of import module for redhat (jimi@sngx.net)
- Merge branch 'master' of git://git.fedorahosted.org/cobbler (jimi@sngx.net)
- Added new modules for copying a distros's fetchable files to the
  /tftpboot/images directory   - add_post_distro_tftp_copy_fetchable_files.py
  copies on an add/edit   - sync_post_tftp_copy_fetchable_files.py copies the
  files for ALL distros on a full sync (jimi@sngx.net)
- Removed trailing '---' from each of the PXE templates for ESXi, which causes
  PXE issues (jimi@sngx.net)
- Make stripping of "G" from vgs output case-insensitive
  (heffer@fedoraproject.org)
- Replace rhpl with ethtool (heffer@fedoraproject.org)
- Add --force-path option to force overwrite of virt-path location
  (pryor@bnl.gov)
- item_[profile|system] - update parents after editing (mlevedahl@gmail.com)
- collection.py - rename rather than delete mirror dirs (mlevedahl@gmail.com)
- Wil Cooley <wcooley@nakedape.cc> (shenson@redhat.com)
- Merge remote branch 'kilpatds/io' (shenson@redhat.com)
- Add additional qemu_driver_type parameter to start_install function
  (Konrad.Scherer@windriver.com)
- Add valid debian names for releases (Konrad.Scherer@windriver.com)
- Add debian preseed support to koan (Konrad.Scherer@windriver.com)
- Add support for EFI grub booting. (dgoodwin@rm-rf.ca)
- Turn the 'daemonize I/O' code back on.  cobbler sync seems to still work
  (dkilpatrick@verisign.com)
- Fix some spacing in the init script (dkilpatrick@verisign.com)
- Added a copy-default attribute to koan, to control the params passed to
  grubby (paji@redhat.com)
- Turn on the cache by default Enable a negative cache, with a shorter timeout.
  Use the cache for normal lookups, not much ip-after-failed.
  (dkilpatrick@verisign.com)
- no passing full error message.  Der (dkilpatrick@verisign.com)
- Pull the default block size into the template, since that can need to be
  changed. Make tftpd.py understand -B for compatibility.  Default to a smaller
  mtu, for vmware compatibility. (dkilpatrick@verisign.com)
- in.tftpd needs to be run as root.  Whoops (dkilpatrick@verisign.com)
- Handle exceptions in the idle-timer handling.  This could cause tftpd.py to
  never exit (dkilpatrick@verisign.com)
- Do a better job of handling things when a logger doesn't exist. And don't try
  and find out what the FD is for logging purposes when I know that might throw
  and I won't catch it. (dkilpatrick@verisign.com)
- Scott Henson pointed out that my earlier changes stopped a sync from also
  copying kernel/initrd files into the web directry.  Split out the targets
  from the copy, and make sure that sync still copies to webdir, and then also
  fixed where I wasn't copying those files in the synclite case.
  (dkilpatrick@verisign.com)
- Put back code that I removed incorrectly. (sync DHCP, DNS)
  (dkilpatrick@verisign.com)
- Support installing FreeBSD without an IP address set in the host record.
  (dkilpatrick@verisign.com)
- Fixed some bugs in the special-case handling code, where I was not properly
  handling kernel requests, because I'd merged some code that looked alike, but
  couldn't actually be merged. (dkilpatrick@verisign.com)
- fixing koan to use cobblers version of os_release which works with RHEL 6
  (jsherril@redhat.com)
- Adding preliminary support for importing ESXi for PXE booting (jimi@sngx.net)
- Fix cobbler check tftp typo. (dgoodwin@rm-rf.ca)
- buildiso now builds iso's that include the http_port setting (in
  /etc/cobbler/settings) in the kickstart file url
  (maarten.dirkse@filterworks.com)
- Add check detection for missing ksvalidator (dean.wilson@gmail.com)
- Use shlex.split() to properly handle a quoted install URL (e.g. url
  --url="http://example.org") (jlaska@redhat.com)
- Update codes.py to accept 'fedora14' as a valid --os-version
  (jlaska@redhat.com)
- No more self (shenson@redhat.com)
- Don't die if a single repo fails to sync. (shenson@redhat.com)
- Refactor: depluralize madhatter branch (kelsey.hightower@gmail.com)
- Updating setup.py and spec file. (kelsey.hightower@gmail.com)
- New unit tests: Mgmtclasses (kelsey.hightower@gmail.com)
- Updating cobbler/koan man pages with info on using the new configuration
  management capabilities (kelsey.hightower@gmail.com)
- Cobbler web integration for new configuration management capabilities
  (kelsey.hightower@gmail.com)
- Koan configuration management enhancements (kelsey.hightower@gmail.com)
- Cobbler configuration management enhancements (kelsey.hightower@gmail.com)
- New cobbler objects: mgmtclasses, packages, and files.
  (kelsey.hightower@gmail.com)
- Merge remote branch 'jsabo/kickstart_done' (shenson@redhat.com)
- Move kickstart_done and kickstart_start out of kickgen.py and into their own
  snippets. This also adds support for VMware ESX triggers and magic urls by
  checking for the "vmware" breed and then using curl when that's all thats
  available vs wget.  VMware's installer makes wget available during the %pre
  section but only curl is around following install at %post time.  Yay!  I've
  also updated the sample kickstarts to use $SNIPPET('kickstart_done') and
  $SNIPPET('kickstart_start') (jonathan.sabo@gmail.com)
- No more getting confused between otype and obj_type (shenson@redhat.com)
- The clean_link_cache method was calling subprocess_call without a logger
  (shenson@redhat.com)
- Scott Henson pointed out that my earlier changes stopped a sync from also
  copying kernel/initrd files into the web directry.  Split out the targets
  from the copy, and make sure that sync still copies to webdir, and then also
  fixed where I wasn't copying those files in the synclite case.
  (dkilpatrick@verisign.com)
- revert bad templates path (dkilpatrick@verisign.com)
- Put back code that I removed incorrectly. (sync DHCP, DNS)
  (dkilpatrick@verisign.com)
- Support installing FreeBSD without an IP address set in the host record.
  (dkilpatrick@verisign.com)
- Fixed some bugs in the special-case handling code, where I was not properly
  handling kernel requests, because I'd merged some code that looked alike, but
  couldn't actually be merged. (dkilpatrick@verisign.com)
- Two more fixes to bugs introduced by pytftpd patch set: * The generated
  configs did not have initrd set propertly * Some extra debugging log lines
  made it into remote.py (dkilpatrick@verisign.com)
- Fix Trac#530 by properly handling a logger being none. Additionally, make
  subprocess_call and subprocess_get use common bits to reduce duplication.
  (shenson@redhat.com)
- Fix a cobbler_web authentication leak issue.  There are times when the token
  that cobbelr_web had did not match the user logged in.  This patch ensures
  that the token always matches the user that is logged in.
  (shenson@redhat.com)
- No more getting confused between otype and obj_type (shenson@redhat.com)
- The clean_link_cache method was calling subprocess_call without a logger
  (shenson@redhat.com)
- Merge remote branch 'kilpatds/master' (shenson@redhat.com)
- Scott Henson pointed out that my earlier changes stopped a sync from also
  copying kernel/initrd files into the web directry.  Split out the targets
  from the copy, and make sure that sync still copies to webdir, and then also
  fixed where I wasn't copying those files in the synclite case.
  (dkilpatrick@verisign.com)
- revert bad templates path (dkilpatrick@verisign.com)
- Put back code that I removed incorrectly. (sync DHCP, DNS)
  (dkilpatrick@verisign.com)
- Support installing FreeBSD without an IP address set in the host record.
  (dkilpatrick@verisign.com)
- Fixed some bugs in the special-case handling code, where I was not properly
  handling kernel requests, because I'd merged some code that looked alike, but
  couldn't actually be merged. (dkilpatrick@verisign.com)
- Two more fixes to bugs introduced by pytftpd patch set: * The generated
  configs did not have initrd set propertly * Some extra debugging log lines
  made it into remote.py (dkilpatrick@verisign.com)
- fast sync.  A new way of copying files around using a link cache.  It creates
  a link cache per device and uses it as an intermediary so that files that are
  the same are not copied multiple times.  Should greatly speed up sync times.
  (shenson@redhat.com)
- A few small fixes and a new feature for the Python tftp server * Support
  environments where the MAC address is know, but the IP address   is not
  (private networks).  I do this by waiting for pxelinux.0 to   request a file
  with the mac address added to the filename, and then   look up the host by
  MAC. * Fix my MAC lookup logic.  I didn't know to look for the ARP type (01-,
  at least for ethernet) added by pxelinux.0 * Fix up some log lines to make
  more sense * Fix a bug where I didn't get handle an empty fetchable_files
  properly, and didn't fall back to checking for profile matches.
  (dkilpatrick@verisign.com)
- Two fixed to bad changes in my prior patch set.  Sorry about that. * Bad path
  in cobbler/action_sync.py.  No "templates" * Bad generation of the default
  boot menu.  The first initrd from a profile   was getting into the metadata
  cache and hanging around, thus becoming the   initrd for all labels.
  (dkilpatrick@verisign.com)
- A smart tftp server, and a module to manage it
  (dkilpatr@dkilpatr.verisign.com)
- Export the generated pxelinux.cfg file via the materialized system
  information RPC method.  This enables the python tftpd server below to serve
  that file up without any sync being required.
  (dkilpatr@dkilpatr.verisign.com)
- Move management of /tftpboot into modules.  This is a setup step for a later
  python tftpd server that will eliminate the need for much of this work.
  (dkilpatr@dkilpatr.verisign.com)
- Fetchable Files attribute:   Provides a new attribute similar in spirit to
  mgmt_files, but   with somewhat reversed meaning.
  (dkilpatr@dkilpatr.verisign.com)
- fix log rotation to actually work (bpeck@redhat.com)
- find_kernel and find_initrd already do the right checks for file_is_remote
  and return None if things are wrong. (bpeck@redhat.com)
- Trac #588 Add mercurial support for scm tracking (kelsey.hightower@gmail.com)
- Add a breed for scientific linux (shenson@redhat.com)
- "mgmt_parameters" for item_profile has the wrong default setting when
  creating a sub_profile. I'm assuming that <<inherit>> would be correct for a
  sub_profile as well. (bpeck@redhat.com)
- The new setup.py placed webui_content in the wrong spot...
  (akesling@redhat.com)
- Merge commit 'a81ca9a4c18f17f5f8d645abf03c0e525cd234e1' (jeckersb@redhat.com)
- Added back in old-style version tracking... because api.py needs it.
  (akesling@redhat.com)
- Wrap the cobbler-web description (shenson@redhat.com)
- Create the tftpboot directory during install (shenson@redhat.com)
- Add in /var/lib/cobbler/loaders (shenson@redhat.com)
- Create the images directory so that selinux will be happy
  (shenson@redhat.com)
- Dont install some things in the webroot and put the services script down
  (shenson@redhat.com)
- Fix some issues with clean installs of cobbler post build cleanup
  (shenson@redhat.com)
- rhel5 doesn't build egg-info by default. (bpeck@redhat.com)
- Some systems don't reboot properly at the end of install. s390 being one of
  them. This post module will call power reboot if postreboot is in ks_meta for
  that system. (bpeck@redhat.com)
- Changes to allow s390 to work. s390 has a hard limit on the number of chars
  it can recieve. (bpeck@redhat.com)
- show netboot status via koan. This is really handy if you have a system which
  fails to pxe boot you can create a service in rc.local which checks the
  status of netboot and calls --replace-self for example. (bpeck@redhat.com)
- When adding in distros/profiles from disk don't bomb out if missing kernel or
  ramdisk. just don't add it. (bpeck@redhat.com)
- add X log to anamon tracking as well. (bpeck@redhat.com)
- Added new remote method clear_logs. Clearing console and anamon logs in %pre
  is too late if the install never happens. (bpeck@redhat.com)
- fixes /var/www/cobbler/svc/services.py to canonicalize the uri before parsing
  it. This fixes a regression with mod_wsgi enabled and trying to provision a
  rhel3 machine. (bpeck@redhat.com)
- anaconda umounts /proc on us while were still running. Deal with it.
  (bpeck@redhat.com)
- fix escape (bpeck@redhat.com)
- dont lowercase power type (bpeck@redhat.com)
- Bump to 2.1.0 (shenson@redhat.com)
- Properly detect unknown distributions (shenson@redhat.com)
- cobblerd service: Required-Start: network -> $network
  (cristian.ciupitu@yahoo.com)
- cobblerd service: add Default-Stop to LSB header (cristian.ciupitu@yahoo.com)
- No more . on the end (shenson@redhat.com)
- Do not delete settings and modules.conf (shenson@redhat.com)
- Remove manpage generation from the make file (shenson@redhat.com)
- Update the author and author email (shenson@redhat.com)
- Proper ownership on some files (shenson@redhat.com)
- More rpm cleanups (shenson@redhat.com)
- Don't have the #! because rpm complains (shenson@redhat.com)
- No more selinux here, we should not be calling chcon, things will end up with
  the proper context in a well configured selinux environment
  (shenson@redhat.com)
- No more chowning the log file. (shenson@redhat.com)
- A new spec file to go with the new setup.py (shenson@redhat.com)
- Forgot to add aux to MANIFEST.in (akesling@redhat.com)
- Fixed naming scheme for web UI to make it more uniform, what was Puppet
  Parameters is now Management Parameters. (akesling@redhat.com)
- Removed unnecessary cruft. (akesling@redhat.com)
- Reconfigured setup.py to now place config files and web ui content in the
  right places.  The paths are configurable like they were in the previous
  setup.py, but everything is much cleaner. (akesling@redhat.com)
- Removed unnecessary templating functionality from configuration generation
  (and setup.py) (akesling@redhat.com)
- Added more useful files to setup.py and MANIFEST.in as well as extra
  functionality which setup.py should contain. (akesling@redhat.com)
- Massive overhaul of setup.py .  Moved things around a little to clean up
  building/packaging/distributing.  The new setup.py is still incomplete.
  (akesling@redhat.com)
- RPM specific changes to setup.cfg. (akesling@redhat.com)
- Currently working through making setup.py functional for generating rpms
  dynamically.  setup.py is just cobbler-web at the moment... and it appears to
  work.  The next things to do are test the current RPM and add in
  functionality for reducing repetitive setup.py configuration lines.
  (akesling@redhat.com)
- Changed list-view edit link from a javascript onclick event to an actual
  link... so that you can now just open it in a new tab. (akesling@redhat.com)
- Added tip for random MAC Address functionality to System MAC Address field.
  (akesling@redhat.com)
- Added "Puppet Parameters" attribute to Profile and System items. The new
  input field is a textarea which takes proper a YAML formatted dictionary.
  This data is used for the Puppet External Nodes api call (found in
  services.py). (akesling@croissant.usersys.redhat.com)
- Resume apitesting assuming against local Cobbler server. (dgoodwin@rm-rf.ca)
- Replace rogue tab with whitespace. (dgoodwin@rm-rf.ca)
- Open all log files in append mode.  Tasks should not be special.  This
  simplifies the handling of logging for selinux. (shenson@redhat.com)
- Add rendered dir to cobbler.spec. (dgoodwin@rm-rf.ca)
- Re-add mod_python dep only for cobbler-web. (dgoodwin@rm-rf.ca)
- initializing variable that is not always initialized but is always accessed
  (jsherril@redhat.com)
- Merge remote branch 'pvreman/master' (shenson@redhat.com)
- add logging of triggers (peter.vreman@acision.com)
- add logging of triggers (peter.vreman@acision.com)
- cobbler-ext-nodes needs also to use http_port (peter.vreman@acision.com)
- Adding VMware ESX specific boot options (jonathan.sabo@gmail.com)
- Merge stable into master (shenson@redhat.com)
- Fix cobbler_web authentication in a way that doesn't break previously working
  stuff (shenson@redhat.com)
- Allow qemu disk type to be specified. Contributed by Galia Lisovskaya
  (shenson@redhat.com)
- Merge remote branch 'jsabo/esx' (shenson@redhat.com)
- Fix a bug where we were not looking for the syslinux provided menu.c32 before
  going after the getloaders one (shenson@redhat.com)
- Fix cobbler_web authentication in a way that doesn't break previously working
  stuff (shenson@redhat.com)
- More preparation for the release (shenson@redhat.com)
- Update spec file for release (shenson@redhat.com)
- Update changelog for release (shenson@redhat.com)
- Bugfix: fetch extra metadata from upstream repositories more safely
  (icomfort@stanford.edu)
- Bugfix: allow the creation of subprofiles again (icomfort@stanford.edu)
- Don't warn needlessly when repo rpm_list is empty (icomfort@stanford.edu)
- Bugfix: run createrepo on partial yum mirrors (icomfort@stanford.edu)
- Change default mode for new directories from 0777 to 0755
  (icomfort@stanford.edu)
- Fix replication when prune is specified and no systems are specified. This
  prevents us from killing systems on a slave that keeps its own systems. To
  get the old behavior, just specify a systems list that won't match anything.
  (shenson@redhat.com)
- Always authorize the CLI (shenson@redhat.com)
- Bugfix: fetch extra metadata from upstream repositories more safely
  (icomfort@stanford.edu)
- Bugfix: allow the creation of subprofiles again (icomfort@stanford.edu)
- Don't warn needlessly when repo rpm_list is empty (icomfort@stanford.edu)
- Bugfix: run createrepo on partial yum mirrors (icomfort@stanford.edu)
- Change default mode for new directories from 0777 to 0755
  (icomfort@stanford.edu)
- Fix replication when prune is specified and no systems are specified. This
  prevents us from killing systems on a slave that keeps its own systems. To
  get the old behavior, just specify a systems list that won't match anything.
  (shenson@redhat.com)
- Always authorize the CLI (shenson@redhat.com)
- Merge branch 'wsgi' (dgoodwin@rm-rf.ca)
- Adding VMware ESX 4 update 1 support (jonathan.sabo@gmail.com)
- remove references to apt support from the man page (jeckersb@redhat.com)
- wsgi: Service cleanup. (dgoodwin@rm-rf.ca)
- wsgi: Revert to old error handling. (dgoodwin@rm-rf.ca)
- wsgi: Switch Cobbler packaging/config from mod_python to mod_wsgi. (dgoodwin
  @rm-rf.ca)
- wsgi: Return 404 when hitting svc URLs for missing objects. (dgoodwin@rm-
  rf.ca)
- Merge branch 'master' into wsgi (dgoodwin@rm-rf.ca)
- wsgi: First cut of port to mod_wsgi. (dgoodwin@rm-rf.ca)

* Thu Jun 17 2010 Scott Henson <shenson@redhat.com> - 2.1.0-1
- Bump upstream release

* Tue Apr 27 2010 Scott Henson <shenson@redhat.com> - 2.0.4-1
- Bug fix release, see Changelog for details

* Thu Apr 15 2010 Devan Goodwin <dgoodwin@rm-rf.ca> 2.0.3.2-1
- Tagging for new build tools.

* Mon Mar  1 2010 Scott Henson <shenson@redhat.com> - 2.0.3.1-3
- Bump release because I forgot cobbler-web

* Mon Mar  1 2010 Scott Henson <shenson@redhat.com> - 2.0.3.1-2
- Remove requires on mkinitrd as it is not used

* Mon Feb 15 2010 Scott Henson <shenson@redhat.com> - 2.0.3.1-1
- Upstream Brown Paper Bag Release (see CHANGELOG)

* Thu Feb 11 2010 Scott Henson <shenson@redhat.com> - 2.0.3-1
- Upstream changes (see CHANGELOG)

* Mon Nov 23 2009 John Eckersberg <jeckersb@redhat.com> - 2.0.2-1
- Upstream changes (see CHANGELOG)

* Tue Sep 15 2009 Michael DeHaan <michael.dehaan AT gmail> - 2.0.0-1
- First release with unified spec files
