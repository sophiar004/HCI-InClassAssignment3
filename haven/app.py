"""Run with python3 -m haven.app. Tkinter is the only UI dependency."""

import argparse
import tkinter as tk
from datetime import datetime

from haven.model import Store, read_climate

BG = "#F3F5EF"
CARD = "#FFFFFF"
INK = "#183D3A"
MUTED = "#526762"
TEAL = "#176653"
PALE = "#DCEBE1"
AMBER = "#80500C"

TUTORIAL_STEPS = (
    ("Welcome to Haven",
     "Haven is a local home companion for daily routines and room awareness.\n\n"
     "Use the large buttons on the left to move between screens. You can open "
     "this tutorial again anytime with Help & guide."),
    ("Start on Home",
     "Home shows the current time, room temperature and humidity, and your next "
     "daily reminder.\n\n"
     "Look for Local sensor when the DHT22 is connected. Demo data means Haven "
     "is showing sample values. Sensor unavailable means the connection needs attention."),
    ("Use a reminder",
     "Open Reminders, then choose Mark as taken only after completing the task. "
     "Haven asks you to confirm and lets you undo mistakes.\n\n"
     "Choose In 10 minutes when you need more time."),
    ("Complete a check-in",
     "Open Check-in and choose the option closest to how you feel. Haven confirms "
     "your choice immediately.\n\n"
     "Check-ins are saved in Activity only when local activity logging is enabled."),
    ("Choose your privacy settings",
     "Open Settings to turn local activity history on or off and clear saved history. "
     "Haven keeps this prototype's data on the device.\n\n"
     "Haven does not call a caregiver or emergency service, and it cannot detect "
     "falls or stove hazards. Contact a trusted person when you need help."),
)


class Haven(tk.Tk):
    def __init__(self, fullscreen=False, store=None):
        super().__init__()
        # Keep the same physical pixel layout across desktop/Pi font DPI defaults.
        self.tk.call("tk", "scaling", 96 / 72)
        self.title("Haven | Your daily companion")
        self.geometry("800x480")
        self.minsize(800, 480)
        self.configure(bg=BG)
        self.attributes("-fullscreen", fullscreen)
        self.bind("<Escape>", lambda event: self.attributes("-fullscreen", False))
        self.bind("<F11>", lambda event: self.attributes("-fullscreen", not self.attributes("-fullscreen")))
        self.store = store or Store()
        self.page = "Home"
        self.dialog = None
        self.climate_labels = []
        self.nav_buttons = {}
        self.toast_job = None

        header = tk.Frame(self, bg=BG, height=64)
        header.pack(fill="x", padx=20)
        header.pack_propagate(False)
        self.label(header, "haven", 27, bold=True).pack(side="left")
        self.label(header, "YOUR DAILY COMPANION", 10, color=MUTED).pack(side="left", padx=16)
        self.clock = self.label(header, "", 14, bold=True)
        self.clock.pack(side="right")

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=16)
        nav = tk.Frame(body, bg=BG, width=138)
        nav.pack(side="left", fill="y", padx=(0, 16))
        nav.pack_propagate(False)
        for name in ("Home", "Reminders", "Check-in", "Activity", "Settings"):
            button = self.button(nav, name, lambda p=name: self.show(p), primary=False)
            button.pack(fill="x", pady=(0, 9))
            self.nav_buttons[name] = button
        self.button(nav, "Help & guide", self.guide, primary=False, font_size=12).pack(side="bottom", fill="x", pady=8)
        self.content = tk.Frame(body, bg=BG)
        self.content.pack(side="left", fill="both", expand=True)

        footer = tk.Frame(self, bg=BG, height=34)
        footer.pack(fill="x", padx=20)
        footer.pack_propagate(False)
        self.feedback = self.label(footer, "", 11, color=TEAL)
        self.feedback.pack(side="left")
        self.label(footer, "LOCAL ONLY  /  PROTOTYPE", 10, color=MUTED).pack(side="right")
        self.show("Home")
        self.tick()
        if self.store.notice:
            self.after(400, lambda: self.toast(self.store.notice))
        elif not self.store.state["onboarded"]:
            self.after(400, self.guide)

    def label(self, parent, text, size=15, bold=False, color=INK, **kwargs):
        return tk.Label(parent, text=text, font=("DejaVu Sans", size, "bold" if bold else "normal"),
                        bg=parent.cget("bg"), fg=color, anchor="w", justify="left", **kwargs)

    def button(self, parent, text, command, primary=True, font_size=14):
        # A real Button supplies keyboard focus, Space/Return activation, and pressed feedback.
        button = tk.Button(parent, text=text, command=command,
                           font=("DejaVu Sans", font_size, "bold"), bg=TEAL if primary else PALE,
                           fg="white" if primary else INK, activebackground=INK,
                           activeforeground="white", relief="flat", bd=0, padx=8, pady=13,
                           highlightthickness=2, highlightbackground=BG, highlightcolor=AMBER,
                           cursor="hand2", takefocus=True)
        button.bind("<Return>", lambda event: button.invoke())
        return button

    def show(self, page):
        self.page = page
        self.climate_labels = []
        for widget in self.content.winfo_children():
            widget.destroy()
        for name, button in self.nav_buttons.items():
            button.configure(bg=INK if page == name else PALE, fg="white" if page == name else INK)
        {"Home": self.home, "Reminders": self.reminders, "Check-in": self.check_in,
         "Activity": self.activity, "Settings": self.settings}[page]()

    def title_block(self, title, subtitle):
        self.label(self.content, title, 25, True).pack(anchor="w", pady=(2, 2))
        self.label(self.content, subtitle, 12, color=MUTED).pack(anchor="w", pady=(0, 12))

    def card(self, parent):
        return tk.Frame(parent, bg=CARD, padx=16, pady=12)

    def home(self):
        hour = datetime.now().hour
        greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
        self.title_block(greeting + ".", "A little support for your everyday routine.")
        row = tk.Frame(self.content, bg=BG)
        row.pack(fill="both", expand=True)
        row.columnconfigure((0, 1), weight=1, uniform="cards")
        row.rowconfigure(0, weight=1)
        room = self.card(row)
        room.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.label(room, "YOUR ROOM", 11, True, MUTED).pack(anchor="w")
        source = self.label(room, "", 12, color=MUTED)
        source.pack(anchor="w", pady=(4, 2))
        temp = self.label(room, "", 33, True)
        temp.pack(anchor="w", pady=(8, 0))
        humidity = self.label(room, "", 17)
        humidity.pack(anchor="w", pady=6)
        state = self.label(room, "", 12, wraplength=220)
        state.pack(anchor="w", pady=(4, 0))
        self.climate_labels = [source, temp, humidity, state]
        self.update_climate()
        reminder = self.card(row)
        reminder.grid(row=0, column=1, sticky="nsew")
        self.label(reminder, "DAILY REMINDER", 11, True, MUTED).pack(anchor="w")
        self.label(reminder, "Morning routine", 19, True).pack(anchor="w", pady=(12, 6))
        self.reminder_label = self.label(reminder, self.store.reminder_status(), 12, color=TEAL)
        self.reminder_label.pack(anchor="w")
        self.label(reminder, "Example medication reminder.\nFollow your own care plan.", 11, color=MUTED).pack(anchor="w", pady=10)
        self.button(reminder, "View reminder", lambda: self.show("Reminders")).pack(fill="x", side="bottom")
        self.button(self.content, "How are you feeling?   Start a check-in", lambda: self.show("Check-in"), primary=False).pack(fill="x", pady=(12, 0))

    def reminders(self):
        self.title_block("Your reminders", "One simple step at a time.")
        box = self.card(self.content)
        box.pack(fill="both", expand=True)
        self.label(box, "8:00 AM  /  DAILY EXAMPLE", 11, True, MUTED).pack(anchor="w")
        self.label(box, "Morning medication", 22, True).pack(anchor="w", pady=(10, 4))
        self.reminder_label = self.label(box, self.store.reminder_status(), 15, True, TEAL)
        self.reminder_label.pack(anchor="w")
        self.label(box, "Sample reminder only. Use the medicine and dose\nin your prescribed care plan.", 13, color=MUTED).pack(anchor="w", pady=12)
        buttons = tk.Frame(box, bg=CARD)
        buttons.pack(fill="x", side="bottom")
        if self.store.taken():
            self.button(buttons, "Undo completion", lambda: self.complete(False), primary=False).pack(fill="x")
        else:
            self.button(buttons, "Mark as taken", self.confirm_taken).pack(side="left", fill="x", expand=True, padx=(0, 8))
            self.button(buttons, "In 10 minutes", self.snooze, primary=False).pack(side="left", fill="x", expand=True)

    def check_in(self):
        self.title_block("How are you feeling?", "Choose what feels closest to you today.")
        for text in ("I'm feeling well", "I'm feeling okay", "I could use some support"):
            self.button(self.content, text, lambda value=text: self.record_checkin(value), primary=False).pack(fill="x", pady=(0, 10))
        self.label(self.content, "Check-ins stay on this device when activity logging is on.\nThis screen does not contact a caregiver or emergency service.", 11, color=MUTED).pack(anchor="w", pady=4)

    def record_checkin(self, value):
        self.store.log("Check-in: " + value)
        if self.persist():
            suffix = "Saved on this device." if self.store.state["logging"] else "Activity logging is off; this was not saved."
            self.popup("Thank you for checking in", suffix + ("\nContact someone you trust if you need support." if "support" in value else ""), [("Back to Home", lambda: self.show("Home"))])

    def activity(self):
        self.title_block("Recent activity", "Optional history, stored only on this device.")
        box = self.card(self.content)
        box.pack(fill="both", expand=True)
        if not self.store.state["events"]:
            self.label(box, "No saved activity yet", 19, True).pack(anchor="w", pady=12)
            self.label(box, "Turn on activity logging in Settings\nto keep check-ins and reminder actions.", 14, color=MUTED).pack(anchor="w")
            return
        text = tk.Text(box, bg=CARD, fg=INK, font=("DejaVu Sans", 13), wrap="word", relief="flat", borderwidth=0, highlightthickness=0, height=7)
        scrollbar = tk.Scrollbar(box, command=text.yview, width=24)
        scrollbar.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        text.configure(yscrollcommand=scrollbar.set)
        for event in self.store.state["events"]:
            if not isinstance(event, dict):
                continue
            text.insert("end", str(event.get("time", "")).replace("T", "  ") + "\n" + str(event.get("text", "")) + "\n\n")
        text.configure(state="disabled")

    def settings(self):
        self.title_block("Privacy & settings", "You decide what Haven remembers.")
        box = self.card(self.content)
        box.pack(fill="both", expand=True)
        self.label(box, "Camera & microphone: off", 17, True).pack(anchor="w")
        self.label(box, "No recording, cloud connection, or caregiver sharing.", 12, color=MUTED).pack(anchor="w", pady=(4, 12))
        self.button(box, "Activity logging: " + ("ON" if self.store.state["logging"] else "OFF"), self.toggle_logging, primary=False).pack(fill="x")
        self.label(box, "Reminder completion is saved so it survives a restart.\nTurning logging off keeps existing history until you clear it.", 11, color=MUTED).pack(anchor="w", pady=8)
        row = tk.Frame(box, bg=CARD)
        row.pack(fill="x", side="bottom")
        self.button(row, "Clear history", self.confirm_clear, primary=False, font_size=12).pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.button(row, "Exit Haven", self.destroy, primary=False, font_size=12).pack(side="left", fill="x", expand=True)

    def toggle_logging(self):
        self.store.state["logging"] = not self.store.state["logging"]
        if self.persist():
            self.show("Settings")
            self.toast("Activity logging " + ("enabled." if self.store.state["logging"] else "disabled."))

    def confirm_clear(self):
        self.popup("Clear activity history?", "This deletes saved activity on this device.\nToday's reminder completion will be kept.", [("Keep history", lambda: None), ("Clear history", self.clear_history)])

    def clear_history(self):
        self.store.state["events"] = []
        if self.persist():
            self.toast("Activity history cleared.")

    def confirm_taken(self):
        self.popup("Mark reminder as taken?", "Only confirm after you have taken your medication.\nYou can undo an accidental tap on the next screen.", [("Go back", lambda: None), ("Yes, mark taken", lambda: self.complete(True))])

    def complete(self, value):
        try:
            self.store.mark_taken(value)
        except OSError:
            self.storage_error()
            return
        self.show("Reminders")
        self.toast("Marked as taken. Undo is available." if value else "Completion undone.")

    def snooze(self):
        try:
            self.store.snooze()
        except OSError:
            self.storage_error()
            return
        self.show("Reminders")
        self.toast("Reminder moved ahead by 10 minutes.")

    def persist(self):
        try:
            self.store.save()
            return True
        except OSError:
            self.storage_error()
            return False

    def storage_error(self):
        self.popup("Could not save changes", "Check that your local storage folder is writable.\nChanges in this session may be lost after closing.", [("Okay", lambda: None)])

    def guide(self):
        self.tutorial(0)

    def tutorial(self, step):
        title, message = TUTORIAL_STEPS[step]
        title = f"Step {step + 1} of {len(TUTORIAL_STEPS)}  |  {title}"
        actions = []
        if step:
            actions.append(("Back", lambda: self.tutorial(step - 1)))
        if step < len(TUTORIAL_STEPS) - 1:
            actions.append(("Next", lambda: self.tutorial(step + 1)))
        else:
            actions.append(("Finish tutorial", self.finish_guide))
        self.popup(title, message, actions)

    def finish_guide(self):
        self.store.state["onboarded"] = True
        if self.persist():
            self.toast("Tutorial complete. Open Help & guide to see it again.")

    def popup(self, title, message, actions):
        if self.dialog:
            self.dialog.destroy()
        # An in-window overlay stays within a 7-inch panel, including in kiosk mode.
        overlay = tk.Frame(self, bg=INK)
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.dialog = overlay
        panel = tk.Frame(overlay, bg=CARD, padx=24, pady=20)
        panel.place(relx=.5, rely=.5, anchor="center", relwidth=.90)
        self.label(panel, title, 22, True).pack(anchor="w", pady=(0, 12))
        self.label(panel, message, 14, wraplength=650).pack(anchor="w", pady=(0, 16))
        row = tk.Frame(panel, bg=CARD)
        row.pack(fill="x")
        for i, (text, action) in enumerate(actions):
            def run(callback=action):
                overlay.destroy()
                self.dialog = None
                callback()
            button = self.button(row, text, run, primary=i == len(actions) - 1)
            button.pack(side="left", expand=True, fill="x", padx=4)
            if i == len(actions) - 1:
                button.focus_set()
        # Trap keyboard focus inside the modal as well as blocking touch behind it.
        overlay.grab_set()
        overlay.bind("<Destroy>", lambda event: self.focus_set() if event.widget == overlay else None)

    def toast(self, message):
        if self.toast_job:
            self.after_cancel(self.toast_job)
        self.feedback.configure(text=message)
        self.toast_job = self.after(10000, lambda: self.feedback.configure(text=""))

    def update_climate(self):
        if not self.climate_labels:
            return
        source, temp, humidity, status = self.climate_labels
        reading = read_climate()
        source.configure(text=reading["source"])
        if not reading["available"]:
            temp.configure(text="-- °C")
            humidity.configure(text="Humidity unavailable")
            status.configure(text="Check sensor connection.\nNo recent reading received.", fg=AMBER)
            return
        t, h = reading["temperature"], reading["humidity"]
        temp.configure(text=f"{t:.1f} °C")
        humidity.configure(text=f"{h:.0f}% humidity")
        # Informational prototype bands, not medical or hazard detection thresholds.
        message = "Room conditions are steady"
        if t < 18 or t > 28:
            message = "Room is cool" if t < 18 else "Room is warm"
        elif h < 30 or h > 65:
            message = "Air is dry" if h < 30 else "Air is humid"
        status.configure(text=message, fg=TEAL if message.endswith("steady") else AMBER)

    def tick(self):
        now = datetime.now()
        self.clock.configure(text=now.strftime("%a, %b %d   %I:%M %p").replace(" 0", " "))
        self.update_climate()
        if self.page in ("Home", "Reminders"):
            self.reminder_label.configure(text=self.store.reminder_status())
        self.after(1000, self.tick)


def main():
    parser = argparse.ArgumentParser(description="Haven: local 800x480 touchscreen prototype")
    parser.add_argument("--fullscreen", action="store_true", help="Fill the Raspberry Pi display")
    args = parser.parse_args()
    Haven(fullscreen=args.fullscreen).mainloop()


if __name__ == "__main__":
    main()
