"""Run with: python -m host.controller --port COM5 --front URL --rear URL."""
import argparse
import io
import queue
import threading
import time
from urllib.request import urlopen
from urllib.error import HTTPError

from .intent import DriveIntent
from .protocol import encode_wheels, read_mjpeg_frame


class CameraReader(threading.Thread):
    def __init__(self, url, stop):
        super().__init__(daemon=True)
        self.url, self.stop_event = url, stop
        self.latest = queue.Queue(maxsize=1)

    def publish(self, item):
        try:
            self.latest.get_nowait()
        except queue.Empty:
            pass
        self.latest.put_nowait(item)

    def run(self):
        while not self.stop_event.is_set():
            try:
                with urlopen(self.url, timeout=3) as response:
                    while not self.stop_event.is_set():
                        jpeg = read_mjpeg_frame(response)
                        self.publish((time.monotonic(), jpeg, None))
            except Exception as exc:
                if isinstance(exc, HTTPError):
                    exc.close()
                self.publish((0, None, str(exc)))
                self.stop_event.wait(1)


def main():
    parser = argparse.ArgumentParser(description="Two Wi-Fi cameras and Bluetooth SPP robot control")
    parser.add_argument("--port", default="", help="Paired Bluetooth serial port, e.g. COM5 or /dev/rfcomm0")
    parser.add_argument("--front", default="http://robot-front.local:81/stream")
    parser.add_argument("--rear", default="http://robot-rear.local:81/stream")
    args = parser.parse_args()

    # Keep --help and protocol tests usable on computers without Tk installed.
    try:
        import tkinter as tk
        from tkinter import ttk
        import serial
        from PIL import Image, ImageTk
    except ImportError as exc:
        parser.exit(1, f"Missing GUI dependency: {exc}. See README.md for installation.\n")

    class Controller:
        def __init__(self):
            self.root = tk.Tk()
            self.root.title("Four-wheel surveillance robot")
            self.root.geometry("1020x760")
            self.root.minsize(780, 680)
            self.intent = DriveIntent()
            self.serial = None
            self.stop_event = threading.Event()
            self.last_frame = [0.0, 0.0]
            self.images = [None, None]
            self.release_jobs = {}
            self.port = tk.StringVar(value=args.port)
            self.status = tk.StringVar(value="Pair SurveillanceRobot, enter its serial port, then connect.")
            self.speed = tk.IntVar(value=120)
            self.wheel_values = [tk.IntVar(value=0) for _ in range(4)]

            top = ttk.Frame(self.root, padding=12)
            top.pack(fill="x")
            ttk.Label(top, text="Bluetooth serial port:").pack(side="left")
            ttk.Entry(top, textvariable=self.port, width=28).pack(side="left", padx=8)
            self.connect_button = ttk.Button(top, text="Connect", command=self.connect)
            self.connect_button.pack(side="left")
            ttk.Button(top, text="STOP (Space)", command=self.halt).pack(side="right")

            cameras = ttk.Frame(self.root, padding=12)
            cameras.pack(fill="both", expand=True)
            self.views, self.camera_status = [], []
            for index, (name, url) in enumerate((("Front", args.front), ("Rear", args.rear))):
                panel = ttk.LabelFrame(cameras, text=name, padding=8)
                panel.grid(row=0, column=index, sticky="nsew", padx=4)
                cameras.columnconfigure(index, weight=1, uniform="camera")
                view = ttk.Label(panel, text="Connecting to camera…", anchor="center")
                view.pack(fill="both", expand=True)
                status = ttk.Label(panel, text=url, wraplength=430)
                status.pack(fill="x", pady=(6, 0))
                self.views.append(view)
                self.camera_status.append(status)
            cameras.rowconfigure(0, weight=1)
            self.readers = [CameraReader(url, self.stop_event) for url in (args.front, args.rear)]
            for reader in self.readers:
                reader.start()

            controls = ttk.Frame(self.root, padding=12)
            controls.pack(fill="x")
            ttk.Label(controls, text="Hold W/A/S/D, arrows, or a direction button. Release to stop.").pack()
            ttk.Label(controls, text="Driving requires both videos to be live. Losing focus or video stops motion.").pack()
            speed_row = ttk.Frame(controls)
            speed_row.pack(fill="x", pady=6)
            ttk.Label(speed_row, text="Drive speed (0–255):").pack(side="left")
            tk.Scale(speed_row, from_=0, to=255, orient="horizontal", variable=self.speed,
                     length=260).pack(side="left")
            directions = ttk.Frame(controls)
            directions.pack()
            for text, key in (("Left", "a"), ("Forward", "w"), ("Reverse", "s"), ("Right", "d")):
                button = ttk.Button(directions, text=text, takefocus=False)
                button.pack(side="left", padx=4)
                button.bind("<ButtonPress-1>", lambda event, k=key: self.intent.direction(k))
                button.bind("<ButtonRelease-1>", lambda event: self.halt())
                button.bind("<Leave>", lambda event: self.halt())

            individual = ttk.LabelFrame(controls, text="Individual wheel speeds (−255 to 255)", padding=8)
            individual.pack(fill="x", pady=10)
            for name, variable in zip(("Front left", "Front right", "Rear left", "Rear right"), self.wheel_values):
                ttk.Label(individual, text=name).pack(side="left", padx=(8, 4))
                ttk.Spinbox(individual, from_=-255, to=255, textvariable=variable,
                            width=5).pack(side="left")
            manual = ttk.Button(controls, text="Hold to drive individual wheels", takefocus=False)
            manual.pack()
            manual.bind("<ButtonPress-1>", lambda event: self.intent.start_manual())
            manual.bind("<ButtonRelease-1>", lambda event: self.halt())
            manual.bind("<Leave>", lambda event: self.halt())
            ttk.Label(self.root, textvariable=self.status, padding=12, wraplength=960).pack(fill="x")

            self.root.bind("<KeyPress>", self.key_press)
            self.root.bind("<KeyRelease>", self.key_release)
            self.root.bind("<FocusOut>", lambda event: self.root.after_idle(self.check_focus))
            self.root.protocol("WM_DELETE_WINDOW", self.close)
            self.root.after(50, self.update_video)
            self.root.after(100, self.heartbeat)

        def connect(self):
            if self.serial is not None:
                self.disconnect("Bluetooth disconnected. Press Connect to reconnect.")
                return
            try:
                self.serial = serial.Serial(self.port.get().strip(), baudrate=115200,
                                            timeout=0, write_timeout=0.2)
                self.serial.write(b"\nSTOP\n")
                self.intent.halt()
                self.connect_button.configure(text="Disconnect")
                self.root.focus_set()
                self.status.set("Bluetooth connected; release controls after any stop, then press again.")
            except (serial.SerialException, OSError, ValueError) as exc:
                self.disconnect(f"Could not connect: {exc}")

        def disconnect(self, message):
            self.intent.halt()
            if self.serial is not None:
                try:
                    self.serial.write(b"\nSTOP\n")
                except (serial.SerialException, OSError):
                    pass
                finally:
                    self.serial.close()
                    self.serial = None
            self.connect_button.configure(text="Connect")
            self.status.set(message)

        def halt(self):
            self.intent.halt()
            if self.serial is not None:
                try:
                    self.serial.write(b"STOP\n")
                except (serial.SerialException, OSError):
                    self.disconnect("Bluetooth write failed; motors will stop on timeout.")

        def check_focus(self):
            if self.root.focus_displayof() is None:
                self.halt()

        @staticmethod
        def normalized_key(event):
            return {"Up": "w", "Down": "s", "Left": "a", "Right": "d"}.get(
                event.keysym, event.keysym.lower())

        def key_press(self, event):
            key = self.normalized_key(event)
            if key in self.release_jobs:
                self.root.after_cancel(self.release_jobs.pop(key))
            if key == "space":
                self.intent.press(key)
                self.halt()
                return "break"
            if key in ("w", "a", "s", "d"):
                if event.widget.winfo_class() in ("TEntry", "TSpinbox", "Scale", "TScale"):
                    return
                self.intent.press(key)
                return "break"

        def key_release(self, event):
            key = self.normalized_key(event)
            # X11 auto-repeat emits release/press pairs; defer release until idle.
            def release():
                self.release_jobs.pop(key, None)
                self.intent.release(key)
            self.release_jobs[key] = self.root.after_idle(release)

        def update_video(self):
            for index, reader in enumerate(self.readers):
                try:
                    timestamp, jpeg, error = reader.latest.get_nowait()
                except queue.Empty:
                    continue
                if error:
                    self.last_frame[index] = 0
                    self.camera_status[index].configure(text=f"Offline; retrying: {error}")
                    continue
                try:
                    with Image.open(io.BytesIO(jpeg)) as image:
                        image.thumbnail((460, 340))
                        self.images[index] = ImageTk.PhotoImage(image)
                    self.views[index].configure(image=self.images[index], text="")
                    self.last_frame[index] = timestamp
                    self.camera_status[index].configure(text=f"Live • {reader.url}")
                except (OSError, ValueError) as exc:
                    self.last_frame[index] = 0
                    self.camera_status[index].configure(text=f"Bad JPEG: {exc}")
            self.root.after(50, self.update_video)

        def heartbeat(self):
            video_ready = all(time.monotonic() - timestamp < 2 for timestamp in self.last_frame)
            if not video_ready or self.serial is None:
                self.intent.halt()
            if self.serial is not None:
                try:
                    manual = [int(value.get()) for value in self.wheel_values] if self.intent.manual else (0,) * 4
                    wheels = self.intent.wheels(self.speed.get(), manual)
                    packet = encode_wheels(wheels) if any(wheels) else b"STOP\n"
                    if self.serial.write(packet) != len(packet):
                        raise serial.SerialException("Incomplete Bluetooth write")
                    self.status.set("Bluetooth connected • " + (
                        f"FL FR RL RR: {wheels}" if video_ready else "Waiting for both live videos; motors stopped."))
                except (ValueError, tk.TclError):
                    self.halt()
                    self.status.set("Enter four whole-number speeds from −255 to 255.")
                except (serial.SerialException, OSError) as exc:
                    self.disconnect(f"Bluetooth lost: {exc}. Reconnect manually.")
            self.root.after(100, self.heartbeat)

        def close(self):
            self.stop_event.set()
            self.disconnect("Closed")
            self.root.destroy()

    app = Controller()
    app.root.mainloop()


if __name__ == "__main__":
    main()
