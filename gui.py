import queue
import threading
import tkinter as tk
from tkinter import ttk
from input_devices import get_input_devices
from output_device import get_output_devices
from run_lesson import run_lesson

status_queue = queue.Queue()
lesson_thread = None
stop_flag = None
input_devices = get_input_devices()
output_devices = get_output_devices()



def on_start():
    input_device = mic_choice.get()
    output_device = output_choice.get()
    if not input_device:
        status_var.set("Please select a microphone before starting.")
        return
    if not output_device:
        status_var.set("Please select an output device before starting.")
        return
    global lesson_thread, stop_flag
    if lesson_thread and lesson_thread.is_alive():
        return  
    stop_flag = threading.Event()
    lesson_thread = threading.Thread(
        target=run_lesson,
        args=(stop_flag, status_queue,input_devices[input_device]),
        daemon=True,
    )
    lesson_thread.start()
    start_button.state(["disabled"])
    stop_button.state(["!disabled"])


def on_stop():
    if stop_flag:
        stop_flag.set()
    stop_button.state(["disabled"])
    status_var.set("Stopping \u2014 generating feedback, please wait...")


def poll():
    global lesson_thread
    while not status_queue.empty():
        status_var.set(status_queue.get())
    if lesson_thread and not lesson_thread.is_alive():
        lesson_thread = None
        start_button.state(["!disabled"])
        stop_button.state(["disabled"])
    root.after(100, poll)


root = tk.Tk()
root.title("Lesson Feedback Tool")
root.minsize(360, 140)
mic_choice = tk.StringVar(value="Please select a microphone")
output_choice = tk.StringVar(value="Please select an output device")    
mainframe = ttk.Frame(root, padding=16)
mainframe.grid(column=0, row=0, sticky=(tk.N, tk.W, tk.E, tk.S))
root.columnconfigure(0, weight=1)
root.rowconfigure(0, weight=1)
mainframe.columnconfigure(0, weight=1)
ttk.Label(mainframe, text="Microphone:").grid(column=0, row=1, sticky=tk.W, pady=(0, 8))
mic_dropdown = ttk.Combobox(mainframe, textvariable=mic_choice, values=list(input_devices.keys()))
mic_dropdown.grid(column=1, row=1, sticky=(tk.W, tk.E), pady=(0, 8))

ttk.Label(mainframe, text="Output Device:").grid(column=0, row=2, sticky=tk.W, pady=(0, 8))
output_dropdown = ttk.Combobox(mainframe, textvariable=output_choice, values=list(output_devices.keys()))
output_dropdown.grid(column=1, row=2, sticky=(tk.W, tk.E), pady=(0, 8))

status_var = tk.StringVar(value="Idle. Pick a microphone and click Start to begin the lesson.")
ttk.Label(mainframe, textvariable=status_var, wraplength=320).grid(
    column=0, row=3, columnspan=2, pady=(0, 16)
)

start_button = ttk.Button(mainframe, text="Start", command=on_start)
start_button.grid(column=0, row=4, padx=4, sticky=tk.E)

stop_button = ttk.Button(mainframe, text="Stop", command=on_stop)
stop_button.grid(column=1, row=4, padx=4, sticky=tk.W)
stop_button.state(["disabled"])  

root.after(100, poll)  
root.mainloop()