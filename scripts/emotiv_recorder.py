import threading
import pandas as pd
from datetime import datetime
import pylsl


class EEGDataCollector:
    """
    Passive EEG data collector that listens to EEG and Marker streams.
    Does NOT control the experiment - just records what it receives.
    """

    def __init__(self):
        self.eeg_data = []  # Stores EEG samples with timestamps
        self.marker_events = []  # Stores marker events with timestamps
        self.is_recording = False
        self.recording_thread = None
        self.eeg_inlet = None
        self.marker_inlet = None

    def connect(self):
        """Connect to EEG and Marker streams"""
        try:
            # Connect to EEG stream
            print("🔍 Looking for EEG stream...")
            eeg_streams = pylsl.resolve_byprop('type', 'EEG', timeout=10)
            if not eeg_streams:
                raise Exception("No EEG stream found")

            self.eeg_inlet = pylsl.StreamInlet(eeg_streams[0])
            print(f"✓ Connected to EEG: {eeg_streams[0].name()}")

            # Connect to Marker stream
            print("🔍 Looking for Marker stream...")
            marker_streams = pylsl.resolve_byprop('type', 'Markers', timeout=10)
            if not marker_streams:
                raise Exception("No Marker stream found")

            self.marker_inlet = pylsl.StreamInlet(marker_streams[0])
            print(f"✓ Connected to Markers: {marker_streams[0].name()}")

            return True

        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False

    def start_recording(self):
        """Start recording EEG and markers"""
        if self.is_recording:
            print("⚠️ Already recording")
            return

        self.is_recording = True
        self.eeg_data = []
        self.marker_events = []
        self.recording_thread = threading.Thread(target=self._record_continuous)
        self.recording_thread.daemon = True
        self.recording_thread.start()
        print("🎯 Started recording - listening for EEG and markers...")

    def stop_recording(self):
        """Stop recording"""
        if not self.is_recording:
            return

        self.is_recording = False
        if self.recording_thread:
            self.recording_thread.join(timeout=2)
        print(f"⏹️ Stopped recording")
        print(f"   Collected {len(self.eeg_data)} EEG samples")
        print(f"   Collected {len(self.marker_events)} marker events")

    def _record_continuous(self):
        """
        Main recording loop - collects EEG and markers with LSL timestamps.
        Runs in background thread.
        """
        sample_count = 0
        last_marker = None

        while self.is_recording:
            try:
                # Pull EEG sample (blocking with short timeout)
                eeg_sample, eeg_timestamp = self.eeg_inlet.pull_sample(timeout=0.01)

                if eeg_sample:
                    self.eeg_data.append({
                        'timestamp': eeg_timestamp,
                        'channels': eeg_sample,
                        'sample_id': sample_count
                    })
                    sample_count += 1

                # Pull ALL available marker samples (non-blocking)
                # Important: pull ALL markers, so we don't miss any
                while True:
                    marker_sample, marker_timestamp = self.marker_inlet.pull_sample(timeout=0.0)
                    if marker_sample is None:
                        break

                    marker_label = marker_sample[0]
                    self.marker_events.append({
                        'timestamp': marker_timestamp,
                        'marker': marker_label
                    })

                    # Only print if it's a new marker (avoid spam)
                    if marker_label != last_marker:
                        print(f"📍 Marker: '{marker_label}' at LSL time {marker_timestamp:.3f}")
                        last_marker = marker_label

            except Exception as e:
                print(f"❌ Recording error: {e}")
                break

    def align_markers_to_eeg(self):
        """
        Align markers to EEG samples based on LSL timestamps.
        For each EEG sample, find the most recent marker that occurred before it.
        """
        if not self.eeg_data:
            print("❌ No EEG data to align")
            return []

        if not self.marker_events:
            print("⚠️ No markers found - all samples will be labeled 'none'")
            # Return EEG data with 'none' markers
            return [{
                'timestamp': sample['timestamp'],
                'marker': 'none',
                'channels': sample['channels'],
                'sample_id': sample['sample_id']
            } for sample in self.eeg_data]

        print(f"\n🔄 Aligning {len(self.marker_events)} markers to {len(self.eeg_data)} EEG samples...")

        # Sort markers by timestamp (should already be sorted, but just in case)
        sorted_markers = sorted(self.marker_events, key=lambda x: x['timestamp'])

        # Print marker timeline
        print("\n📋 Marker Timeline:")
        for i, m in enumerate(sorted_markers):
            print(f"   {i + 1}. {m['marker']} at {m['timestamp']:.3f}")

        # Assign markers to EEG samples
        aligned_data = []
        marker_idx = 0

        for eeg_sample in self.eeg_data:
            eeg_time = eeg_sample['timestamp']

            # Find the most recent marker before or at this EEG timestamp
            while (marker_idx < len(sorted_markers) - 1 and
                   sorted_markers[marker_idx + 1]['timestamp'] <= eeg_time):
                marker_idx += 1

            # Assign marker if we found one before this sample
            if marker_idx < len(sorted_markers) and sorted_markers[marker_idx]['timestamp'] <= eeg_time:
                current_marker = sorted_markers[marker_idx]['marker']
            else:
                current_marker = 'none'

            aligned_data.append({
                'timestamp': eeg_time,
                'marker': current_marker,
                'channels': eeg_sample['channels'],
                'sample_id': eeg_sample['sample_id']
            })

        return aligned_data

    def save_data(self, filename=None):
        """Save aligned data to CSV"""
        if not self.eeg_data:
            print("❌ No data to save")
            return None

        # Align markers to EEG
        aligned_data = self.align_markers_to_eeg()

        if not aligned_data:
            print("❌ No aligned data to save")
            return None

        # Generate filename
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"eeg_data_{timestamp}.csv"

        try:
            # Create column names for all channels
            num_channels = len(aligned_data[0]['channels'])
            channel_names = [f'CH{i + 1}' for i in range(num_channels)]

            # Prepare data for DataFrame
            rows = []
            for sample in aligned_data:
                row = {
                    'timestamp': sample['timestamp'],
                    'marker': sample['marker'],
                    'sample_id': sample['sample_id']
                }
                # Add channel data
                for i, ch_name in enumerate(channel_names):
                    row[ch_name] = sample['channels'][i]
                rows.append(row)

            # Create DataFrame and save
            df = pd.DataFrame(rows)
            df.to_csv(filename, index=False)

            print(f"\n💾 Saved {len(df)} samples to {filename}")

            # Print statistics
            self._print_statistics(df)

            return filename

        except Exception as e:
            print(f"❌ Save failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _print_statistics(self, df):
        """Print detailed statistics about the recorded data"""
        print(f"\n📊 RECORDING STATISTICS:")
        print("=" * 60)

        # Timing info
        duration = df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]
        sample_rate = len(df) / duration if duration > 0 else 0

        print(f"⏱️  Timing:")
        print(f"   First sample: {df['timestamp'].iloc[0]:.3f}")
        print(f"   Last sample:  {df['timestamp'].iloc[-1]:.3f}")
        print(f"   Duration:     {duration:.2f} seconds")
        print(f"   Sample rate:  ~{sample_rate:.1f} Hz")

        # Marker distribution
        print(f"\n🏷️  Marker Distribution:")
        marker_counts = df['marker'].value_counts().sort_index()
        total_samples = len(df)

        for marker, count in marker_counts.items():
            percentage = (count / total_samples) * 100
            duration_sec = count / sample_rate if sample_rate > 0 else 0
            print(f"   {marker:30s}: {count:5d} samples ({percentage:5.1f}%) ~{duration_sec:.1f}s")

        # Task analysis
        print(f"\n📈 Task Analysis:")
        task_types = {}
        for marker in marker_counts.index:
            if marker != 'none':
                # Extract task type (e.g., "clench_left_hand_start" -> "clench_left_hand")
                if '_start' in marker or '_end' in marker:
                    task_base = marker.replace('_start', '').replace('_end', '')
                    if task_base not in task_types:
                        task_types[task_base] = 0
                    task_types[task_base] += marker_counts[marker]

        for task, count in sorted(task_types.items()):
            percentage = (count / total_samples) * 100
            print(f"   {task:30s}: {count:5d} samples ({percentage:5.1f}%)")


def main():
    """
    Main function - run the data collector.
    This should be run ALONGSIDE your GUI, not instead of it.

    Usage:
    1. Start this script first
    2. Then start your GUI
    3. Run your experiment in the GUI
    4. Press Enter here when experiment is complete
    5. Data will be saved automatically
    """
    collector = EEGDataCollector()

    print("=" * 60)
    print("EEG DATA COLLECTOR")
    print("=" * 60)
    print("\nThis collector listens passively to EEG and Marker streams.")
    print("Make sure your EEG device is streaming before continuing.\n")

    # Connect to streams
    if not collector.connect():
        print("\n❌ Failed to connect to streams. Exiting.")
        return

    print("\n✓ Connected successfully!")
    print("\nNow you can start your GUI and run the experiment.")
    print("This collector will record everything automatically.\n")

    # Start recording
    collector.start_recording()

    try:
        # Wait for user to stop
        input("Press ENTER when experiment is complete to stop recording and save data...\n")

    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")

    finally:
        # Stop recording
        collector.stop_recording()

        # Save data
        print("\n💾 Saving data...")
        filename = collector.save_data()

        if filename:
            print(f"\n✅ SUCCESS! Data saved to: {filename}")
        else:
            print("\n❌ Failed to save data")


if __name__ == "__main__":
    main()
