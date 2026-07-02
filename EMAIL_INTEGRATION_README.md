# Email Notification Feature Integration

## Overview
An email notification feature has been integrated into the Smart Door System. This feature automatically sends a security alert email when an unknown face is detected 4 consecutive times by the camera. 

## Configuration Details

The email sending configuration is exclusively managed from the codebase and is not exposed in the web application for security reasons.

### Hardcoded Sender Credentials
The system uses Gmail SMTP to send emails. The sender account credentials have been securely hardcoded using a Google App Password.

The exact credentials placed in the system are:
- **SMTP_USERNAME**: `facialrecognitionandattendance@gmail.com`
- **SMTP_PASSWORD**: `awky zocc uvnq qzrd` (Google App Password)
- **SMTP_SERVER**: `smtp.gmail.com`
- **SMTP_PORT**: `587`

These values are defined in `config/settings.py`.

### Receiver Email Address
The receiver email address (the person who will receive the alerts) has a default fallback in the code:
- **EMAIL_RECIPIENT**: `[EMAIL_ADDRESS]`

**Note**: While the sender settings are hardcoded in the Python configuration files, the **Alert Receiver Email** can still be modified directly from the Web Application's admin settings page (`http://127.0.0.1:5000/settings`).

## Detection Rules
- **Threshold**: An alert is triggered only when an unknown face is detected **4 consecutive times** (`UNKNOWN_FACE_EMAIL_THRESHOLD = 4`).
- **Cooldown**: To prevent spamming, the system waits for a cooldown period (default: **60 seconds**) after sending an email before it will send another one (`EMAIL_COOLDOWN = 60`).

## Files Modified
1. **`config/settings.py`**: Added the email configuration constants (including the hardcoded SMTP Username and Google App Password).
2. **`modules/email_notifier.py`**: Added the logic to handle consecutive unknown face detections, manage cooldowns, and dispatch the email securely using Python's `smtplib`.
3. **`web/app.py`**: Ensured that the settings route only handles the admin profile and receiver email, discarding the sender settings from the database.
4. **`web/templates/settings.html`**: Completely removed the UI fields for the Sender Email and Google App Password, keeping only the Alert Receiver Email input field.
