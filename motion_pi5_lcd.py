#!/usr/bin/env python3
from picamera2 import Picamera2, Preview
from picamera2.encoders import H264Encoder
import time, cv2, numpy as np, os
from RPLCD.i2c import CharLCD
from datetime import datetime
from libcamera import Transform
import signal
import sys

THRESHOLD = 300000

COOLDOWN_S     = 3
VIDEO_DURATION = 60

picam2     = Picamera2()


picam2.start_preview(
    Preview.QTGL,
    x=0, y=0,
    width=320, height=240
)

preview_cfg = picam2.create_preview_configuration(main={"size": (320, 240)},   transform=Transform(hflip=1, vflip=1))
picam2.configure(preview_cfg)
picam2.start()
time.sleep(2)   # let AE/WB settle

lcd = CharLCD('PCF8574', 0x27)
lcd.clear()
lcd.write_string("Scanning")
time.sleep(2)
lcd.clear()

def capture_gray():
    frame = picam2.capture_array("main")
    gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.GaussianBlur(gray, (21, 21), 0)

def cleanup_and_exit(signum=None, frame=None):
    print("Cleaning up resources...")
    try:
        picam2.stop_preview()
    except Exception as e:
        print("Error stopping preview:", e)
    try:
        picam2.close()
    except Exception as e:
        print("Error closing camera:", e)
    try:
        lcd.clear()
    except Exception as e:
        print("Error clearing LCD:", e)
    sys.exit(0)

prev = capture_gray()

video_cfg = picam2.create_video_configuration(
    main={"size": (1920, 1080),"format": "YUV420"},
    transform=Transform(hflip=1, vflip=1))
encoder   = H264Encoder(bitrate=3_000_000)

try:
    while True:
        time.sleep(1)
        gray  = capture_gray()

        if prev is None:
            prev = gray
   
        delta = cv2.absdiff(prev, gray)
        motion = np.sum(cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)[1])
        print("Motion level:", motion)

        if motion > THRESHOLD:
            now       = datetime.now()
            folder    = now.strftime("%Y/%m/%d")
            os.makedirs(f"/home/coreyMain1/Desktop/Camera/{folder}", exist_ok=True)
            path      = now.strftime(f"/home/coreyMain1/Desktop/Camera/{folder}/video_%Y%m%d_%H%M%S.h264")
            print("Motion detected—recording →", path)


            # Update LCD: recording
            lcd.clear()
            lcd.write_string("Now Recording")
                    
            # a) switch into video mode
            picam2.switch_mode(video_cfg) 

            # b) start recording
            picam2.start_recording(encoder, path)
            time.sleep(VIDEO_DURATION)
            picam2.stop_recording()

            # c) back to preview mode
            picam2.switch_mode(preview_cfg)  

            time.sleep(1) 

            prev = None
            time.sleep(COOLDOWN_S)
        else:
            prev = gray
            lcd.clear()
            lcd.write_string("Scanning")

finally:
    cleanup_and_exit()
