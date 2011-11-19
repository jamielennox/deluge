from deluge.ui.ui import _UI

class Gtk(_UI):

    help = """Starts the Deluge GTK+ interface"""
    cmdline = """A GTK-based graphical user interface"""

    def __init__(self, *args, **kwargs):
        super(Gtk, self).__init__("gtk", *args, **kwargs)

    def start(self, args = None):
        from gtkui import GtkUI
        super(Gtk, self).start(args)
        GtkUI(self.args)

def start():
    Gtk().start()
