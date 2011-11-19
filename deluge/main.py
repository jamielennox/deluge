#
# main.py
#
# Copyright (C) 2007 Andrew Resch <andrewresch@gmail.com>
# Copyright (C) 2010 Pedro Algarvio <pedro@algarvio.me>
#
# Deluge is free software.
#
# You may redistribute it and/or modify it under the terms of the
# GNU General Public License, as published by the Free Software
# Foundation; either version 3 of the License, or (at your option)
# any later version.
#
# deluge is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with deluge.    If not, write to:
# 	The Free Software Foundation, Inc.,
# 	51 Franklin Street, Fifth Floor
# 	Boston, MA  02110-1301, USA.
#
#    In addition, as a special exception, the copyright holders give
#    permission to link the code of portions of this program with the OpenSSL
#    library.
#    You must obey the GNU General Public License in all respects for all of
#    the code used other than OpenSSL. If you modify file(s) with this
#    exception, you may extend this exception to your version of the file(s),
#    but you are not obligated to do so. If you do not wish to do so, delete
#    this exception statement from your version. If you delete this exception
#    statement from all source files in the program, then also delete it here.
#
#


# The main starting point for the program.    This function is called when the
# user runs the command 'deluge'.

"""Main starting point for Deluge.  Contains the main() entry point."""

import os
import sys
import optparse
import logging

import deluge.log
import deluge.error
from deluge.commonoptions import CommonOptionParser

DEFAULT_PREFS = {
    "default_ui": "gtk"
}

def start_ui():
    """Entry point for ui script"""
    import deluge.common
    deluge.common.setup_translations()

    # Setup the argument parser
    parser = CommonOptionParser()
    group = optparse.OptionGroup (parser, _("Default Options"))

    group.add_option("-u", "--ui", dest="ui",
        help="""The UI that you wish to launch.  The UI choices are:\n
        \t gtk -- A GTK-based graphical user interface (default)\n
        \t web -- A web-based interface (http://localhost:8112)\n
        \t console -- A console or command-line interface""", action="store", type="str")
    group.add_option("-a", "--args", dest="args",
        help="Arguments to pass to UI, -a '--option args'", action="store", type="str")
    group.add_option("-s", "--set-default-ui", dest="default_ui",
        help="Sets the default UI to be run when no UI is specified", action="store", type="str")
    
    parser.add_option_group(group)

    # Get the options and args from the OptionParser
    (options, args) = parser.parse_args()

    config = deluge.configmanager.ConfigManager("ui.conf", DEFAULT_PREFS)

    if options.default_ui:
        config["default_ui"] = options.default_ui
        config.save()
        print "The default UI has been changed to", options.default_ui
        sys.exit(0)

    version = deluge.common.get_version()

    log = logging.getLogger(__name__)
    log.info("Deluge ui %s", version)
    log.debug("options: %s", options)
    log.debug("args: %s", args)
    log.debug("ui_args: %s", args)

    selected_ui = options.ui if options.ui else config["default_ui"]

    config.save()
    del config

    # reconstruct arguments to hand off to child client
    client_args = [] 
    if options.args: 
        import shlex
        client_args.extend(shlex.split(options.args))
    client_args.extend(args)

    try:
        if selected_ui == "gtk":
            log.info("Starting GtkUI..")
            from deluge.ui.gtkui.gtkui import Gtk
            ui = Gtk(skip_common = True)
            ui.start(client_args)
        elif selected_ui == "web":
            log.info("Starting WebUI..")
            from deluge.ui.web.web import Web
            ui = Web(skip_common = True)
            ui.start(client_args)
        elif selected_ui == "console":
            log.info("Starting ConsoleUI..")
            from deluge.ui.console.main import Console
            ui = Console(skip_common = True)
            ui.start(client_args)
    except ImportError, e:
        import sys
        import traceback
        error_type, error_value, tb = sys.exc_info()
        stack = traceback.extract_tb(tb)
        last_frame = stack[-1]
        if last_frame[0] == __file__:
            log.error("Unable to find the requested UI: %s.  Please select a different UI with the '-u' option or alternatively use the '-s' option to select a different default UI.", selected_ui)
        else:
            log.exception(e)
            log.error("There was an error whilst launching the request UI: %s", selected_ui)
            log.error("Look at the traceback above for more information.")
        sys.exit(1)

def start_daemon():
    """Entry point for daemon script"""
    import deluge.common
    deluge.common.setup_translations()

    if 'dev' not in deluge.common.get_version():
        import warnings
        warnings.filterwarnings('ignore', category=DeprecationWarning, module='twisted')

    # Setup the argument parser
    parser = CommonOptionParser(usage="%prog [options] [actions]")

    group = optparse.OptionGroup (parser, _("Daemon Options"))
    group.add_option("-p", "--port", dest="port",
        help="Port daemon will listen on", action="store", type="int")
    group.add_option("-i", "--interface", dest="interface",
        help="Interface daemon will listen for bittorrent connections on, \
this should be an IP address", metavar="IFACE",
        action="store", type="str")
    group.add_option("-u", "--ui-interface", dest="ui_interface",
        help="Interface daemon will listen for UI connections on, this should be\
 an IP address", metavar="IFACE", action="store", type="str")
    if not (deluge.common.windows_check() or deluge.common.osx_check()):
        group.add_option("-d", "--do-not-daemonize", dest="donot",
            help="Do not daemonize", action="store_true", default=False)
    group.add_option("-P", "--pidfile", dest="pidfile",
        help="Use pidfile to store process id", action="store", type="str")
    if not deluge.common.windows_check():
        group.add_option("-U", "--user", dest="user",
            help="User to switch to. Only use it when starting as root", action="store", type="str")
        group.add_option("-g", "--group", dest="group",
            help="Group to switch to. Only use it when starting as root", action="store", type="str")
    group.add_option("--profile", dest="profile", action="store_true", default=False,
        help="Profiles the daemon")

    parser.add_option_group(group)

    # Get the options and args from the OptionParser
    (options, args) = parser.parse_args()

    # Sets the options.logfile to point to the default location
    def open_logfile():
        if not options.logfile:
            options.logfile = deluge.configmanager.get_config_dir("deluged.log")

    # Writes out a pidfile if necessary
    def write_pidfile():
        if options.pidfile:
            open(options.pidfile, "wb").write("%s\n" % os.getpid())

    # If the donot daemonize is set, then we just skip the forking
    if not (deluge.common.windows_check() or deluge.common.osx_check() or options.donot):
        if os.fork():
            # We've forked and this is now the parent process, so die!
            os._exit(0)
        os.setsid()
        # Do second fork
        if os.fork():
            os._exit(0)

    # Write pid file before chuid
    write_pidfile()

    if options.user:
        if not options.user.isdigit():
            import pwd
            options.user = pwd.getpwnam(options.user)[2]
        os.setuid(options.user)
    if options.group:
        if not options.group.isdigit():
            import grp
            options.group = grp.getgrnam(options.group)[2]
        os.setuid(options.group)

    open_logfile()

    # Setup the logger
    try:
        # Try to make the logfile's directory if it doesn't exist
        os.makedirs(os.path.abspath(os.path.dirname(options.logfile)))
    except:
        pass

    log = logging.getLogger(__name__)

    if options.profile:
        import hotshot
        hsp = hotshot.Profile(deluge.configmanager.get_config_dir("deluged.profile"))
        hsp.start()
    try:
        from deluge.core.daemon import Daemon
        Daemon(options, args)
    except deluge.error.DaemonRunningError, e:
        log.error(e)
        log.error("You cannot run multiple daemons with the same config directory set.")
        log.error("If you believe this is an error, you can force a start by deleting %s.", deluge.configmanager.get_config_dir("deluged.pid"))
        sys.exit(1)
    except Exception, e:
        log.exception(e)
        sys.exit(1)
    finally:
        if options.profile:
            hsp.stop()
            hsp.close()
            import hotshot.stats
            stats = hotshot.stats.load(deluge.configmanager.get_config_dir("deluged.profile"))
            stats.strip_dirs()
            stats.sort_stats("time", "calls")
            stats.print_stats(400)
