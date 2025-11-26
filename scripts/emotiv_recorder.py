import time
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
        self.channel_labels = []
        self.num_eeg_channels = 32  # Default: Only save first 32 channels (actual EEG)
        self.recording_start_time = None  # Wall clock time when recording starts
        self.first_sample_lsl_time = None  # LSL time of first sample
        self.channel_labels = []
        self.num_eeg_channels = 32  # Default: Only save first 32 channels (actual EEG)

    def connect(self):
        """Connect to EEG and Marker streams"""
        try:
            # Connect to EEG stream
            print("🔍 Looking for EEG stream...")
            eeg_streams = pylsl.resolve_byprop('type', 'EEG', timeout=10)
            if not eeg_streams:
                raise Exception("No EEG stream found")

            self.eeg_inlet = pylsl.StreamInlet(eeg_streams[0])
            stream_info = eeg_streams[0]

            # Get channel information
            total_channels = stream_info.channel_count()
            print(f"✓ Connected to EEG: {stream_info.name()}")
            print(f"   Total channels in stream: {total_channels}")

            # Get channel labels if available
            self.channel_labels = []
            xml_info = stream_info.desc().child("channels").first_child()
            while not xml_info.empty():
                label = xml_info.child_value("label")
                if label:
                    self.channel_labels.append(label)
                xml_info = xml_info.next_sibling()

            if self.channel_labels:
                print(f"   Channel labels: {', '.join(self.channel_labels[:5])}... (showing first 5)")
            else:
                print(f"   No channel labels found, will use CH1-CH{total_channels}")

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
        Records EEG data and preserves marker transitions
        """
        sample_count = 0
        current_marker = "no_marker"
        session_stop_time = None
        grace_period = 2.0
        experiment_start_time = None
        pending_markers = []  # Queue of markers waiting to be applied

        while self.is_recording:
            try:
                # Collect ALL new markers
                while True:
                    marker_sample, marker_timestamp = self.marker_inlet.pull_sample(timeout=0.0)
                    if marker_sample is None:
                        break

                    new_marker = marker_sample[0]
                    pending_markers.append((new_marker, marker_timestamp))

                    # Store marker event
                    self.marker_events.append({
                        'timestamp': marker_timestamp,
                        'marker': new_marker,
                        'relative_time': marker_timestamp - (experiment_start_time or marker_timestamp)
                    })

                    print(f"📍 RECEIVED: '{new_marker}' at LSL time {marker_timestamp:.3f}")

                    # Set experiment start time
                    if experiment_start_time is None and new_marker != "session_stop":
                        experiment_start_time = marker_timestamp
                        print(f"⏰ Experiment started at LSL time: {experiment_start_time:.3f}")

                    # Auto-stop detection
                    if new_marker in ['session_stop', 'session_complete']:
                        if session_stop_time is None:
                            session_stop_time = time.time()
                            print(f"\n⏰ Session end detected! Will auto-stop in {grace_period} seconds...")

                # Process EEG samples
                eeg_sample, eeg_timestamp = self.eeg_inlet.pull_sample(timeout=0.01)
                if eeg_sample is not None:
                    eeg_channels_only = eeg_sample[:self.num_eeg_channels]

                    # Calculate relative time
                    if experiment_start_time is not None:
                        relative_time = eeg_timestamp - experiment_start_time
                    else:
                        relative_time = 0.0

                    # Apply any pending markers to this sample
                    if pending_markers:
                        # Use the most recent pending marker
                        current_marker, marker_time = pending_markers[-1]
                        # Keep other markers in queue for future samples?
                        # For now, we'll use the most recent one

                    self.eeg_data.append({
                        'timestamp': eeg_timestamp,
                        'relative_time': relative_time,
                        'channels': eeg_channels_only,
                        'sample_id': sample_count,
                        'marker': current_marker
                    })
                    sample_count += 1

                # Check if we should auto-stop
                if session_stop_time and (time.time() - session_stop_time) >= grace_period:
                    print(f"✓ Grace period complete. Auto-stopping...")
                    self.is_recording = False
                    break

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

        print(f"🔄 Using pre-aligned markers from {len(self.eeg_data)} EEG samples")

        # Return EEG data with markers already assigned
        return [{
            'timestamp': sample['timestamp'],
            'relative_time': sample.get('relative_time', 0),
            'marker': sample.get('marker', 'none'),
            'channels': sample['channels'],
            'sample_id': sample['sample_id']
        } for sample in self.eeg_data]

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
            # Create column names for EEG channels
            num_channels = len(aligned_data[0]['channels'])

            # Use actual channel labels if available, otherwise use CH1, CH2, etc.
            if self.channel_labels and len(self.channel_labels) >= num_channels:
                channel_names = self.channel_labels[:num_channels]
            else:
                channel_names = [f'CH{i + 1}' for i in range(num_channels)]

            print(f"📊 Saving {num_channels} EEG channels: {', '.join(channel_names[:5])}... (showing first 5)")

            # Prepare data for DataFrame
            rows = []
            for sample in aligned_data:
                row = {
                    'timestamp': sample['timestamp'],
                    'relative_time': sample['relative_time'],
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
    4. Collector will AUTO-STOP 2 seconds after seeing 'session_stop'
       (Or press Enter to stop manually)
    5. Data will be saved automatically
    """
    collector = EEGDataCollector()

    print("=" * 60)
    print("EEG DATA COLLECTOR (with Auto-Stop)")
    print("=" * 60)
    print("\nThis collector listens passively to EEG and Marker streams.")
    print("Make sure your EEG device is streaming before continuing.\n")

    # Connect to streams
    if not collector.connect():
        print("\n❌ Failed to connect to streams. Exiting.")
        return

    print("\n✓ Connected successfully!")
    print("\nNow you can start your GUI and run the experiment.")
    print("This collector will:")
    print("  - Record everything automatically")
    print("  - AUTO-STOP 2 seconds after 'session_stop' marker")
    print("  - Or press ENTER anytime to stop manually\n")

    # Start recording
    collector.start_recording()

    try:
        # Wait for user to stop OR auto-stop
        print("🎙️ Recording... (waiting for session_stop or manual stop)\n")

        # Monitor for auto-stop
        while collector.is_recording:
            time.sleep(0.1)

        print("\n✓ Recording stopped")

    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
        collector.stop_recording()

    finally:
        # Make sure recording is stopped
        if collector.is_recording:
            collector.stop_recording()

        # Save data
        print("\n💾 Saving data...")
        filename = collector.save_data()

        if filename:
            print(f"\n✅ SUCCESS! Data saved to: {filename}")
            print("\nYou can now close this window.")
        else:
            print("\n❌ Failed to save data")


if __name__ == "__main__":
    main()