from pylsl import resolve_streams, StreamInlet
import time

print("=== Scanning for LSL Streams ===")
streams = resolve_streams()

print(f"Found {len(streams)} stream(s):")
for i, stream in enumerate(streams):
    print(f"{i + 1}. {stream.name()} (Type: {stream.type()}, Source: {stream.source_id()})")

# Look for EMOTIV stream
emotiv_streams = [s for s in streams if 'EMOTIV' in s.name() or 'EEG' in s.type()]
if emotiv_streams:
    print(f"\n✓ Found EMOTIV stream: {emotiv_streams[0].name()}")
    inlet = StreamInlet(emotiv_streams[0])
    print("Testing EEG data flow...")

    for i in range(5):  # Try to get 5 samples
        sample, timestamp = inlet.pull_sample(timeout=2.0)
        if sample:
            print(f"Sample {i + 1}: {len(sample)} channels, timestamp: {timestamp}")
        else:
            print(f"Sample {i + 1}: No data")
else:
    print("\n✗ No EMOTIV EEG stream detected")
    print("Make sure:")
    print("1. EMOTIV Pro is running")
    print("2. Headset is connected and getting signal")
    print("3. LSL Streaming is enabled in EMOTIV Pro")