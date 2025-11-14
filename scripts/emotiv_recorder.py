# emotiv_recorder.py
from pylsl import StreamInlet, resolve_streams, StreamInfo, StreamOutlet
import time
import pandas as pd


class EmotivRecorder:
    def __init__(self):
        self.eeg_data = []
        self.markers = []
        self.eeg_inlet = None
        self.marker_outlet = None

    def connect_to_emotiv(self):
        """Connect to EMOTIV's LSL EEG stream"""
        print("Looking for EMOTIV EEG stream...")
        streams = resolve_streams()

        for stream in streams:
            print(f"Found: {stream.name()} ({stream.type()})")
            if 'EMOTIV' in stream.name() or 'EEG' in stream.type():
                self.eeg_inlet = StreamInlet(stream)
                print(f"✓ Connected to EEG stream: {stream.name()}")
                return True

        print("✗ No EMOTIV EEG stream found")
        return False

    def record_session(self, duration=60):
        """Record EEG data and send markers"""
        if not self.eeg_inlet:
            print("Not connected to EMOTIV stream")
            return

        print(f"Recording for {duration} seconds...")
        start_time = time.time()

        while time.time() - start_time < duration:
            # Get EEG sample
            sample, timestamp = self.eeg_inlet.pull_sample(timeout=0.1)
            if sample:
                self.eeg_data.append({
                    'timestamp': timestamp,
                    'data': sample,
                    'marker': 'eeg_data'
                })

        print("Recording complete!")

    def save_data(self, filename="eeg_with_markers.csv"):
        """Save EEG data to CSV"""
        df = pd.DataFrame(self.eeg_data)
        df.to_csv(filename, index=False)
        print(f"Data saved to {filename}")


if __name__ == "__main__":
    recorder = EmotivRecorder()
    if recorder.connect_to_emotiv():
        recorder.record_session(30)  # Record for 30 seconds
        recorder.save_data()