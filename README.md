# PrintQueuesk

A self-service print kiosk application that enables users to upload documents and pay for printing services using bills and coins.

## Overview

PrintQueuesk is a fullscreen kiosk application built with Python and Tkinter that provides an intuitive interface for document printing services. Users can upload files via QR code scanning or local hotspot, configure print options, and pay using bills or coins through an Arduino-based payment system with automatic change dispensing.

## Features

### Document Upload
- **QR Code Scanning**: Users scan a QR code to access the web upload portal
- **Hotspot Mode**: Direct file transfer via local WiFi hotspot connection
- **Supported Formats**: PDF, DOCX files

### Print Configuration
- **Page Selection**: Print all pages or specify a custom page range
- **Color Options**: Choose between colored or black & white printing
- **Paper Sizes**: Support for A4 and Letter size paper
- **Multiple Copies**: Print multiple copies of the document
- **Live Preview**: Real-time document preview with page navigation

### Payment System
- **Bill & Coin Acceptor**: Arduino-based payment system accepts both bills and coins
- **Automatic Change Dispensing**: Returns excess payment automatically
- **Real-time Balance Display**: Shows inserted amount and remaining balance
- **Transaction Timeout**: Auto-cancellation after idle period

### Additional Features
- **Firebase Integration**: Real-time job tracking and status updates
- **Automatic File Cleanup**: Removes temporary files after 5 minutes
- **Idle Screen Carousel**: Displays promotional images when inactive
- **Low Paper/Ink Alerts**: Warns users when supplies are running low
- **Fullscreen Kiosk Mode**: Locked fullscreen interface for public use

## Project Structure

```
PrintQueuesk/
├── main_app.py              # Main application entry point
├── config/
│   ├── arduino_config.py    # Arduino bill/coin acceptor configuration
│   ├── database_utils.py    # Database utilities
│   ├── firebase_config.py   # Firebase configuration
│   ├── hotspot_config.py    # WiFi hotspot settings
│   └── print_config.py      # Printer configuration
├── screens/
│   ├── home_screen.py       # Home/Welcome screen with QR code
│   ├── hotspot_screen.py    # Hotspot file transfer screen
│   ├── options_screen.py    # Print configuration screen
│   ├── summary_screen.py    # Order summary screen
│   └── payment_screen.py    # Payment processing screen
├── static/
│   ├── css/                 # Stylesheets for web interface
│   ├── img/                 # Images and icons
│   └── js/                  # JavaScript files
├── templates/               # HTML templates for web upload
└── dist/
    └── PrintQueuesk.exe     # Compiled executable
```

## Requirements

- Python 3.10+
- Windows OS (for printing functionality)
- Arduino with bill/coin acceptor module
- Network connection for Firebase sync

## Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure Firebase:
   - Place your `firebase_service_account.json` in the `config/` folder

3. Run the application:
   ```bash
   python main_app.py
   ```

   Or use the pre-built executable:
   ```
   dist/PrintQueuesk.exe
   ```

## Dependencies

- Flask & Flask-SocketIO (web server)
- Firebase Admin SDK (database)
- PyMuPDF (PDF rendering)
- python-docx & docx2pdf (Word document support)
- Pillow (image processing)
- pyserial (Arduino communication)
- pywin32 (Windows printing)

## Building the Executable

To create a standalone executable:

```bash
pip install pyinstaller
pyinstaller --clean main_app.spec
```

The executable will be created in the `dist/` folder.

## License

© 2025 PrintQueuesk. All rights reserved.