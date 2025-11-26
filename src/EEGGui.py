import tkinter as tk
from tkinter import ttk
import random
import time
from pylsl import StreamInfo, StreamOutlet
import threading


class MotorImageryGUI:
    def __init__(self, root):
        self.training_thread = None
        self.trials_entry = None
        self.interval_entry = None
        self.stop_button = None
        self.start_button = None
        self.progress = None
        self.counter_label = None
        self.instruction_label = None
        self.root = root

        self.root.title("Motor Imagery Training - Emotiv BCI")
        self.root.geometry("800x600")
        self.root.configure(bg='#1a1a1a')

        # LSL marker outlet
        info = StreamInfo('MotorImageryMarkers', 'Markers', 1, 0, 'string', 'emotiv_mi_markers')
        self.outlet = StreamOutlet(info)

        # Task configuration
        self.tasks = ['Clench Left Hand', 'Clench Right Hand', 'Open Left Hand', 'Open Right Hand', 'Stick Out Tongue']
        self.task_colors = {
            self.tasks[0]: '#3498db',
            self.tasks[1]: '#e74c3c',
            self.tasks[2]: '#2ecc71',
            self.tasks[3]: '#f39c12',
            self.tasks[4]: '#95a5a6'
        }
        self.interval = 4.0  # seconds
        self.is_running = False
        self.trial_count = 0
        self.max_trials = 50

        self.setup_ui()

    def setup_ui(self):
        # Main instruction label
        self.instruction_label = tk.Label(
            self.root,
            text="Ready to Start",
            font=('Arial', 48, 'bold'),
            bg='#1a1a1a',
            fg='white',
            wraplength=700
        )
        self.instruction_label.pack(expand=True)

        # Trial counter
        self.counter_label = tk.Label(
            self.root,
            text="Trial: 0/50",
            font=('Arial', 16),
            bg='#1a1a1a',
            fg='white'
        )
        self.counter_label.pack(pady=10)

        # Progress bar
        self.progress = ttk.Progressbar(
            self.root,
            length=400,
            mode='determinate'
        )
        self.progress.pack(pady=10)

        # Control frame
        control_frame = tk.Frame(self.root, bg='#1a1a1a')
        control_frame.pack(pady=20)

        # Start button
        self.start_button = tk.Button(
            control_frame,
            text="Start Training",
            font=('Arial', 14, 'bold'),
            bg='#27ae60',
            fg='white',
            command=self.start_training,
            width=15,
            height=2
        )
        self.start_button.pack(side=tk.LEFT, padx=5)

        # Stop button
        self.stop_button = tk.Button(
            control_frame,
            text="Stop",
            font=('Arial', 14, 'bold'),
            bg='#c0392b',
            fg='white',
            command=self.stop_training,
            width=15,
            height=2,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)

        # Settings frame
        settings_frame = tk.Frame(self.root, bg='#1a1a1a')
        settings_frame.pack(pady=10)

        tk.Label(
            settings_frame,
            text="Interval (sec):",
            font=('Arial', 12),
            bg='#1a1a1a',
            fg='white'
        ).pack(side=tk.LEFT, padx=5)

        self.interval_entry = tk.Entry(settings_frame, font=('Arial', 12), width=8)
        self.interval_entry.insert(0, "4.0")
        self.interval_entry.pack(side=tk.LEFT, padx=5)

        tk.Label(
            settings_frame,
            text="Max Trials:",
            font=('Arial', 12),
            bg='#1a1a1a',
            fg='white'
        ).pack(side=tk.LEFT, padx=5)

        self.trials_entry = tk.Entry(settings_frame, font=('Arial', 12), width=8)
        self.trials_entry.insert(0, "50")
        self.trials_entry.pack(side=tk.LEFT, padx=5)

    def start_training(self):
        # Get settings
        try:
            self.interval = float(self.interval_entry.get())
            self.max_trials = int(self.trials_entry.get())
        except ValueError:
            self.instruction_label.config(text="Invalid settings!", fg='red')
            return

        self.is_running = True
        self.trial_count = 0
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.interval_entry.config(state=tk.DISABLED)
        self.trials_entry.config(state=tk.DISABLED)

        # Send session start marker
        self.outlet.push_sample(['session_start'])

        # Start training thread
        self.training_thread = threading.Thread(target=self.run_training)
        self.training_thread.daemon = True
        self.training_thread.start()

    def stop_training(self):
        self.is_running = False
        self.outlet.push_sample(['session_stop'])
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.interval_entry.config(state=tk.NORMAL)
        self.trials_entry.config(state=tk.NORMAL)
        self.instruction_label.config(text="Training Stopped", fg='white', bg='#1a1a1a')

    def run_training(self):
        rest_interval = 4.0  # 4 seconds rest between tasks

        while self.is_running and self.trial_count < self.max_trials:
            # Select random task
            task = random.choice(self.tasks)

            # Update UI for task
            self.root.after(0, self.update_display, task)

            # Send ONLY START marker (no end marker needed)
            marker = task.lower().replace(' ', '_')
            self.outlet.push_sample([f'{marker}_start'])
            print(f"🚀 Sent marker: {marker}_start")

            # Wait for task duration - this defines your epoch length
            start_time = time.time()
            while time.time() - start_time < self.interval and self.is_running:
                elapsed = time.time() - start_time
                progress = (elapsed / self.interval) * 100
                self.root.after(0, self.progress.config, {'value': progress})
                time.sleep(0.05)

            self.trial_count += 1
            self.root.after(0, self.update_counter)

            # Rest period (optional - for baseline)
            self.root.after(0, self.update_display_rest)
            self.outlet.push_sample(['rest_period_start'])
            print(f"😴 Sent marker: rest_period_start")

            start_time = time.time()
            while time.time() - start_time < rest_interval and self.is_running:
                elapsed = time.time() - start_time
                progress = (elapsed / rest_interval) * 100
                self.root.after(0, self.progress.config, {'value': progress})
                time.sleep(0.05)

            # No rest_period_end needed either

        if self.is_running:
            self.root.after(0, self.training_complete)

    def update_display(self, task):
        color = self.task_colors[task]
        self.instruction_label.config(
            text=f"Imagine: {task}",
            fg='white',
            bg=color
        )
        self.root.configure(bg=color)

    def update_display_rest(self):
        self.instruction_label.config(
            text="Rest",
            fg='white',
            bg='#34495e'
        )
        self.root.configure(bg='#34495e')

    def update_counter(self):
        self.counter_label.config(text=f"Trial: {self.trial_count}/{self.max_trials}")

    def training_complete(self):
        self.outlet.push_sample(['session_complete'])
        self.instruction_label.config(
            text="Training Complete!",
            fg='white',
            bg='#27ae60'
        )
        self.root.configure(bg='#27ae60')
        self.stop_training()


if __name__ == "__main__":
    root = tk.Tk()
    app = MotorImageryGUI(root)
    root.mainloop()
