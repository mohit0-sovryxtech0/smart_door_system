# Smart Door Security System

An IoT-enabled door security system using face recognition for entry authentication and ultrasonic proximity sensor for exit.

## Features

- **Face Recognition Entry**: Camera mounted outside door recognizes enrolled users for access
- **Ultrasonic Exit**: Proximity sensor inside door triggers automatic exit unlock
- **Real-time GUI**: Live camera preview with door state and auto-lock countdown
- **Admin Web Dashboard**: User management, access logs, and system statistics
- **Auto-lock Door**: Automatically relocks after 10 seconds
- **Secure by Design**: Hashed passwords, encoded biometrics (not raw images), secure APIs
- **24/7 Operation**: Designed for continuous operation with error handling and recovery

## System Requirements

- Python 3.8 or higher
- Webcam (for face recognition)
- HC-SR04 Ultrasonic sensor for exit mode
- Servo motor for door lock
- Windows/Linux/Raspberry Pi

## Installation

### 1. Clone or download the project

```bash
cd smart_door_system
```

### 2. Create virtual environment (recommended)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt

**Note for Windows users**: Installing `face-recognition` may require Visual Studio Build Tools. If you encounter errors, install CMake and dlib first:

```bash
pip install cmake
pip install dlib
pip install face-recognition
```

### 4. Initialize the database

The database is automatically created on first run. A default admin user is created:
- **Username**: `admin`
- **Password**: `admin12`

## Running the System

### Start the Main Application (GUI)

```bash
# Normal mode (requires camera and sensors)
python main.py

# Simulation mode (no hardware required)
python main.py --simulation
```

### Start the Web Admin Dashboard

```bash
# Run the web server
python web/app.py

# Access the dashboard at http://localhost:5000
```

### Run Both (Recommended for Production)

Open two terminals:

**Terminal 1 - Main Application:**
```bash
python main.py --simulation
```

**Terminal 2 - Web Dashboard:**
```bash
python web/app.py
```

## User Enrollment

### Step 1: Add user via Web Dashboard

1. Open http://localhost:5000
2. Login with admin credentials
3. Go to Users → Add User
4. Fill in employee details

### Step 2: Enroll face via command line

```bash
# List all users
python enroll_user.py --list

# Enroll face for user ID 1
python enroll_user.py --user 1 --face
```

Fingerprint enrollment is coming soon in a future update.

## How It Works

- **Entry Mode**: Camera detects faces. If a recognized face is matched, the door unlocks for 10 seconds then auto-locks.
- **Exit Mode**: Ultrasonic sensor detects a person within 5cm. Door unlocks for 10 seconds then auto-locks.

## Project Structure

```
smart_door_system/
├── main.py                 # Main application with GUI
├── enroll_user.py          # User enrollment script
├── requirements.txt        # Python dependencies
├── README.md               # This file
│
├── config/
│   └── settings.py         # Configuration settings
│
├── database/
│   ├── schema.sql          # SQL database schema
│   └── db_manager.py       # Database operations
│
├── modules/
│   ├── __init__.py
│   ├── face_recognition_module.py  # Face detection & matching
│   ├── fingerprint_module.py       # Fingerprint sensor interface
│   ├── door_control.py             # Door relay control
│   └── auth_engine.py              # Multi-factor auth logic
│
├── web/
│   ├── app.py              # Flask web application
│   ├── templates/          # HTML templates
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── dashboard.html
│   │   ├── users.html
│   │   ├── user_form.html
│   │   ├── logs.html
│   │   └── error.html
│   └── static/
│       ├── css/style.css   # Stylesheets
│       └── js/main.js      # JavaScript
│
├── logs/                   # System logs
├── enrollments/            # Enrollment data
└── database/
    └── smart_door.db       # SQLite database (created on first run)
```

## Configuration

Edit `config/settings.py` to customize:

```python
# Camera settings
CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480

# Face recognition
FACE_RECOGNITION_TOLERANCE = 0.6  # Lower = stricter

# Door settings
DOOR_UNLOCK_DURATION = 10  # seconds

# Web server
WEB_HOST = "127.0.0.1"
WEB_PORT = 5000
```

## Hardware Setup (for Production)

### Servo Motor (for door lock)
- Signal → GPIO 18 (PWM pin)
- VCC → 5V
- GND → Ground

### Ultrasonic Sensor (HC-SR04)
- VCC → 5V
- Trig → GPIO 23
- Echo → GPIO 24
- GND → Ground

## Security Features

1. **Password Hashing**: Admin passwords hashed with bcrypt
2. **Biometric Security**: Face encodings stored, not raw images
3. **Access Logging**: All attempts logged with timestamps

## API Endpoints

### Authentication Required
- `GET /api/users` - List all users
- `GET /api/users/<id>` - Get user details
- `POST /api/users` - Create user
- `PUT /api/users/<id>` - Update user
- `DELETE /api/users/<id>` - Delete user
- `POST /api/users/<id>/toggle` - Enable/disable user
- `GET /api/logs` - Get access logs
- `GET /api/logs/stats` - Get statistics

### Public (for main.py integration)
- `POST /api/validate` - Validate user for authentication
- `POST /api/log_access` - Log access attempt

## Troubleshooting

### Camera not working
- Check if another application is using the camera
- Try changing `CAMERA_INDEX` in settings

### Face recognition slow
- Change `FACE_DETECTION_MODEL` from "cnn" to "hog" in settings
- Reduce `CAMERA_WIDTH` and `CAMERA_HEIGHT`

### Fingerprint sensor not connecting
- Check the COM port in settings
- Ensure proper driver installation
- Use `--simulation` mode for testing

### Database errors
- Delete `database/smart_door.db` to reset
- Run the application to recreate

## License

This project is for educational purposes (Final Year Project).

## Authors

- Smart Door Security System Development Team
- Co-Authored-By: Warp mohitstha29@gmail.com
