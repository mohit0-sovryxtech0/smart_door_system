#!/usr/bin/env python3
"""
Facial Recognition Door Lock System
=====================================
Continuously monitors a camera feed, detects and recognises known faces,
and triggers a servo motor to open the door when a match is found.

Sequence
--------
1. Capture frame from camera
2. Detect face → encode → compare against database
3. If match found  →  rotate servo 90° (door opens)
4. After 10 seconds → rotate servo back 90° (door closes)

Hardware
--------
* USB webcam          →  /dev/video0  (or set CAMERA_INDEX in settings)
* SG90 / MG90S servo  →  GPIO 18 (BCM), PWM 50 Hz

Libraries
---------
* face_recognition  (dlib backend)
* opencv-python     (camera capture)
* gpiozero / RPi.GPIO (servo PWM)
* SQLite3           (face encoding database)

Usage
-----
    # Normal mode (real hardware)
    sudo python3 door_lock_controller.py

    # Simulation mode (no GPIO — prints servo moves instead)
    python3 door_lock_controller.py --simulation
"""

import sys
import time
import signal
import logging
import argparse
from pathlib import Path

# ── Project root on path ───────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── Configuration ─────────────────────────────────────────────────────────
from config.settings import (
    CAMERA_INDEX,
    FACE_RECOGNITION_TOLERANCE,
    FACE_DETECTION_MODEL,
    FACE_ENCODING_JITTERS,
    CONFIDENCE_THRESHOLD,
    DOOR_SERVO_PIN,
    DOOR_SERVO_OPEN_ANGLE,
    DOOR_SERVO_CLOSED_ANGLE,
    DOOR_UNLOCK_DURATION,
    DOOR_SERVO_PWM_FREQ,
)

# ── Project modules ───────────────────────────────────────────────────────
from modules.face_recognition_module import (
    FaceRecognitionEngine,
    FaceResult,
    FaceStatus,
)
from modules.door_control import DoorController, DoorState

# ── Logging setup ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("DoorLock")

# ── Graceful shutdown ──────────────────────────────────────────────────────
_running = True


def _graceful_exit(signum=None, _frame=None):
    """Handle Ctrl+C and SIGTERM so the servo always returns to closed."""
    global _running
    _running = False
    logger.info("Shutdown signal received — returning servo to closed position...")


signal.signal(signal.SIGINT,  _graceful_exit)
signal.signal(signal.SIGTERM, _graceful_exit)


# ==========================================================================
# DoorLockController
# ==========================================================================

class DoorLockController:
    """
    Core logic: face recognition engine + servo door controller.

    The servo rotates 90° clockwise when a valid face is matched,
    holds for DOOR_UNLOCK_DURATION seconds, then rotates 90° back.
    """

    def __init__(self, simulation: bool = False):
        self.simulation = simulation

        # ── Face recognition engine ─────────────────────────────────────
        logger.info("Initialising face recognition engine...")
        self.face_engine = FaceRecognitionEngine()
        if not self.face_engine.start():
            if self.simulation:
                logger.warning(
                    "Camera not available — running in camera-less simulation. "
                    "Face recognition will always return NO_FACE. "
                    "Connect a camera and re-run without --simulation to use real hardware."
                )
            else:
                raise RuntimeError(
                    "Failed to start face recognition engine — no camera found. "
                    "Check CAMERA_INDEX in config/settings.py and verify the camera is connected."
                )

        known = [u["name"] for u in self.face_engine._known_user_data]
        logger.info(f"Loaded {len(known)} known face(s): {', '.join(known)}")

        # ── Door / servo controller ─────────────────────────────────────
        logger.info("Initialising door controller (servo)...")
        self.door = DoorController(simulation=simulation)

        # ── State tracking ──────────────────────────────────────────────
        self._last_match_time = 0.0   # debounce: seconds since last unlock
        self._cooldown = 2.0          # minimum seconds between unlocks

    # ------------------------------------------------------------------ #

    def run(self) -> None:
        """
        Main loop — runs until SIGINT / SIGTERM or KeyboardInterrupt.

        Every cycle:
          1. Grab a frame
          2. Run face detection + recognition
          3. If matched AND door is locked AND cooldown passed → unlock
          4. Sleep briefly to keep CPU usage reasonable
        """
        logger.info("=" * 55)
        logger.info("       FACE RECOGNITION DOOR LOCK")
        logger.info("=" * 55)
        logger.info(f"  Camera index     : {CAMERA_INDEX}")
        logger.info(f"  Servo pin        : GPIO {DOOR_SERVO_PIN}")
        logger.info(f"  Open angle       : {DOOR_SERVO_OPEN_ANGLE}°")
        logger.info(f"  Closed angle     : {DOOR_SERVO_CLOSED_ANGLE}°")
        logger.info(f"  Auto-lock after  : {DOOR_UNLOCK_DURATION} s")
        logger.info(f"  Tolerance        : {FACE_RECOGNITION_TOLERANCE}")
        logger.info(f"  Confidence floor : {CONFIDENCE_THRESHOLD}")
        logger.info(f"  Detection model  : {FACE_DETECTION_MODEL}")
        logger.info(f"  Simulation mode  : {self.simulation}")
        logger.info("=" * 55)
        logger.info("Press Ctrl+C to stop.\n")

        cycle = 0

        while _running:
            try:
                self._process_cycle(cycle)
            except Exception as exc:
                logger.error(f"Cycle error: {exc}")

            cycle += 1
            time.sleep(0.1)          # ~10 FPS — gives the camera time to refresh

        self._shutdown()

    # ------------------------------------------------------------------ #

    def _process_cycle(self, cycle: int) -> None:
        """
        Single iteration of the main loop.
        """
        # ── 1. Capture + recognise ─────────────────────────────────────────
        result: FaceResult = self.face_engine.process_frame()
        status = result.status

        # ── 2. React based on recognition result ───────────────────────────
        if status == FaceStatus.FACE_MATCHED:
            self._handle_match(result)

        elif status == FaceStatus.FACE_DETECTED:
            # Face is in frame but not matched (unknown person)
            if cycle % 10 == 0:       # log every ~1 s to avoid spam
                logger.info(f"Unknown face detected (conf={result.confidence:.3f})")

        elif status == FaceStatus.NO_FACE:
                logger.info("No face detected — scanning...")

        elif status == FaceStatus.MULTIPLE_FACES:
            logger.warning("Multiple faces detected — ignoring for security")

        elif status == FaceStatus.CAMERA_ERROR:
            logger.error("Camera error — check connection")

    # ------------------------------------------------------------------ #

    def _handle_match(self, result: FaceResult) -> None:
        """
        Called when a known face is matched.
        Triggers the servo to open the door (if not already open).
        """
        # ── Cooldown guard: prevent the same person from re-triggering
        #    immediately after a previous unlock.
        now = time.time()
        elapsed = now - self._last_match_time
        if elapsed < self._cooldown:
            logger.debug(
                f"Match for {result.user_name} ignored — "
                f"cooldown active ({elapsed:.1f}s < {self._cooldown}s)"
            )
            return

        # ── Don't unlock an already-open door ─────────────────────────────
        if self.door.is_unlocked():
            logger.debug("Door already unlocked — skipping")
            return

        # ── Trigger unlock ────────────────────────────────────────────────
        confidence_pct = result.confidence * 100
        logger.info(
            f"MATCH: {result.user_name}  "
            f"(confidence {confidence_pct:.1f}%)  "
            f"→ OPENING DOOR"
        )

        self._last_match_time = now
        ok = self.door.unlock(
            duration=DOOR_UNLOCK_DURATION,
            reason=f"Face matched: {result.user_name}",
        )

        if not ok:
            logger.error("Failed to unlock door")

    # ------------------------------------------------------------------ #

    def _shutdown(self) -> None:
        """Ensure servo returns to closed position on exit."""
        logger.info("Shutting down...")
        self.door.cleanup()
        self.face_engine.stop()
        logger.info("Shutdown complete. Servo is in locked position.")


# ==========================================================================
# Entry point
# ==========================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Facial Recognition Door Lock System"
    )
    parser.add_argument(
        "--simulation", "-s",
        action="store_true",
        help="Run in simulation mode (no real GPIO — servo moves are logged only)",
    )
    args = parser.parse_args()

    try:
        controller = DoorLockController(simulation=args.simulation)
        controller.run()
    except RuntimeError as exc:
        logger.error(f"Startup failed: {exc}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")


if __name__ == "__main__":
    main()
