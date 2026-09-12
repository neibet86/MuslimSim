"""Shared MuslimSim dropdown colours, applied once per application root."""
from tkinter import ttk

BLUE = "#5aa9ff"

def apply_dropdown_theme(root, background="#212936"):
    style = ttk.Style(root)
    style.configure("TCombobox", foreground=BLUE, arrowcolor=BLUE,
                    fieldbackground=background, background=background,
                    selectforeground=BLUE, selectbackground="#29486e")
    style.map("TCombobox",
              foreground=[("disabled", "#7198c4"), ("!disabled", BLUE)],
              fieldbackground=[("disabled", background), ("readonly", background)],
              selectforeground=[("!disabled", BLUE)],
              selectbackground=[("!disabled", "#29486e")])
    style.configure("TMenubutton", foreground=BLUE)
    style.map("TMenubutton", foreground=[("disabled", "#7198c4"), ("!disabled", BLUE)])
    # The opened ttk list is a Tk Listbox, not part of the ttk style.
    for option, value in {"foreground": BLUE, "background": background,
                          "selectForeground": BLUE, "selectBackground": "#29486e"}.items():
        root.option_add("*TCombobox*Listbox." + option, value)
    for option, value in {"foreground": BLUE, "activeForeground": BLUE,
                          "disabledForeground": "#7198c4", "background": background,
                          "activeBackground": "#29486e"}.items():
        root.option_add("*Menu." + option, value)
