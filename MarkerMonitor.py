from pylsl import StreamInlet, resolve_streams
import time

print("=== LSL Marker Monitor ===")
print("This will scan for streams without hanging...")

# Use resolve_streams() with a timeout approach
max_wait_time = 10  # Maximum seconds to wait for stream
start_time = time.time()

while time.time() - start_time < max_wait_time:
    try:
        # Get all available streams (this doesn't hang)
        all_streams = resolve_streams()

        # Look for our specific stream
        target_stream = None
        for stream in all_streams:
            print(f"Found stream: {stream.name()} (type: {stream.type()})")
            if stream.name() == 'MotorImageryMarkers':
                target_stream = stream
                break

        if target_stream:
            print(f"\n✓ SUCCESS! Connected to: {target_stream.name()}")
            inlet = StreamInlet(target_stream)

            print("Waiting for markers... (Press Ctrl+C to stop)")
            print("=" * 50)

            try:
                while True:
                    sample, timestamp = inlet.pull_sample(timeout=1.0)
                    if sample:
                        print(f"🎯 [{time.strftime('%H:%M:%S')}] {sample[0]}")
                    else:
                        # Show we're still alive but waiting
                        print(".", end="", flush=True)
            except KeyboardInterrupt:
                print("\n\nMonitoring stopped by user.")
                break

        else:
            print(
                f"MotorImageryMarkers not found yet... ({int(max_wait_time - (time.time() - start_time))}s remaining)")
            time.sleep(2)

    except Exception as e:
        print(f"Error: {e}")
        break

if time.time() - start_time >= max_wait_time:
    print(f"\n✗ Timeout: Could not find MotorImageryMarkers stream after {max_wait_time} seconds")
    print("\nTroubleshooting tips:")
    print("1. Make sure main.py is running and sending markers")
    print("2. Check if Windows Firewall is blocking LSL")
    print("3. Try running as Administrator")
    print("4. Make sure both programs are on the same computer")