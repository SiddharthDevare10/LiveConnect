# LiveConnect

**LiveConnect** is a real-time video streaming and chat web application that allows users to create or join private rooms with synchronized video playback and secure access.

---

## Features

- User authentication (login & registration)
- Create or join private rooms with Room ID & PIN
- Real-time synchronized video streaming from host to all participants
- Live chat with usernames displayed alongside messages
- Access control to ensure only logged-in users can join rooms
- Separate frontend (HTML/CSS/JavaScript) and backend (Python Flask)
- Temporary deployment using Ngrok for easy sharing/testing

---

## Prerequisites

- Python 3.x installed
- pip 
- Ngrok (optional, for exposing local server)

---

## Installation and Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/YOUR_USERNAME/LiveConnect.git
   cd LiveConnect

2. **Install dependencies**

    ```bash
    pip install -r requirements.txt

4. **Run the application**

    ```bash
    python app.py

5. **(Optional) Expose the app publicly with Ngrok**

    Download and install ngrok from https://ngrok.com/.

    ```bash
    ngrok http 5000
