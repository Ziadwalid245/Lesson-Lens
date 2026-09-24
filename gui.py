import os
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from input_devices import get_default_input_name, get_input_devices
from output_device import get_default_output_name, get_output_devices
from run_lesson import run_lesson

status_queue = queue.Queue()
lesson_thread = None
stop_flag = None
last_lesson_dir = None
input_devices = get_input_devices()
output_devices = get_output_devices()


def on_start():
    global lesson_thread, stop_flag
    mic, speakers = mic_choice.get(), output_choice.get()
    if mic not in input_devices:
        status_var.set("Please pick your microphone first.")
        return
    if speakers not in output_devices:
        status_var.set("Please pick the speakers/headphones you hear the student on.")
        return
    if lesson_thread and lesson_thread.is_alive():
        return
    stop_flag = threading.Event()
    lesson_thread = threading.Thread(
        target=run_lesson,
        args=(stop_flag, status_queue, input_devices[mic], output_devices[speakers]),
        daemon=True,
    )
    lesson_thread.start()
    set_running(True)


def on_stop():
    if stop_flag:
        stop_flag.set()
    stop_button.state(["disabled"])
    status_var.set("Stopping... generating feedback, please wait.")


def on_open_folder():
    if last_lesson_dir:
        os.startfile(last_lesson_dir)


def set_running(running):
    start_button.state(["disabled" if running else "!disabled"])
    stop_button.state(["!disabled" if running else "disabled"])
    for box in (mic_dropdown, output_dropdown):
        box.state(["disabled"] if running else ["!disabled", "readonly"])


def poll():
    global lesson_thread, last_lesson_dir
    while not status_queue.empty():
        kind, text = status_queue.get()
        if kind == "line":
            transcript_box.configure(state="normal")
            transcript_box.insert("end", text + "\n")
            transcript_box.see("end")
            transcript_box.configure(state="disabled")
        elif kind == "warning":
            messagebox.showwarning("Lesson Lens", text)
        elif kind == "error":
            status_var.set("Stopped with an error.")
            messagebox.showerror("Lesson Lens", text)
        elif kind == "done":
            last_lesson_dir = text
            status_var.set("Feedback ready!")
            open_button.state(["!disabled"])
            os.startfile(os.path.join(text, "feedback.docx"))
        else:
            status_var.set(text)
    if lesson_thread and not lesson_thread.is_alive():
        lesson_thread = None
        set_running(False)
    root.after(100, poll)


root = tk.Tk()
root.title("Lesson Lens")
root.minsize(520, 360)
frame = ttk.Frame(root, padding=16)
frame.grid(sticky="nsew")
root.columnconfigure(0, weight=1)
root.rowconfigure(0, weight=1)
frame.columnconfigure(1, weight=1)
frame.rowconfigure(4, weight=1)

mic_choice = tk.StringVar(value=get_default_input_name() or "")
output_choice = tk.StringVar(value=get_default_output_name() or "")

ttk.Label(frame, text="Your microphone:").grid(column=0, row=0, sticky="w", pady=(0, 8))
mic_dropdown = ttk.Combobox(frame, textvariable=mic_choice, values=list(input_devices), state="readonly")
mic_dropdown.grid(column=1, row=0, columnspan=2, sticky="ew", pady=(0, 8))

ttk.Label(frame, text="Student plays on:").grid(column=0, row=1, sticky="w", pady=(0, 8))
output_dropdown = ttk.Combobox(frame, textvariable=output_choice, values=list(output_devices), state="readonly")
output_dropdown.grid(column=1, row=1, columnspan=2, sticky="ew", pady=(0, 8))

status_var = tk.StringVar(value="Ready. Check the devices above, then press Start.")
ttk.Label(frame, textvariable=status_var, wraplength=480).grid(column=0, row=2, columnspan=3, sticky="w", pady=(0, 8))

buttons = ttk.Frame(frame)
buttons.grid(column=0, row=3, columnspan=3, sticky="w", pady=(0, 8))
start_button = ttk.Button(buttons, text="Start", command=on_start)
start_button.pack(side="left", padx=(0, 4))
stop_button = ttk.Button(buttons, text="Stop", command=on_stop, state="disabled")
stop_button.pack(side="left", padx=4)
open_button = ttk.Button(buttons, text="Open lesson folder", command=on_open_folder, state="disabled")
open_button.pack(side="left", padx=4)

transcript_box = tk.Text(frame, height=12, wrap="word", state="disabled")
transcript_box.grid(column=0, row=4, columnspan=3, sticky="nsew")

root.after(100, poll)
root.mainloop()
