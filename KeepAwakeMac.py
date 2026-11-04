#!/usr/bin/env python3
"""KeepAwake for macOS: a small, locally running mouse mover.

Requires Python 3, Tkinter and PyAutoGUI when running from source.
The packaged .app includes Python and its Python dependencies.
"""

import ctypes
import math
import os
import random
import subprocess
import sys
import time
import tkinter as tk
from tkinter import messagebox, ttk

import pyautogui


APP_NAME = "KeepAwakeMac"
SAFE_MARGIN = 80
USER_MOVE_THRESHOLD = 5
MOVE_STEPS = 20
STEP_MS = 50
MONITOR_MS = 100

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0


def accessibility_is_enabled():
    """Check macOS Accessibility consent before attempting pointer control."""
    if sys.platform != "darwin":
        return False
    try:
        framework = ctypes.CDLL(
            "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
        )
        framework.AXIsProcessTrusted.restype = ctypes.c_bool
        framework.AXIsProcessTrusted.argtypes = []
        return bool(framework.AXIsProcessTrusted())
    except (OSError, AttributeError):
        return False


def open_accessibility_settings():
    """Open macOS Privacy & Security > Accessibility."""
    try:
        subprocess.Popen(
            [
                "/usr/bin/open",
                "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
            ]
        )
    except OSError as exc:
        messagebox.showerror("Could not open Settings", str(exc))


class KeepAwakeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("KeepAwake for macOS")
        self.root.geometry("460x400")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.running = False
        self.paused = False
        self.caffeinate = None
        self.last_position = None
        self.next_move_at = 0.0
        self.path = None
        self.expected = None
        self.idle_seconds = 8
        self.max_distance = 25
        self.width, self.height = pyautogui.size()

        self.idle_var = tk.StringVar(value="8")
        self.distance_var = tk.StringVar(value="25")
        self.status_var = tk.StringVar(value="Stopped")
        self.detail_var = tk.StringVar(value="Press Start to keep your Mac awake.")

        self._build_ui()
        self.root.after(MONITOR_MS, self.tick)

    def _build_ui(self):
        base = ttk.Frame(self.root, padding=22)
        base.pack(fill="both", expand=True)

        ttk.Label(base, text="KeepAwake", font=("Helvetica", 21, "bold")).pack(anchor="w")
        ttk.Label(
            base,
            text="Keep the display awake and gently move the pointer when idle.",
            wraplength=405,
        ).pack(anchor="w", pady=(5, 17))

        status_frame = ttk.LabelFrame(base, text="Status", padding=11)
        status_frame.pack(fill="x")
        ttk.Label(status_frame, textvariable=self.status_var, font=("Helvetica", 13, "bold")).pack(anchor="w")
        ttk.Label(status_frame, textvariable=self.detail_var, wraplength=383).pack(anchor="w", pady=(5, 0))

        settings = ttk.LabelFrame(base, text="Mouse movement settings", padding=12)
        settings.pack(fill="x", pady=(15, 14))
        ttk.Label(settings, text="Idle time (seconds):").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(settings, textvariable=self.idle_var, width=9).grid(row=0, column=1, padx=(15, 0), sticky="w")
        ttk.Label(settings, text="Max movement (pixels):").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(settings, textvariable=self.distance_var, width=9).grid(row=1, column=1, padx=(15, 0), sticky="w")

        buttons = ttk.Frame(base)
        buttons.pack(fill="x")
        self.start_button = ttk.Button(buttons, text="Start", command=self.start)
        self.start_button.pack(side="left", padx=(0, 6))
        self.pause_button = ttk.Button(buttons, text="Pause", command=self.toggle_pause, state="disabled")
        self.pause_button.pack(side="left", padx=(0, 6))
        self.stop_button = ttk.Button(buttons, text="Stop", command=self.stop, state="disabled")
        self.stop_button.pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Exit", command=self.close).pack(side="right")

        ttk.Button(
            base, text="Open macOS Accessibility Settings", command=open_accessibility_settings
        ).pack(anchor="w", pady=(16, 0))
        ttk.Label(
            base,
            text="Safety: automatic movement is disabled near screen edges.\n"
                 "Normal display-sleep settings return when stopped or exited.",
            wraplength=410,
            font=("Helvetica", 10),
        ).pack(anchor="w", pady=(11, 0))

    def _get_settings(self):
        try:
            idle = int(self.idle_var.get())
            distance = int(self.distance_var.get())
        except ValueError:
            messagebox.showerror("Invalid settings", "Enter whole numbers for both settings.")
            return None
        if not 3 <= idle <= 3600:
            messagebox.showerror("Invalid idle time", "Use an idle time between 3 and 3600 seconds.")
            return None
        if not 1 <= distance <= 100:
            messagebox.showerror("Invalid distance", "Use a maximum distance between 1 and 100 pixels.")
            return None
        return idle, distance

    def _enable_awake(self):
        if self.caffeinate is not None and self.caffeinate.poll() is None:
            return True
        try:
            # -d = prevent display sleep; -i = prevent idle system sleep.
            # -w ensures the assertion ends if this application exits unexpectedly.
            self.caffeinate = subprocess.Popen(
                ["/usr/bin/caffeinate", "-d", "-i", "-w", str(os.getpid())],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except OSError as exc:
            messagebox.showerror("Could not keep Mac awake", f"caffeinate failed: {exc}")
            self.caffeinate = None
            return False

    def _disable_awake(self):
        process = self.caffeinate
        self.caffeinate = None
        if process is not None and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=1)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    process.kill()
                except OSError:
                    pass

    def _reset_cursor_tracking(self):
        self.path = None
        self.expected = None
        self.last_position = tuple(pyautogui.position())
        self.next_move_at = time.monotonic() + self.idle_seconds

    def start(self):
        if self.running:
            return
        if sys.platform != "darwin":
            messagebox.showerror("macOS only", "This version must be run on macOS.")
            return
        values = self._get_settings()
        if values is None:
            return
        if not accessibility_is_enabled():
            messagebox.showwarning(
                "Accessibility permission required",
                "To move the pointer, KeepAwake needs Accessibility permission.\n\n"
                "Open System Settings > Privacy & Security > Accessibility, "
                "enable KeepAwakeMac, then reopen the app if needed.",
            )
            open_accessibility_settings()
            return
        self.idle_seconds, self.max_distance = values
        if not self._enable_awake():
            return
        self.running = True
        self.paused = False
        self._reset_cursor_tracking()
        self.start_button.configure(state="disabled")
        self.pause_button.configure(state="normal", text="Pause")
        self.stop_button.configure(state="normal")
        self.status_var.set("Running")
        self.detail_var.set(f"Mac awake. Mouse moves after {self.idle_seconds}s of cursor inactivity.")

    def toggle_pause(self):
        if not self.running:
            return
        if not self.paused:
            self.paused = True
            self.path = None
            self._disable_awake()
            self.pause_button.configure(text="Resume")
            self.status_var.set("Paused")
            self.detail_var.set("Mouse mover and keep-awake are paused.")
        else:
            if not self._enable_awake():
                return
            self.paused = False
            self._reset_cursor_tracking()
            self.pause_button.configure(text="Pause")
            self.status_var.set("Running")
            self.detail_var.set("Mac awake. Mouse movement will resume after inactivity.")

    def stop(self):
        self.running = False
        self.paused = False
        self.path = None
        self._disable_awake()
        self.start_button.configure(state="normal")
        self.pause_button.configure(state="disabled", text="Pause")
        self.stop_button.configure(state="disabled")
        self.status_var.set("Stopped")
        self.detail_var.set("Normal macOS sleep behavior restored.")

    def close(self):
        self.stop()
        self.root.destroy()

    def _near_edge(self, p):
        return (
            p[0] <= SAFE_MARGIN
            or p[1] <= SAFE_MARGIN
            or p[0] >= self.width - SAFE_MARGIN
            or p[1] >= self.height - SAFE_MARGIN
        )

    def _user_moved(self, pos):
        self.path = None
        self.expected = None
        self.last_position = pos
        self.next_move_at = time.monotonic() + self.idle_seconds

    def _begin_movement(self, pos):
        target_x = max(SAFE_MARGIN + 1, min(self.width - SAFE_MARGIN - 1,
                                          pos[0] + random.randint(-self.max_distance, self.max_distance)))
        target_y = max(SAFE_MARGIN + 1, min(self.height - SAFE_MARGIN - 1,
                                          pos[1] + random.randint(-self.max_distance, self.max_distance)))
        if (target_x, target_y) == pos:
            self.next_move_at = time.monotonic() + random.uniform(3, 6)
            return
        self.path = (pos, (target_x, target_y), 0)
        self.expected = pos
        self._advance_movement(pos)

    def _advance_movement(self, pos):
        if not self.path:
            return
        origin, target, step = self.path
        step += 1
        progress = step / MOVE_STEPS
        x = round(origin[0] + (target[0] - origin[0]) * progress)
        y = round(origin[1] + (target[1] - origin[1]) * progress)
        pyautogui.moveTo(x, y, duration=0)
        self.expected = (x, y)
        self.last_position = self.expected
        if step >= MOVE_STEPS:
            self.path = None
            self.expected = None
            self.next_move_at = time.monotonic() + random.uniform(3, 6)
        else:
            self.path = (origin, target, step)

    def tick(self):
        try:
            if self.running and not self.paused:
                pos = tuple(pyautogui.position())
                now = time.monotonic()
                if self._near_edge(pos):
                    # Do not interfere near screen edges or corners.
                    self._user_moved(pos)
                elif self.path is not None:
                    distance = math.dist(pos, self.expected)
                    if distance > USER_MOVE_THRESHOLD:
                        self._user_moved(pos)
                    else:
                        self._advance_movement(pos)
                elif self.last_position and math.dist(pos, self.last_position) > USER_MOVE_THRESHOLD:
                    # A person moved the mouse: postpone automatic movement.
                    self._user_moved(pos)
                elif now >= self.next_move_at:
                    self._begin_movement(pos)
                else:
                    self.last_position = pos
        except pyautogui.FailSafeException:
            self.paused = True
            self.path = None
            self._disable_awake()
            self.pause_button.configure(text="Resume")
            self.status_var.set("Paused (safety stop)")
            self.detail_var.set("PyAutoGUI safety stop activated. Move the cursor away, then Resume.")
        except Exception as exc:
            self.stop()
            messagebox.showerror("KeepAwake stopped", f"Pointer control failed:\n{exc}")
        finally:
            try:
                self.root.after(STEP_MS if self.path else MONITOR_MS, self.tick)
            except tk.TclError:
                pass


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("aqua") if "aqua" in ttk.Style().theme_names() else None
    except tk.TclError:
        pass
    KeepAwakeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
