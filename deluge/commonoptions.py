#
# optionmanager.py
#
# Copyright (C) 2007 Andrew Resch <andrewresch@gmail.com>
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

import optparse
import sys
import logging
import deluge.common
import deluge.log 
import deluge.configmanager


class CommonOptionParser(optparse.OptionParser): 
    def __init__(self, *args, **kwargs): 
        
        if 'version' not in kwargs: 
            try:
                from deluge._libtorrent import lt
                lt_version = "\nlibtorrent: %s" % lt.version
            except ImportError:
                lt_version = ""
            finally:
                kwargs['version'] = "%prog: " + deluge.common.get_version() + lt_version

        optparse.OptionParser.__init__(self, *args, **kwargs)

        self.common_group = optparse.OptionGroup(self, _("Common Options"))
        self.common_group.add_option("-c", "--config", dest="config",
            help="Set the config folder location", action="store", type="str")
        self.common_group.add_option("-l", "--logfile", dest="logfile",
            help="Output to designated logfile instead of stdout", action="store", type="str")
        self.common_group.add_option("-L", "--loglevel", dest="loglevel",
            help="Set the log level: none, info, warning, error, critical, debug", action="store", type="str")
        self.common_group.add_option("-q", "--quiet", dest="quiet",
            help="Sets the log level to 'none', this is the same as `-L none`", action="store_true", default=False)
        self.common_group.add_option("-r", "--rotate-logs",
            help="Rotate logfiles.", action="store_true", default=False)

        self.add_option_group(self.common_group)

    def parse_args(self, *args):
        options, args = optparse.OptionParser.parse_args(self, *args)

        if options.quiet:
            options.loglevel = "none"

        logfile_mode = 'a' if options.rotate_logs else 'w' 

        # Setup the logger
        deluge.log.setupLogger(level=options.loglevel,
                               filename=options.logfile,
                               filemode=logfile_mode)

        if options.config:
            if not deluge.configmanager.set_config_dir(options.config):
                log = logging.getLogger(__name__)
                log.error("There was an error setting the config dir! Exiting..")
                sys.exit(1)

        return options, args
