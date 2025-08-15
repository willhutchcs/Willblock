from PIL import Image
import win32gui
import win32ui
import win32con
import ctypes
import vlc
import random
import torch
import time
from torchvision import models, transforms
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtWidgets import QApplication, QWidget
from OpenGL.GL import *
import torch.nn.functional as F
import threading
import sys
import keyboard
import pygetwindow as gw
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
from comtypes import CLSCTX_ALL

player = vlc.MediaPlayer("music.ogg")

# == Load Model ==
model = models.resnet18()
model.fc = torch.nn.Linear(model.fc.in_features, 2)  # Rebuild classifier
if torch.cuda.is_available():
    model.load_state_dict(torch.load("nba_vs_ad.pth"))
else:
    model.load_state_dict(torch.load("nba_vs_ad.pth", map_location=torch.device('cpu')))
    
model.eval()
transform = transforms.Compose([
    transforms.Resize((224, 224)),  # Resize to match model's input size
    transforms.ToTensor(),  # Convert to tensor)  # Normalize if needed
])

# === Get Screen Size ===
user32 = ctypes.windll.user32
screen_width = user32.GetSystemMetrics(0)
screen_height = user32.GetSystemMetrics(1)

# === Capture Window Function ===

def capture_window(window):
    hwnd = window._hWnd
    left, top, right, bottom = window.left, window.top, window.right, window.bottom
    width, height = right - left, bottom - top

    # Get window DC and memory DC
    hwndDC = win32gui.GetWindowDC(hwnd)
    mfcDC  = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()

    # Create bitmap
    saveBitMap = win32ui.CreateBitmap()
    saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
    saveDC.SelectObject(saveBitMap)

    # Copy window content to memory bitmap
    result = saveDC.BitBlt((0, 0), (width, height), mfcDC, (0, 0), win32con.SRCCOPY)

    # Convert to PIL image
    bmpinfo = saveBitMap.GetInfo()
    bmpstr = saveBitMap.GetBitmapBits(True)
    img = Image.frombuffer("RGB", (bmpinfo["bmWidth"], bmpinfo["bmHeight"]), bmpstr, "raw", "BGRX", 0, 1)

    # Clean up
    win32gui.DeleteObject(saveBitMap.GetHandle())
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)

    return img


# === Create Overlay Window First ===
class ImageOverlay(QWidget):
    def __init__(self, img_path=None, screen_index=0):
        super().__init__()

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_OpaquePaintEvent)  # Ensures transparent window works correctly

        # Make the window transparent to input (no mouse or keyboard events)
        self.setWindowFlag(Qt.WindowTransparentForInput)

        self.image_path = img_path
        self.image = None
        if img_path:
            self.image = Image.open(img_path).convert("RGBA")

        # Get the screen geometry for the specified screen index
        desktop = QApplication.desktop()
        screen_geometry = desktop.screenGeometry(screen_index)
        self.setGeometry(screen_geometry)  # Set the overlay to cover the screen

        # Resize the image to fit the screen resolution
        if self.image:
            self.image = self.image.resize((screen_geometry.width(), screen_geometry.height()))

        self.visible = False

    def paintEvent(self, event):
        if self.visible and self.image:
            painter = QPainter(self)
            img_data = QImage(self.image.tobytes(), self.image.width, self.image.height, QImage.Format_RGBA8888)
            painter.drawImage(0, 0, img_data)
            painter.end()

    def show_overlay(self):
        if not self.visible:
            self.visible = True
            self.show()

    def hide_overlay(self):
        if self.visible:
            self.visible = False
            self.hide()

app = QApplication(sys.argv)

# === Load Image ===
IMAGE_PATH = "overlay.jpg"
overlay = ImageOverlay(IMAGE_PATH)

def listen_for_keys():
    while True:
        if keyboard.is_pressed('esc'):
            overrideOn()
            time.sleep(0.3)  # debounce
        elif keyboard.is_pressed('q'):
            overrideOff()
            time.sleep(0.3)

def mute_app(app_name, mute=True):
    sessions = AudioUtilities.GetAllSessions()
    for session in sessions:
        if session.Process and session.Process.name().lower() == app_name.lower():
            volume = session._ctl.QueryInterface(ISimpleAudioVolume)
            volume.SetMute(mute, None)
            return
    print(f"App not found: {app_name}")

def overrideOn(event=None):
    QTimer.singleShot(0, overlay.hide_overlay)
    stop_event.set()
    start_event.clear()
    print("Manual Override ON")
    mute_app("firefox.exe", mute=False)
    global override
    override = True

def overrideOff(event=None):
    print("Manual Override OFF")
    global override
    override = False

def overlayMusic():
    start_event.set()
    player.audio_set_volume(80)
    player.play()
    player.set_time(random.randint(0, 6000) * 1000)
    while not stop_event.is_set():
        time.sleep(0.2)
    player.stop()

def checkScreen():
    try:
        scs = capture_window(firefox_window)
        scs = scs.convert("RGB")
        scs.save("test_scs.jpg")
        img_tensor = transform(scs)
        img_tensor = img_tensor.unsqueeze(0)
        with torch.no_grad():
            output = model(img_tensor)
            probabilities = F.softmax(output, dim=1)
            if probabilities.tolist()[0][0] > probabilities.tolist()[0][1]: # if it's an ad
                print("Ad detected with", int(probabilities.tolist()[0][0]*100), "% confidence")
                if not start_event.is_set():
                    thread = threading.Thread(target=overlayMusic)
                    stop_event.clear()
                    thread.start()
                    mute_app("firefox.exe", mute=True)
                    QTimer.singleShot(0, overlay.show_overlay)
            else:                                                                       # if it's not ad
                print("Game detected with", int(probabilities.tolist()[0][1]*100), "% confidence")
                if start_event.is_set():
                    start_event.clear()
                    stop_event.set()
                    mute_app("firefox.exe", mute=False)
                    # Ensure the music thread finishes before hiding the overlay
                    if 'thread' in locals() and thread.is_alive():
                        thread.join()
                    QTimer.singleShot(0, overlay.hide_overlay)
    except Exception as e:
        print(f"Error in checkScreen: {e}")

stop_event = threading.Event()
start_event = threading.Event()

thread = None # Initialize the thread variable

def start_checking():
    if not override:
        checkScreen()  # Run the screen check logic
    QTimer.singleShot(1000, start_checking)  # Schedule the next screen check after 1 second

threading.Thread(target=listen_for_keys, daemon=True).start()

firefox_window = None
windows = gw.getAllTitles()


for title in windows:
    if "Firefox" in title:
        try:
            firefox_window = gw.getWindowsWithTitle(title)[0]
            print(f"Found Firefox window: {title}")
            break
        except IndexError:
            print(f"Firefox window '{title}' not found.")
            sys.exit()
if firefox_window is None:
    print("Firefox window not found. Please make sure Firefox is open.")
    sys.exit()

mute_app("firefox.exe", mute=False)

override = False
def main():
    global overlay
    app = QApplication(sys.argv)

    # Start checking the screen every 1 second
    start_checking()

    # Set up the GUI to display overlay
    overlay.show()

    sys.exit(app.exec_())  # Start the event loop

if __name__ == "__main__":
    main()
