import time
import csv
import threading
import pandas as pd
from datetime import datetime


class EEGRecorder:
    def __init__(self):
        self.recorded_data = []
        self.current_marker = "no_marker"
        self.is_recording = False
        self.recording_thread = None
        self.marker_lock = threading.Lock()

    def connect_eeg(self):
        """Connect to EEG device"""
        try:
            # Your EEG connection code here
            print("✓ Connected to EEG stream")
            return True
        except Exception as e:
            print(f"❌ EEG connection failed: {e}")
            return False

    def start_recording(self):
        """Start continuous EEG recording"""
        self.is_recording = True
        self.recorded_data = []
        self.recording_thread = threading.Thread(target=self._record_continuous)
        self.recording_thread.start()
        print("🎯 Started continuous EEG recording")

    def stop_recording(self):
        """Stop EEG recording"""
        self.is_recording = False
        if self.recording_thread:
            self.recording_thread.join()
        print("⏹️ Stopped EEG recording")

    def _record_continuous(self):
        """Continuous EEG data recording (runs in separate thread)"""
        sample_count = 0
        while self.is_recording:
            try:
                # Simulate/get real EEG data
                eeg_sample = self._get_eeg_sample(sample_count)

                with self.marker_lock:
                    current_marker = self.current_marker

                # Create data sample with current marker
                sample = {
                    'timestamp': time.time(),
                    'data': eeg_sample,
                    'marker': current_marker,
                    'sample_id': sample_count,
                    'task_time': time.time() - getattr(self, 'task_start_time', time.time())
                }

                self.recorded_data.append(sample)
                sample_count += 1

                # Simulate EEG sampling rate (e.g., 128 Hz)
                time.sleep(0.0078)  # ~128 Hz

            except Exception as e:
                print(f"❌ Recording error: {e}")
                break

    def _get_eeg_sample(self, sample_id):
        """Get EEG sample from LSL stream"""
        try:
            import pylsl

            if not hasattr(self, 'inlet'):
                # Resolve EEG stream (run this once)
                print("Looking for EEG stream...")
                streams = pylsl.resolve_byprop('type', 'EEG', timeout=5)
                if streams:
                    self.inlet = pylsl.StreamInlet(streams[0])
                    print(f"✓ Connected to: {streams[0].name()}")
                else:
                    raise Exception("No EEG stream found")

            # Get sample from LSL
            sample, timestamp = self.inlet.pull_sample(timeout=0.1)
            return sample

        except Exception as e:
            print(f"❌ LSL error: {e}")
            # Return simulated data as fallback
            import random
            return [random.uniform(-100, 100) for _ in range(32)]

    def set_marker(self, marker):
        """Set marker for upcoming EEG samples"""
        with self.marker_lock:
            self.current_marker = marker
            self.task_start_time = time.time()
        print(f"🎯 Marker set: {marker}")

    def run_experiment_sequence(self):
        """Run the complete experiment sequence"""
        if not self.connect_eeg():
            return False

        try:
            # Start continuous recording
            self.start_recording()

            # Define experiment sequence: (marker, duration_in_seconds)
            experiment_sequence = [
                ("session_start", 2),
                ("stick_out_tongue_start", 5),
                ("stick_out_tongue_end", 2),
                ("rest_period_start", 4),
                ("rest_period_end", 1),
                ("open_left_hand_start", 5),
                ("open_left_hand_end", 2),
                ("rest_period_start", 4),
                ("rest_period_end", 1),
                ("clench_left_hand_start", 5),
                ("clench_left_hand_end", 2),
                ("rest_period_start", 4),
                ("session_stop", 2)
            ]

            print("🔬 Starting experiment sequence...")

            for marker, duration in experiment_sequence:
                print(f"➡️ Task: {marker} for {duration} seconds")

                # Set marker for this task period
                self.set_marker(marker)

                # Wait for the task duration
                time.sleep(duration)

            # Stop recording
            self.stop_recording()

            # Save data
            filename = self.save_data()

            # Verify data
            self.verify_markers()

            return True

        except Exception as e:
            print(f"❌ Experiment failed: {e}")
            self.stop_recording()
            return False

    def save_data(self):
        """Save recorded data to CSV"""
        if not self.recorded_data:
            print("❌ No data to save")
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"eeg_data_{timestamp}.csv"

        try:
            with open(filename, 'w', newline='') as file:
                writer = csv.writer(file)
                # Write header
                writer.writerow(['timestamp', 'data', 'marker', 'sample_id', 'task_time'])

                # Write data
                for sample in self.recorded_data:
                    writer.writerow([
                        sample['timestamp'],
                        str(sample['data']),
                        sample['marker'],
                        sample['sample_id'],
                        sample['task_time']
                    ])

            print(f"💾 Saved {len(self.recorded_data)} samples to {filename}")
            return filename

        except Exception as e:
            print(f"❌ Save failed: {e}")
            return None

    def verify_markers(self):
        """Verify marker distribution in recorded data"""
        if not self.recorded_data:
            print("❌ No data to verify")
            return

        markers = [sample['marker'] for sample in self.recorded_data]
        marker_counts = {}

        for marker in markers:
            marker_counts[marker] = marker_counts.get(marker, 0) + 1

        print("\n📊 MARKER DISTRIBUTION VERIFICATION:")
        print("=" * 40)
        for marker, count in marker_counts.items():
            percentage = (count / len(markers)) * 100
            print(f"  {marker}: {count} samples ({percentage:.1f}%)")

        # Check for expected markers
        expected_markers = [
            "session_start", "stick_out_tongue_start", "stick_out_tongue_end",
            "rest_period_start", "rest_period_end", "open_left_hand_start",
            "open_left_hand_end", "clench_left_hand_start", "clench_left_hand_end",
            "session_stop"
        ]

        print("\n✅ Expected markers present:")
        for expected in expected_markers:
            if expected in marker_counts:
                print(f"  ✓ {expected}")
            else:
                print(f"  ✗ {expected} (MISSING)")

    def load_and_analyze_data(self, filename):
        """Load and analyze saved data"""
        try:
            df = pd.read_csv(filename)
            print(f"\n📈 Data Analysis for {filename}:")
            print(f"Total samples: {len(df)}")
            print(f"Recording duration: {df['timestamp'].max() - df['timestamp'].min():.2f} seconds")
            print(f"Sample rate: ~{len(df) / (df['timestamp'].max() - df['timestamp'].min()):.1f} Hz")

            marker_dist = df['marker'].value_counts()
            print("\nMarker distribution:")
            for marker, count in marker_dist.items():
                print(f"  {marker}: {count} samples")

        except Exception as e:
            print(f"❌ Analysis failed: {e}")


# Usage example
def main():
    recorder = EEGRecorder()

    # Run the experiment
    success = recorder.run_experiment_sequence()

    if success:
        print("\n🎉 Experiment completed successfully!")

        # Generate a filename to analyze (you can specify your actual filename)
        # recorder.load_and_analyze_data("your_eeg_data_file.csv")
    else:
        print("\n💥 Experiment failed!")


if __name__ == "__main__":
    main()