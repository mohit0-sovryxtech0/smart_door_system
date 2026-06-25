# Refactor Plan: Face-Only Authentication with Simultaneous Entry/Exit

## Goal
Convert to face-only authentication with both entry (camera outside) and exit (ultrasonic inside) modes running simultaneously. Door unlocks on face match OR ultrasonic detection, auto-locks after 10 seconds.

## Key Issues Identified

### 1. Mode Selection (main.py)
- **Current**: Radio buttons toggle between Entry Mode and Exit Mode
- **Required**: Both sensors run simultaneously - camera checks for entry, ultrasonic checks for exit
- **Change**: Remove `_entry_mode` toggle, always run both checks in `_process_loop()`

### 2. Servo Vibration Issue (door_control.py)
- **Current**: RPi.GPIO path uses step-by-step rotation (lines 197-204) which can cause vibration/brrrr in middle positions
- **Required**: Direct stable movement from 0° to 90° and back without intermediate stops
- **Change**: Simplify `rotate_to()` to move directly to target angle

### 3. Syntax Error (enroll_user_gui.py:455)
- **Current**: `return True` followed by `# Get user details` comment breaks method indentation
- **Required**: Fix indentation to make code valid Python

## Changes Required

### 1. main.py
- [ ] Remove `_entry_mode` state variable (line 164)
- [ ] Remove radio button mode selection UI (lines 299-327)
- [ ] Remove `_on_mode_change()` method (lines 339-343)
- [ ] Modify `_process_loop()` to always check both face AND ultrasonic
- [ ] Remove `_process_exit_auth()` conditional logic - ultrasonic runs always
- [ ] Keep door auto-lock handling via DoorController's 10s timer

### 2. door_control.py (ServoController class)
- [ ] Remove step-by-step loop in `rotate_to()` lines 197-204
- [ ] For RPi.GPIO: Send direct PWM signal to target angle, no stepping
- [ ] Increase `_settle_delay` from 0.2s to 0.5s for stable positioning
- [ ] Remove pulse-width cycling that causes vibration

### 3. enroll_user_gui.py
- [ ] Fix indentation error at line 455 - restore proper method structure
- [ ] The `validate_selection()` method body is broken

## Technical Details

### Servo Movement Fix (door_control.py)
```python
def rotate_to(self, angle: float, step: float = 5.0, delay: float = 0.01):
    angle = max(min(angle, self.open_angle), self.closed_angle)
    self._current_angle = angle

    if self.simulation:
        logger.info(f"[SIM] Servo → {angle:.0f}°")
        return

    try:
        if GPIOZERO_AVAILABLE and self._servo is not None:
            self._servo.angle = angle
        elif RPI_GPIO_AVAILABLE and self._pwm is not None:
            # Direct movement - no stepping
            duty = self._angle_to_duty(angle, self.pwm_freq)
            self._pwm.ChangeDutyCycle(duty)
            # Hold signal for stability then stop to prevent buzz
            time.sleep(self._settle_delay)
            self._pwm.ChangeDutyCycle(0)
        # Longer settle delay for mechanical stability
        time.sleep(0.3)
    except Exception as e:
        logger.error(f"Servo move error: {e}")
```

### Main Loop Logic (main.py)
```python
def _process_loop(self):
    # ALWAYS run both entry and exit detection
    face_result = self.face_engine.process_frame()
    self._update_face_display(face_result)
    self._process_entry_auth(face_result)
    self._process_exit_auth()  # Unconditional
```

## Critical Design Decisions

1. **Entry vs Exit Detection**: Both run simultaneously, no mode toggle
   - Camera detects faces continuously (for entry)
   - Ultrasonic sensor detects proximity continuously (for exit)
   - Either trigger unlocks the door

2. **Door Lock Prevention**: When door is already unlocked, ignore subsequent triggers
   - Check `door_controller.is_locked()` before unlocking

3. **Servo Stability**: 
   - Move directly to target angle (no intermediate steps)
   - Stop PWM signal after reaching position to prevent motor buzz
   - Longer settle time (0.5s) before next movement

## Validation Steps
1. Run `python3 -m py_compile main.py enroll_user_gui.py modules/door_control.py` - all should pass
2. Test face recognition → door unlocks → auto-locks after 10s
3. Test ultrasonic detection → door unlocks → auto-locks after 10s  
4. Test both sensors work simultaneously without conflict
5. Verify no servo vibration when idle