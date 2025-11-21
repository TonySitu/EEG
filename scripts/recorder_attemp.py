# simple_emotiv_recorder.py
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import pandas as pd


class SimpleEmotivRecorder:
    def __init__(self, root):
        self.root = root
        self.root.title("Simple EMOTIV Recorder")
        self.root.geometry("500x300")

        self.recording = False
        self.data = []
        self.markers = []

        self.setup_gui()

        # Try to import LSL (but don't crash if it fails)
        try:
            from pylsl import StreamInlet, resolve_streams, StreamInfo, StreamOutlet
            self.pylsl_available = True
            self.StreamInlet = StreamInlet
            self.resolve_streams = resolve_streams
            self.StreamInfo = StreamInfo
            self.StreamOutlet = StreamOutlet
            self.status_label.config(text="Status: LSL loaded - Click 'Scan for EMOTIV'")
        except ImportError as e:
            self.pylsl_available = False
            self.status_label.config(text="Status: LSL not available - Install pylsl")
            print(f"LSL import error: {e}")

    def setup_gui(self):
        # Status
        self.status_label = tk.Label(self.root, text="Status: Initializing...", font=('Arial', 12))
        self.status_label.pack(pady=10)

        # Buttons
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=10)

        self.scan_btn = tk.Button(btn_frame, text="Scan for EMOTIV", command=self.scan_for_emotiv,
                                  bg='blue', fg='white', font=('Arial', 10))
        self.scan_btn.pack(side=tk.LEFT, padx=5)

        self.start_btn = tk.Button(btn_frame, text="Start Tasks", command=self.start_tasks,
                                   bg='green', fg='white', font=('Arial', 10), state=tk.DISABLED)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = tk.Button(btn_frame, text="Stop", command=self.stop_tasks,
                                  bg='red', fg='white', font=('Arial', 10), state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        # Task display
        self.task_label = tk.Label(self.root, text="Ready to start", font=('Arial', 16),
                                   bg='lightgray', height=3)
        self.task_label.pack(pady=20, fill=tk.X, padx=20)

        # Progress
        self.progress = ttk.Progressbar(self.root, orient=tk.HORIZONTAL, length=300, mode='determinate')
        self.progress.pack(pady=10)

        # Info
        self.info_label = tk.Label(self.root, text="Click 'Scan for EMOTIV' to begin", font=('Arial', 9))
        self.info_label.pack(pady=5)

    def scan_for_emotiv(self):
        """Scan for EMOTIV LSL stream"""
        if not self.pylsl_available:
            messagebox.showerror("Error", "pylsl not available. Install with: pip install pylsl")
            return

        try:
            self.status_label.config(text="Status: Scanning for EMOTIV...")

            streams = self.resolve_streams()
            emotiv_found = False

            for stream in streams:
                stream_name = stream.name()
                self.info_label.config(text=f"Found: {stream_name}")
                if 'EMOTIV' in stream_name or 'EEG' in stream.type():
                    self.eeg_inlet = self.StreamInlet(stream)
                    self.status_label.config(text=f"Status: Connected to {stream_name}!")
                    self.start_btn.config(state=tk.NORMAL)
                    emotiv_found = True

                    # Create marker stream
                    info = self.StreamInfo('MotorImageryMarkers', 'Markers', 1, 0, 'string', 'emotiv_mi')
                    self.marker_outlet = self.StreamOutlet(info)
                    break

            if not emotiv_found:
                self.status_label.config(text="Status: No EMOTIV stream found")
                self.info_label.config(text="Make sure EMOTIV Pro is running with LSL enabled")

        except Exception as e:
            self.status_label.config(text="Status: Error during scan")
            messagebox.showerror("Scan Error", f"Error scanning for EMOTIV: {str(e)}")

    def start_tasks(self):
        """Start the motor imagery tasks"""
        self.recording = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.scan_btn.config(state=tk.DISABLED)

        # Start task sequence in separate thread
        self.task_thread = threading.Thread(target=self.run_tasks)
        self.task_thread.daemon = True
        self.task_thread.start()

    def run_tasks(self):
        """Run motor imagery tasks"""
        tasks = ['Left Hand', 'Right Hand', 'Both Feet', 'Tongue']
        colors = ['#FF9999', '#99FF99', '#9999FF', '#FFFF99']
        task_duration = 4
        rest_duration = 2

        try:
            # Send session start marker
            if hasattr(self, 'marker_outlet'):
                self.marker_outlet.push_sample(['session_start'])
                self.markers.append({'time': time.time(), 'marker': 'session_start'})

            for round_num in range(2):  # 2 rounds of tasks
                for i, task in enumerate(tasks):
                    if not self.recording:
                        break

                    # Send task start marker
                    marker = f"start_{task.replace(' ', '_').lower()}"
                    if hasattr(self, 'marker_outlet'):
                        self.marker_outlet.push_sample([marker])
                        self.markers.append({'time': time.time(), 'marker': marker})

                    # Update UI
                    self.root.after(0, lambda t=task, c=colors[i]: self.update_task_display(t, c))

                    # Task period
                    start_time = time.time()
                    while time.time() - start_time < task_duration and self.recording:
                        elapsed = time.time() - start_time
                        progress = (elapsed / task_duration) * 100
                        self.root.after(0, lambda p=progress: self.progress.config(value=p))
                        time.sleep(0.1)

                    if not self.recording:
                        break

                    # Send task end marker
                    marker = f"end_{task.replace(' ', '_').lower()}"
                    if hasattr(self, 'marker_outlet'):
                        self.marker_outlet.push_sample([marker])
                        self.markers.append({'time': time.time(), 'marker': marker})

                    # Rest period
                    self.root.after(0, lambda: self.update_task_display("Rest", "#DDDDDD"))
                    start_time = time.time()
                    while time.time() - start_time < rest_duration and self.recording:
                        elapsed = time.time() - start_time
                        progress = (elapsed / rest_duration) * 100
                        self.root.after(0, lambda p=progress: self.progress.config(value=p))
                        time.sleep(0.1)

            # Session end
            if self.recording and hasattr(self, 'marker_outlet'):
                self.marker_outlet.push_sample(['session_end'])
                self.markers.append({'time': time.time(), 'marker': 'session_end'})

        except Exception as e:
            print(f"Error in task thread: {e}")

        finally:
            if self.recording:
                self.root.after(0, self.stop_tasks)

    def update_task_display(self, task, color):
        """Update the task display in the main thread"""
        self.task_label.config(text=f"Imagine: {task}", bg=color)
        self.info_label.config(text=f"Recording... Markers sent: {len(self.markers)}")

    def stop_tasks(self):
        """Stop recording and save data"""
        self.recording = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.scan_btn.config(state=tk.NORMAL)
        self.task_label.config(text="Recording Complete", bg="lightyellow")
        self.progress.config(value=0)

        # Save data
        self.save_data()

    def save_data(self):
        """Save markers to CSV"""
        try:
            if self.markers:
                df = pd.DataFrame(self.markers)
                filename = f"markers_{time.strftime('%Y%m%d_%H%M%S')}.csv"
                df.to_csv(filename, index=False)
                self.info_label.config(text=f"Saved {len(self.markers)} markers to {filename}")
                print(f"Markers saved to {filename}")
            else:
                self.info_label.config(text="No markers to save")
        except Exception as e:
            messagebox.showerror("Save Error", f"Error saving data: {str(e)}")


if __name__ == "__main__":
    print("Starting Simple EMOTIV Recorder...")
    root = tk.Tk()
    app = SimpleEmotivRecorder(root)
    print("GUI created - starting main loop...")
    root.mainloop()