#
# main.py
#
# Copyright (C) 2008-2009 Ido Abramovich <ido.deluge@gmail.com>
# Copyright (C) 2009 Andrew Resch <andrewresch@gmail.com>
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

import sys
import logging
import optparse
import shlex
import locale

from twisted.internet import defer, reactor

import deluge.component as component
from deluge.ui.client import client
import deluge.common
from deluge.ui.coreconfig import CoreConfig
from deluge.ui.sessionproxy import SessionProxy
from deluge.ui.console.statusbars import StatusBars
from deluge.ui.console.eventlog import EventLog
import colors

log = logging.getLogger(__name__)

class OptionParser(optparse.OptionParser):
    """subclass from optparse.OptionParser so exit() won't exit."""
    def exit(self, status=0, msg=None):
        self.values._exit = True
        if msg:
            print msg

    def error(self, msg):
        """error(msg : string)

           Print a usage message incorporating 'msg' to stderr and exit.
           If you override this in a subclass, it should not return -- it
           should either exit or raise an exception.
        """
        raise Exception(msg)


class BaseCommand(object):

    usage = 'usage'
    interactive_only = False
    option_list = tuple()
    aliases = []

    def complete(self, text, *args):
        return []
    def handle(self, *args, **options):
        pass

    @property
    def name(self):
        return 'base'

    @property
    def epilog(self):
        return self.__doc__

    def split(self, text):
        if deluge.common.windows_check():
            text = text.replace('\\', '\\\\')
        return shlex.split(text)

    def create_parser(self):
        return OptionParser(prog = self.name,
                            usage = self.usage,
                            epilog = self.epilog,
                            option_list = self.option_list)


class ConsoleUI(component.Component):
    def __init__(self, args=None, cmds = None, daemon = None):
        component.Component.__init__(self, "ConsoleUI", 2)

        # keep track of events for the log view
        self.events = []

        try:
            locale.setlocale(locale.LC_ALL, '')
            self.encoding = locale.getpreferredencoding()
        except:
            self.encoding = sys.getdefaultencoding()

        log.debug("Using encoding: %s", self.encoding)


        # start up the session proxy
        self.sessionproxy = SessionProxy()

        client.set_disconnect_callback(self.on_client_disconnect)

        # Set the interactive flag to indicate where we should print the output
        self.interactive = True
        self._commands = cmds
        if args:
            args = args[0]
            self.interactive = False
            if not cmds:
                print "Sorry, couldn't find any commands"
                return
            else:
                from commander import Commander
                cmdr = Commander(cmds)
                if daemon:
                    cmdr.exec_args(args,*daemon)
                else:
                    cmdr.exec_args(args,None,None,None,None)
                

        self.coreconfig = CoreConfig()
        if self.interactive and not deluge.common.windows_check():
            # We use the curses.wrapper function to prevent the console from getting
            # messed up if an uncaught exception is experienced.
            import curses.wrapper
            curses.wrapper(self.run)
        elif self.interactive and deluge.common.windows_check():
            print """\nDeluge-console does not run in interactive mode on Windows. \n
Please use commands from the command line, eg:\n
    deluge-console.exe help
    deluge-console.exe info
    deluge-console.exe "add --help"
    deluge-console.exe "add -p c:\\mytorrents c:\\new.torrent"
            """
        else:
            reactor.run()

    def run(self, stdscr):
        """
        This method is called by the curses.wrapper to start the mainloop and
        screen.

        :param stdscr: curses screen passed in from curses.wrapper

        """
        # We want to do an interactive session, so start up the curses screen and
        # pass it the function that handles commands
        colors.init_colors()
        self.statusbars = StatusBars()
        from modes.connectionmanager import ConnectionManager
        self.stdscr = stdscr
        self.screen = ConnectionManager(stdscr, self.encoding)
        self.eventlog = EventLog()

        self.screen.topbar = "{!status!}Deluge " + deluge.common.get_version() + " Console"
        self.screen.bottombar = "{!status!}"
        self.screen.refresh()

        # The Screen object is designed to run as a twisted reader so that it
        # can use twisted's select poll for non-blocking user input.
        reactor.addReader(self.screen)

        # Start the twisted mainloop
        reactor.run()


    def start(self):
        # Maintain a list of (torrent_id, name) for use in tab completion
        self.torrents = []
        if not self.interactive:
            self.started_deferred = defer.Deferred()
            def on_session_state(result):
                def on_torrents_status(torrents):
                    for torrent_id, status in torrents.items():
                        self.torrents.append((torrent_id, status["name"]))
                    self.started_deferred.callback(True)

                client.core.get_torrents_status({"id": result}, ["name"]).addCallback(on_torrents_status)
            client.core.get_session_state().addCallback(on_session_state)

            
    def match_torrent(self, string):
        """
        Returns a list of torrent_id matches for the string.  It will search both
        torrent_ids and torrent names, but will only return torrent_ids.

        :param string: str, the string to match on

        :returns: list of matching torrent_ids. Will return an empty list if
            no matches are found.

        """
        if self.interactive and isinstance(self.screen,deluge.ui.console.modes.legacy.Legacy):
            return self.screen.match_torrent(string)
        ret = []
        for tid, name in self.torrents:
            if tid.startswith(string) or name.startswith(string):
                ret.append(tid)

        return ret


    def get_torrent_name(self, torrent_id):
        if self.interactive and hasattr(self.screen,"get_torrent_name"):
            return self.screen.get_torrent_name(torrent_id)

        for tid, name in self.torrents:
            if torrent_id == tid:
                return name
        
        return None


    def set_batch_write(self, batch):
        if self.interactive and isinstance(self.screen,deluge.ui.console.modes.legacy.Legacy):
            return self.screen.set_batch_write(batch)

    def tab_complete_torrent(self, line):
        if self.interactive and isinstance(self.screen,deluge.ui.console.modes.legacy.Legacy):
            return self.screen.tab_complete_torrent(line)

    def set_mode(self, mode):
        reactor.removeReader(self.screen)
        self.screen = mode
        self.statusbars.screen = self.screen
        reactor.addReader(self.screen)

    def on_client_disconnect(self):
        component.stop()

    def write(self, s):
        if self.interactive:
            if isinstance(self.screen,deluge.ui.console.modes.legacy.Legacy):
                self.screen.write(s)
            else:
                self.events.append(s)
        else:
            print colors.strip_colors(s.encode(self.encoding))
