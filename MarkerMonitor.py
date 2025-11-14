from pylsl import StreamInlet, resolve_byprop
import time

print("Looking for MotorImageryMarkers stream...")

streams = resolve_byprop('name', 'MotorImageryMarkers', timeout=5)

if streams:
    inlet = StreamInlet(streams[0])
    print(f"✓ Connected to: {streams[0].name()}")
    print("Waiting for markers...\n" + "=" * 50)

    while True:
        sample, timestamp = inlet.pull_sample(timeout=1.0)
        if sample:
            print(f"Marker: {sample[0]} | Time: {timestamp:.3f}")
else:
    print("✗ No MotorImageryMarkers stream found!")
