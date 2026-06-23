"""Simple servo test utility.

Run this on the target device to verify servo control and DoorController behavior.

Usage:
  python3 diagnostics/servo_test.py --duration 5

The script will instantiate the `DoorController`, print whether it's running
in simulation mode, perform an unlock for the requested duration, and print
status updates.
"""

import time
import argparse
from modules.door_control import DoorController


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--duration', type=float, default=5.0, help='Unlock duration in seconds')
    args = parser.parse_args()

    ctrl = DoorController()

    sim = getattr(ctrl, '_servo_ctrl', None) and getattr(ctrl._servo_ctrl, 'simulation', True)
    print(f"DoorController simulation mode: {sim}")
    print(f"Initial state: {ctrl.get_state().value}")

    print(f"Unlocking for {args.duration} seconds...")
    ok = ctrl.unlock(duration=args.duration, reason="Manual servo test")
    print("Unlock command sent, success=" + str(ok))

    # Poll status until it returns to locked or timeout
    deadline = time.time() + args.duration + 10
    while time.time() < deadline:
        status = ctrl.get_status()
        print(f"State={status.state.value} time_until_lock={status.time_until_lock:.1f}s")
        if status.state.name == 'LOCKED':
            print("Door returned to LOCKED state")
            break
        time.sleep(1)

    print("Test complete. Cleaning up controller.")
    ctrl.cleanup()


if __name__ == '__main__':
    main()
