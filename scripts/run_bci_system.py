import subprocess
import sys
import time
import os


def get_project_root():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    return project_root


def main():
    print("=== Starting BCI System ===")

    project_root = get_project_root()
    src_dir = os.path.join(project_root, "src")

    print(f"Project root: {project_root}")
    print(f"Source directory: {src_dir}")

    # Check if files exist
    gui_path = os.path.join(src_dir, "EEGGui.py")
    monitor_path = os.path.join(src_dir, "MarkerMonitor.py")

    if not os.path.exists(gui_path):
        print(f"ERROR: {gui_path} not found!")
        return

    if not os.path.exists(monitor_path):
        print(f"ERROR: {monitor_path} not found!")
        return

    print("All files found!")

    # Change to project root directory
    os.chdir(project_root)

    print("1. Starting main GUI...")
    gui_process = subprocess.Popen([sys.executable, "src/EEGGui.py"])

    time.sleep(3)

    print("2. Starting marker monitor...")
    monitor_process = subprocess.Popen([sys.executable, "src/MarkerMonitor.py"])

    print("System running! Close the GUI window to stop.")

    # Wait for GUI to close
    gui_process.wait()
    monitor_process.terminate()
    print("System stopped.")


if __name__ == "__main__":
    main()
