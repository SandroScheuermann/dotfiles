#!/usr/bin/env python3

import gi
import subprocess

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk


def current_brightness():
    output = subprocess.check_output(["brightnessctl", "-m"], text=True)
    return int(output.split(",")[3].strip("%"))


def set_brightness(value):
    subprocess.Popen(["brightnessctl", "set", f"{int(value)}%"])


class BrightnessSlider(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_resizable(False)
        self.set_app_paintable(True)
        self.set_border_width(14)

        css = b"""
        window {
          background: rgba(20, 20, 24, 0.94);
          border-radius: 14px;
          border: 1px solid rgba(255, 255, 255, 0.18);
        }
        scale trough {
          min-height: 10px;
          border-radius: 999px;
          background: rgba(255, 255, 255, 0.18);
        }
        scale highlight {
          border-radius: 999px;
          background: #7aa2ff;
        }
        scale slider {
          min-width: 20px;
          min-height: 20px;
          border-radius: 999px;
          background: #ffffff;
          box-shadow: 0 0 16px rgba(122, 162, 255, 0.65);
        }
        label {
          color: #ffffff;
          font-weight: 700;
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        icon = Gtk.Label(label="󰃠")
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 100, 1)
        scale.set_size_request(260, 36)
        scale.set_draw_value(False)
        scale.set_value(current_brightness())
        scale.connect("value-changed", lambda widget: set_brightness(widget.get_value()))

        box.pack_start(icon, False, False, 0)
        box.pack_start(scale, True, True, 0)
        self.add(box)

        display = Gdk.Display.get_default()
        seat = display.get_default_seat()
        pointer = seat.get_pointer()
        _, x, y = pointer.get_position()
        self.move(max(0, x - 170), max(0, y + 12))

        self.connect("focus-out-event", lambda *_: Gtk.main_quit())
        self.connect("key-press-event", lambda *_: Gtk.main_quit())


window = BrightnessSlider()
window.show_all()
Gtk.main()
