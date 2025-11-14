import subprocess
import sys
import time
import threading


def run_main_gui():
    """Run the main GUI"""
    print("Starting main GUI...")
    subprocess.run([sys.executable, "EEGGui.py"])


def run_marker_monitor():
    """Run the marker monitor"""
    print("Starting marker monitor...")
    # Wait a bit for main GUI to start
    time.sleep(3)
    subprocess.run([sys.executable, "MarkerMonitor.py"])


if __name__ == "__main__":
    print("=== Starting BCI System ===")

    # Run both in threads
    gui_thread = threading.Thread(target=run_main_gui)
    monitor_thread = threading.Thread(target=run_marker_monitor)

    gui_thread.start()
    monitor_thread.start()

    gui_thread.join()
    monitor_thread.join()
