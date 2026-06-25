"""
Smart Door Security System - Authentication Engine
Implements face-only authentication. For entry: face recognition unlocks door.
For exit: ultrasonic proximity sensor triggers unlock (handled in main.py).
"""

import threading
import logging
import time
from typing import Optional, Callable
from enum import Enum
from dataclasses import dataclass, field
import sys
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import AUTH_TIMEOUT
from database.db_manager import AccessLogRepository, UserRepository, SystemLogRepository

from modules.face_recognition_module import (
    FaceRecognitionEngine, FaceResult, FaceStatus
)
from modules.door_control import DoorController, DoorState

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AuthState(Enum):
    """Authentication state machine states."""
    IDLE = "Waiting for Authentication"
    FACE_DETECTED = "Face Detected - Verifying..."
    FACE_MATCHED = "Face Matched"
    ACCESS_GRANTED = "ACCESS GRANTED"
    ACCESS_DENIED = "ACCESS DENIED"
    TIMEOUT = "Authentication Timeout"
    ERROR = "Authentication Error"


@dataclass
class AuthSession:
    """Represents an authentication session."""
    state: AuthState = AuthState.IDLE
    face_result: Optional[FaceResult] = None
    matched_user_id: Optional[int] = None
    matched_user_name: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    failure_reason: Optional[str] = None
    confidence: float = 0.0


class AuthenticationEngine:
    """
    Face-only authentication engine.
    Access granted when:
    1. Face matches a registered user
    2. User is active in the database
    """

    def __init__(self, simulation: bool = False):
        self.simulation = simulation

        # Initialize components
        self.face_engine = FaceRecognitionEngine()
        self.door_controller = DoorController(simulation=simulation)

        # Repositories
        self.access_log = AccessLogRepository()
        self.user_repo = UserRepository()
        self.system_log = SystemLogRepository()

        # Authentication state
        self._current_session: Optional[AuthSession] = None
        self._session_lock = threading.Lock()
        self._running = False
        self._auth_thread: Optional[threading.Thread] = None

        # Callbacks
        self._state_callbacks: list = []
        self._result_callbacks: list = []

        # Configuration
        self.auth_timeout = AUTH_TIMEOUT

    def add_state_callback(self, callback: Callable[[AuthSession], None]):
        """Add callback for authentication state changes."""
        if callback not in self._state_callbacks:
            self._state_callbacks.append(callback)

    def remove_state_callback(self, callback: Callable[[AuthSession], None]):
        """Remove state callback."""
        if callback in self._state_callbacks:
            self._state_callbacks.remove(callback)

    def add_result_callback(self, callback: Callable[[AuthSession], None]):
        """Add callback for authentication results (success/failure)."""
        if callback not in self._result_callbacks:
            self._result_callbacks.append(callback)

    def _notify_state_change(self, session: AuthSession):
        """Notify all state callbacks."""
        for callback in self._state_callbacks:
            try:
                callback(session)
            except Exception as e:
                logger.error(f"State callback error: {e}")

    def _notify_result(self, session: AuthSession):
        """Notify all result callbacks."""
        for callback in self._result_callbacks:
            try:
                callback(session)
            except Exception as e:
                logger.error(f"Result callback error: {e}")

    def start(self) -> bool:
        """Start the authentication engine."""
        logger.info("Starting authentication engine...")

        # Start face recognition
        if not self.face_engine.start():
            logger.error("Failed to start face recognition")
            self.system_log.error("AuthEngine", "Failed to start face recognition")
            return False

        self._running = True
        self._current_session = AuthSession()

        # Start authentication loop
        self._auth_thread = threading.Thread(target=self._auth_loop, daemon=True)
        self._auth_thread.start()

        logger.info("Authentication engine started")
        self.system_log.info("AuthEngine", "Authentication engine started")
        return True

    def stop(self):
        """Stop the authentication engine."""
        self._running = False

        if self._auth_thread:
            self._auth_thread.join(timeout=3.0)

        self.face_engine.stop()
        self.door_controller.cleanup()

        logger.info("Authentication engine stopped")
        self.system_log.info("AuthEngine", "Authentication engine stopped")

    def _auth_loop(self):
        """Main authentication loop."""
        while self._running:
            try:
                with self._session_lock:
                    if self._current_session is None:
                        self._current_session = AuthSession()

                    session = self._current_session

                # Check for timeout
                if session.state not in [AuthState.IDLE, AuthState.ACCESS_GRANTED, AuthState.ACCESS_DENIED]:
                    elapsed = time.time() - session.start_time
                    if elapsed > self.auth_timeout:
                        self._handle_timeout(session)
                        continue

                # State machine
                if session.state == AuthState.IDLE:
                    self._process_face_detection(session)

                elif session.state in [AuthState.ACCESS_GRANTED, AuthState.ACCESS_DENIED]:
                    # Wait before resetting
                    time.sleep(2)
                    self._reset_session()

                time.sleep(0.05)  # Small delay to prevent CPU spinning

            except Exception as e:
                logger.error(f"Auth loop error: {e}")
                self.system_log.error("AuthEngine", f"Auth loop error: {str(e)}")
                time.sleep(1)

    def _process_face_detection(self, session: AuthSession):
        """Process face detection in idle state."""
        face_result = self.face_engine.process_frame()

        if face_result.status == FaceStatus.FACE_MATCHED:
            # Face matched - verify user is active
            user = self.user_repo.get_by_id(face_result.user_id)

            if user and user.get('is_active', False):
                session.state = AuthState.ACCESS_GRANTED
                session.face_result = face_result
                session.matched_user_id = face_result.user_id
                session.matched_user_name = f"{user['first_name']} {user['last_name']}"
                session.confidence = face_result.confidence
                session.start_time = time.time()

                self._grant_access(session, user)
            else:
                session.state = AuthState.ACCESS_DENIED
                session.failure_reason = "User account disabled"
                session.start_time = time.time()
                self._notify_state_change(session)

    def _grant_access(self, session: AuthSession, user: dict):
        """Grant access to authenticated user."""
        # Unlock door
        self.door_controller.unlock(
            reason=f"Authenticated: {session.matched_user_name}"
        )

        # Log access
        self.access_log.log_access(
            user_id=session.matched_user_id,
            event_type='ENTRY',
            result='SUCCESS',
            face_match=True,
            fingerprint_match=False,
            confidence_score=session.confidence
        )

        logger.info(f"ACCESS GRANTED: {session.matched_user_name}")
        self.system_log.info(
            "AuthEngine",
            f"Access granted to {session.matched_user_name}",
            f"Confidence: {session.confidence:.2f}"
        )

        self._notify_state_change(session)
        self._notify_result(session)

    def _deny_access(self, session: AuthSession, reason: str):
        """Deny access."""
        session.state = AuthState.ACCESS_DENIED
        session.failure_reason = reason
        session.end_time = time.time()

        # Ensure door is locked
        self.door_controller.lock(reason="Access denied")

        # Log failure
        self.access_log.log_access(
            user_id=session.face_result.user_id if session.face_result else None,
            event_type='ENTRY',
            result='DENIED',
            face_match=session.face_result is not None and
                      session.face_result.status == FaceStatus.FACE_MATCHED,
            fingerprint_match=False,
            failure_reason=reason
        )

        logger.warning(f"ACCESS DENIED: {reason}")
        self.system_log.warning("AuthEngine", f"Access denied: {reason}")

        self._notify_state_change(session)
        self._notify_result(session)

    def _handle_timeout(self, session: AuthSession):
        """Handle authentication timeout."""
        session.state = AuthState.TIMEOUT
        session.failure_reason = "Authentication timeout"
        session.end_time = time.time()

        # Log timeout
        self.access_log.log_access(
            user_id=session.face_result.user_id if session.face_result else None,
            event_type='ENTRY',
            result='FAILED',
            face_match=session.face_result is not None,
            fingerprint_match=False,
            failure_reason="Timeout"
        )

        logger.warning("Authentication timeout")
        self.system_log.warning("AuthEngine", "Authentication timeout")

        self._notify_state_change(session)
        self._notify_result(session)

        # Reset after brief delay
        time.sleep(2)
        self._reset_session()

    def _reset_session(self):
        """Reset authentication session."""
        with self._session_lock:
            self._current_session = AuthSession()
            self._notify_state_change(self._current_session)

    def get_current_session(self) -> AuthSession:
        """Get current authentication session."""
        with self._session_lock:
            if self._current_session is None:
                self._current_session = AuthSession()
            return self._current_session

    def get_face_frame(self):
        """Get current camera frame for display."""
        return self.face_engine.get_current_frame()

    def process_face(self) -> FaceResult:
        """Process a single frame for face detection."""
        return self.face_engine.process_frame()

    def cancel_authentication(self):
        """Cancel current authentication attempt."""
        with self._session_lock:
            if self._current_session and self._current_session.state not in [
                AuthState.IDLE, AuthState.ACCESS_GRANTED, AuthState.ACCESS_DENIED
            ]:
                self._current_session.state = AuthState.ACCESS_DENIED
                self._current_session.failure_reason = "Cancelled"
                self._notify_state_change(self._current_session)

        self._reset_session()


# Convenience function
def get_auth_engine(simulation: bool = False) -> AuthenticationEngine:
    """Get or create the authentication engine."""
    return AuthenticationEngine(simulation=simulation)