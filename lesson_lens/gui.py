"""The window: pick devices and student, press Start, teach, press Stop."""
import logging
import os
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from . import db, paths, settings
from .devices import get_default_input_name, get_default_output_name, get_input_devices, get_output_devices
from .pipeline import run_lesson

log = logging.getLogger(__name__)


class App:
    def __init__(self, root):
        self.root = root
        self.status_queue = queue.Queue()
        self.lesson_thread = None
        self.stop_flag = None
        self.last_lesson_dir = None
        self.input_devices = get_input_devices()
        self.output_devices = get_output_devices()
        self._build()
        self.root.after(100, self.poll)

    def _pick(self, remembered, devices, default):
        """The device used last time if it's still plugged in, else the Windows default."""
        return remembered if remembered in devices else (default or "")

    def _build(self):
        cfg = settings.get()
        root = self.root
        root.title("Lesson Lens")
        root.minsize(520, 380)
        frame = ttk.Frame(root, padding=16)
        frame.grid(sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(5, weight=1)

        self.student_choice = tk.StringVar(value=cfg.last_student)
        self.mic_choice = tk.StringVar(
            value=self._pick(cfg.last_microphone, self.input_devices, get_default_input_name()))
        self.output_choice = tk.StringVar(
            value=self._pick(cfg.last_speakers, self.output_devices, get_default_output_name()))

        ttk.Label(frame, text="Student:").grid(column=0, row=0, sticky="w", pady=(0, 8))
        self.student_box = ttk.Combobox(frame, textvariable=self.student_choice, values=db.student_names())
        self.student_box.grid(column=1, row=0, columnspan=2, sticky="ew", pady=(0, 8))

        ttk.Label(frame, text="Your microphone:").grid(column=0, row=1, sticky="w", pady=(0, 8))
        self.mic_dropdown = ttk.Combobox(
            frame, textvariable=self.mic_choice, values=list(self.input_devices), state="readonly")
        self.mic_dropdown.grid(column=1, row=1, columnspan=2, sticky="ew", pady=(0, 8))

        ttk.Label(frame, text="Student plays on:").grid(column=0, row=2, sticky="w", pady=(0, 8))
        self.output_dropdown = ttk.Combobox(
            frame, textvariable=self.output_choice, values=list(self.output_devices), state="readonly")
        self.output_dropdown.grid(column=1, row=2, columnspan=2, sticky="ew", pady=(0, 8))

        self.status_var = tk.StringVar(value="Ready. Check the devices above, then press Start.")
        ttk.Label(frame, textvariable=self.status_var, wraplength=480).grid(
            column=0, row=3, columnspan=3, sticky="w", pady=(0, 8))

        buttons = ttk.Frame(frame)
        buttons.grid(column=0, row=4, columnspan=3, sticky="w", pady=(0, 8))
        self.start_button = ttk.Button(buttons, text="Start", command=self.on_start)
        self.start_button.pack(side="left", padx=(0, 4))
        self.stop_button = ttk.Button(buttons, text="Stop", command=self.on_stop, state="disabled")
        self.stop_button.pack(side="left", padx=4)
        self.open_button = ttk.Button(
            buttons, text="Open lesson folder", command=self.on_open_folder, state="disabled")
        self.open_button.pack(side="left", padx=4)

        self.transcript_box = tk.Text(frame, height=12, wrap="word", state="disabled")
        self.transcript_box.grid(column=0, row=5, columnspan=3, sticky="nsew")

    def on_start(self):
        mic, speakers = self.mic_choice.get(), self.output_choice.get()
        student = self.student_choice.get().strip()
        if mic not in self.input_devices:
            self.status_var.set("Please pick your microphone first.")
            return
        if speakers not in self.output_devices:
            self.status_var.set("Please pick the speakers/headphones you hear the student on.")
            return
        if self.lesson_thread and self.lesson_thread.is_alive():
            return
        settings.update(last_microphone=mic, last_speakers=speakers, last_student=student)

        self.transcript_box.configure(state="normal")
        self.transcript_box.delete("1.0", "end")
        self.transcript_box.configure(state="disabled")
        self.stop_flag = threading.Event()
        self.lesson_thread = threading.Thread(
            target=run_lesson, name="lesson",
            args=(self.stop_flag, self.status_queue, self.input_devices[mic], self.output_devices[speakers], student),
            daemon=True,
        )
        self.lesson_thread.start()
        self.set_running(True)

    def on_stop(self):
        if self.stop_flag:
            self.stop_flag.set()
        self.stop_button.state(["disabled"])
        self.status_var.set("Stopping... generating feedback, please wait.")

    def on_open_folder(self):
        if self.last_lesson_dir:
            os.startfile(self.last_lesson_dir)

    def on_close(self):
        if self.lesson_thread and self.lesson_thread.is_alive():
            if not messagebox.askyesno(
                "Lesson Lens",
                "A lesson is still being recorded or turned into feedback.\n\n"
                "Quit anyway? The audio and transcript so far stay in the lesson folder.",
                icon="warning",
                default="no",
            ):
                return
            log.warning("Window closed during a lesson")
            if self.stop_flag:
                self.stop_flag.set()
        self.root.destroy()

    def set_running(self, running):
        self.start_button.state(["disabled" if running else "!disabled"])
        self.stop_button.state(["!disabled" if running else "disabled"])
        for box in (self.mic_dropdown, self.output_dropdown):
            box.state(["disabled"] if running else ["!disabled", "readonly"])
        self.student_box.state(["disabled"] if running else ["!disabled"])

    def poll(self):
        while not self.status_queue.empty():
            kind, text = self.status_queue.get()
            if kind == "line":
                self.transcript_box.configure(state="normal")
                self.transcript_box.insert("end", text + "\n")
                self.transcript_box.see("end")
                self.transcript_box.configure(state="disabled")
            elif kind == "warning":
                messagebox.showwarning("Lesson Lens", text)
            elif kind == "error":
                self.status_var.set("Stopped with an error.")
                messagebox.showerror("Lesson Lens", text)
            elif kind == "done":
                self.last_lesson_dir = text
                self.status_var.set("Feedback ready!")
                self.open_button.state(["!disabled"])
                os.startfile(os.path.join(text, "feedback.docx"))
            else:
                self.status_var.set(text)
        if self.lesson_thread and not self.lesson_thread.is_alive():
            self.lesson_thread = None
            self.set_running(False)
            self.student_box.configure(values=db.student_names())  # pick up a newly added student
        self.root.after(100, self.poll)


def run():
    root = tk.Tk()

    def report_callback_exception(exc_type, exc, tb):
        log.error("Error in the window", exc_info=(exc_type, exc, tb))
        messagebox.showerror("Lesson Lens", f"Something went wrong: {exc}\n\nDetails are in the log:\n{paths.LOG_FILE}")

    root.report_callback_exception = report_callback_exception
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
