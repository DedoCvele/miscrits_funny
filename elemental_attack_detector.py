"""
Elemental Attack Detector
=========================
A GUI application that monitors the screen for elemental attack numbers (4 or 5)
and automatically clicks when detected.

Detection Methods:
1. Template Matching: Uses the provided reference images (check for 4.jpg, check for 5.png)
   to find matching patterns on the screen. This is the most accurate method.
2. OCR Fallback: If template matching doesn't work, uses Tesseract OCR to read numbers
   from specific screen regions.

Usage:
- Run the script and click "Elemental" button to start detection
- Press Ctrl+F to exit the program
- Use Settings button to configure threshold, click position, and other options
- Click "Set Click Position" to choose where to click when numbers are detected

Setup:
1. Install Python packages: pip install -r requirements.txt
2. Install Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki
3. Run: python elemental_attack_detector.py
"""

import tkinter as tk
from tkinter import ttk, messagebox
import pyautogui
import pytesseract
from PIL import Image, ImageGrab
import threading
import time
import keyboard
import numpy as np
import cv2
import os
import json

# Configure pyautogui
pyautogui.FAILSAFE = False

# Path to reference images
IMAGE_DIR = "image check"
# Templates for number 4
TEMPLATE_4_1 = os.path.join(IMAGE_DIR, "check for 4.jpg")
TEMPLATE_4_2 = os.path.join(IMAGE_DIR, "check for 4(1).png")
TEMPLATE_4_3 = os.path.join(IMAGE_DIR, "tulipini_4.png")
# Templates for number 5
TEMPLATE_5_1 = os.path.join(IMAGE_DIR, "check for 5.png")
TEMPLATE_5_2 = os.path.join(IMAGE_DIR, "check for 5 (2).png")
# Special instant-click template for number 4 (highest priority)
TEMPLATE_ONLY_4 = os.path.join(IMAGE_DIR, "only_4.png")
CONFIG_FILE = "detector_config.json"

class ElementalAttackDetector:
    def __init__(self, root):
        self.root = root
        self.root.title("Elemental Attack Detector")
        self.root.geometry("400x250")
        self.root.resizable(False, False)
        
        self.running = False
        self.paused = False
        self.detection_thread = None
        self.mode = None
        self.click_coordinates = None  # Will store where to click
        self.detection_region = None  # Will store (x, y, width, height) for detection area
        
        # Configuration settings
        self.match_threshold = 0.7
        self.click_cooldown = 1.0
        self.check_interval = 0.3
        
        # Load saved configuration
        self.load_config()
        
        # Load template images for matching (using lists to support multiple variants)
        self.templates_4 = []  # List of templates for number 4
        self.templates_5 = []  # List of templates for number 5
        self.template_only_4 = None  # Special instant-click template for number 4 (highest priority)
        self.load_templates()
        
        # Create UI
        self.create_ui()
        
        # Setup keyboard shortcut (Ctrl+F to exit)
        keyboard.add_hotkey('ctrl+f', self.stop_program)
        
    def load_config(self):
        """Load configuration from file"""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    self.match_threshold = config.get('match_threshold', 0.7)
                    self.click_cooldown = config.get('click_cooldown', 1.0)
                    self.check_interval = config.get('check_interval', 0.3)
                    click_pos = config.get('click_coordinates')
                    if click_pos:
                        self.click_coordinates = (click_pos[0], click_pos[1])
                    detection_reg = config.get('detection_region')
                    if detection_reg and len(detection_reg) == 4:
                        self.detection_region = tuple(detection_reg)  # (x, y, width, height)
        except Exception as e:
            print(f"Could not load config: {e}")
    
    def save_config(self):
        """Save configuration to file"""
        try:
            config = {
                'match_threshold': self.match_threshold,
                'click_cooldown': self.click_cooldown,
                'check_interval': self.check_interval,
                'click_coordinates': list(self.click_coordinates) if self.click_coordinates else None,
                'detection_region': list(self.detection_region) if self.detection_region else None
            }
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Could not save config: {e}")
    
    def load_templates(self):
        """Load the reference images for template matching"""
        try:
            # Load special instant-click template for number 4 (highest priority)
            if os.path.exists(TEMPLATE_ONLY_4):
                template = cv2.imread(TEMPLATE_ONLY_4, cv2.IMREAD_COLOR)
                if template is not None:
                    template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
                    self.template_only_4 = template
                    print(f"Loaded INSTANT-CLICK template: {os.path.basename(TEMPLATE_ONLY_4)}")
            
            # Load all templates for number 4
            for template_path in [TEMPLATE_4_1, TEMPLATE_4_2, TEMPLATE_4_3]:
                if os.path.exists(template_path):
                    template = cv2.imread(template_path, cv2.IMREAD_COLOR)
                    if template is not None:
                        template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
                        self.templates_4.append(template)
                        print(f"Loaded template for 4: {os.path.basename(template_path)}")
            
            # Load all templates for number 5
            for template_path in [TEMPLATE_5_1, TEMPLATE_5_2]:
                if os.path.exists(template_path):
                    template = cv2.imread(template_path, cv2.IMREAD_COLOR)
                    if template is not None:
                        template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
                        self.templates_5.append(template)
                        print(f"Loaded template for 5: {os.path.basename(template_path)}")
            
            total_templates = len(self.templates_4) + len(self.templates_5) + (1 if self.template_only_4 is not None else 0)
            print(f"Loaded {total_templates} templates total ({len(self.templates_4)} for 4, {len(self.templates_5)} for 5, {'1 instant-click' if self.template_only_4 is not None else '0 instant-click'})")
            
            if total_templates == 0:
                print("Warning: No template images loaded. Falling back to OCR-based detection")
        except Exception as e:
            print(f"Warning: Could not load template images: {e}")
            print("Falling back to OCR-based detection")
        
    def create_ui(self):
        title_label = tk.Label(self.root, text="Elemental Attack Detector", font=("Arial", 12, "bold"))
        title_label.pack(pady=5)
        
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)
        
        self.elemental_btn = tk.Button(
            button_frame, 
            text="Start Elemental", 
            width=15, 
            height=2,
            command=self.start_elemental,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 10)
        )
        self.elemental_btn.pack(side=tk.LEFT, padx=5)
        
        self.physical_btn = tk.Button(
            button_frame, 
            text="Start Physical", 
            width=15, 
            height=2,
            command=self.start_physical,
            bg="#2196F3",
            fg="white",
            font=("Arial", 10)
        )
        self.physical_btn.pack(side=tk.LEFT, padx=5)
        
        # Control buttons frame
        control_frame = tk.Frame(self.root)
        control_frame.pack(pady=5)
        
        self.pause_btn = tk.Button(
            control_frame,
            text="Pause",
            width=12,
            command=self.toggle_pause,
            bg="#FF9800",
            fg="white",
            font=("Arial", 9),
            state="disabled"
        )
        self.pause_btn.pack(side=tk.LEFT, padx=5)
        
        settings_btn = tk.Button(
            control_frame,
            text="Settings",
            width=12,
            command=self.open_settings,
            bg="#9E9E9E",
            fg="white",
            font=("Arial", 9)
        )
        settings_btn.pack(side=tk.LEFT, padx=5)
        
        self.status_label = tk.Label(self.root, text="Ready", fg="gray")
        self.status_label.pack(pady=5)
        
        # Click position info
        self.click_pos_label = tk.Label(
            self.root, 
            text="Click Position: Not set", 
            fg="gray", 
            font=("Arial", 8)
        )
        self.click_pos_label.pack(pady=2)
        if self.click_coordinates:
            self.click_pos_label.config(
                text=f"Click Position: ({self.click_coordinates[0]}, {self.click_coordinates[1]})",
                fg="green"
            )
        
        # Detection region info
        self.detection_region_label = tk.Label(
            self.root,
            text="Detection Region: Not set (using full screen)",
            fg="gray",
            font=("Arial", 8)
        )
        self.detection_region_label.pack(pady=2)
        if self.detection_region:
            x, y, w, h = self.detection_region
            self.detection_region_label.config(
                text=f"Detection Region: ({x}, {y}) - {w}x{h}",
                fg="green"
            )
        
        # Info label
        info_label = tk.Label(
            self.root, 
            text="Press Ctrl+F to exit | Settings to configure", 
            fg="gray", 
            font=("Arial", 7)
        )
        info_label.pack(pady=2)
        
    def start_elemental(self):
        if not self.running:
            self.running = True
            self.paused = False
            self.mode = "elemental"
            self.status_label.config(text="Elemental Mode: Running", fg="green")
            self.elemental_btn.config(state="disabled")
            self.physical_btn.config(state="disabled")
            self.pause_btn.config(state="normal", text="Pause")
            self.detection_thread = threading.Thread(target=self.detect_elemental, daemon=True)
            self.detection_thread.start()
            
    def start_physical(self):
        if not self.running:
            self.running = True
            self.paused = False
            self.mode = "physical"
            self.status_label.config(text="Physical Mode: Running", fg="blue")
            self.elemental_btn.config(state="disabled")
            self.physical_btn.config(state="disabled")
            self.pause_btn.config(state="normal", text="Pause")
            self.detection_thread = threading.Thread(target=self.detect_physical, daemon=True)
            self.detection_thread.start()
    
    def toggle_pause(self):
        """Pause or resume detection"""
        if self.running:
            self.paused = not self.paused
            if self.paused:
                self.pause_btn.config(text="Resume", bg="#4CAF50")
                self.status_label.config(text=f"{self.mode.capitalize()} Mode: Paused", fg="orange")
            else:
                self.pause_btn.config(text="Pause", bg="#FF9800")
                self.status_label.config(text=f"{self.mode.capitalize()} Mode: Running", 
                                       fg="green" if self.mode == "elemental" else "blue")
    
    def open_settings(self):
        """Open settings window"""
        if self.running:
            messagebox.showwarning("Settings", "Please stop detection before changing settings.")
            return
        
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Settings")
        settings_window.geometry("450x550")
        settings_window.resizable(False, False)
        
        # Match threshold
        tk.Label(settings_window, text="Match Threshold (0.0 - 1.0)", font=("Arial", 10)).pack(pady=5)
        threshold_frame = tk.Frame(settings_window)
        threshold_frame.pack(pady=5)
        
        self.threshold_var = tk.DoubleVar(value=self.match_threshold)
        threshold_scale = tk.Scale(
            threshold_frame,
            from_=0.0,
            to=1.0,
            resolution=0.01,
            orient=tk.HORIZONTAL,
            length=300,
            variable=self.threshold_var
        )
        threshold_scale.pack(side=tk.LEFT)
        threshold_label = tk.Label(threshold_frame, textvariable=self.threshold_var, width=5)
        threshold_label.pack(side=tk.LEFT, padx=5)
        
        tk.Label(settings_window, text="Higher = more strict matching (0.65-0.75 recommended)", fg="gray", font=("Arial", 8)).pack()
        tk.Label(settings_window, text="Tip: Using a detection region improves speed and confidence!", fg="blue", font=("Arial", 8, "italic")).pack()
        
        # Click cooldown
        tk.Label(settings_window, text="Click Cooldown (seconds)", font=("Arial", 10)).pack(pady=(15, 5))
        cooldown_frame = tk.Frame(settings_window)
        cooldown_frame.pack(pady=5)
        
        self.cooldown_var = tk.DoubleVar(value=self.click_cooldown)
        cooldown_scale = tk.Scale(
            cooldown_frame,
            from_=0.1,
            to=5.0,
            resolution=0.1,
            orient=tk.HORIZONTAL,
            length=300,
            variable=self.cooldown_var
        )
        cooldown_scale.pack(side=tk.LEFT)
        cooldown_label = tk.Label(cooldown_frame, textvariable=self.cooldown_var, width=5)
        cooldown_label.pack(side=tk.LEFT, padx=5)
        
        # Check interval
        tk.Label(settings_window, text="Check Interval (seconds)", font=("Arial", 10)).pack(pady=(15, 5))
        interval_frame = tk.Frame(settings_window)
        interval_frame.pack(pady=5)
        
        self.interval_var = tk.DoubleVar(value=self.check_interval)
        interval_scale = tk.Scale(
            interval_frame,
            from_=0.1,
            to=2.0,
            resolution=0.1,
            orient=tk.HORIZONTAL,
            length=300,
            variable=self.interval_var
        )
        interval_scale.pack(side=tk.LEFT)
        interval_label = tk.Label(interval_frame, textvariable=self.interval_var, width=5)
        interval_label.pack(side=tk.LEFT, padx=5)
        
        # Click position
        click_pos_frame = tk.Frame(settings_window)
        click_pos_frame.pack(pady=15)
        
        tk.Label(click_pos_frame, text="Click Position:", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        if self.click_coordinates:
            pos_text = f"({self.click_coordinates[0]}, {self.click_coordinates[1]})"
        else:
            pos_text = "Not set"
        pos_label = tk.Label(click_pos_frame, text=pos_text, fg="blue", font=("Arial", 9))
        pos_label.pack(side=tk.LEFT, padx=5)
        
        def set_click_position():
            settings_window.withdraw()  # Hide settings window
            
            # Create countdown window
            countdown_window = tk.Toplevel()
            countdown_window.title("Set Click Position")
            countdown_window.geometry("400x150")
            countdown_window.attributes('-topmost', True)
            
            countdown_label = tk.Label(
                countdown_window,
                text="Move your mouse to the target position...",
                font=("Arial", 12)
            )
            countdown_label.pack(pady=20)
            
            time_label = tk.Label(
                countdown_window,
                text="",
                font=("Arial", 16, "bold"),
                fg="red"
            )
            time_label.pack(pady=10)
            
            def countdown(seconds):
                if seconds > 0:
                    time_label.config(text=f"Capturing in {seconds}...")
                    countdown_window.after(1000, lambda: countdown(seconds - 1))
                else:
                    x, y = pyautogui.position()
                    self.click_coordinates = (x, y)
                    pos_label.config(text=f"({x}, {y})", fg="green")
                    self.click_pos_label.config(
                        text=f"Click Position: ({x}, {y})",
                        fg="green"
                    )
                    countdown_window.destroy()
                    messagebox.showinfo("Success", f"Click position set to ({x}, {y})")
                    settings_window.deiconify()
            
            countdown(3)  # 3 second countdown
        
        set_pos_btn = tk.Button(
            click_pos_frame,
            text="Set Position",
            command=set_click_position,
            bg="#2196F3",
            fg="white"
        )
        set_pos_btn.pack(side=tk.LEFT, padx=5)
        
        # Detection region
        detection_region_frame = tk.Frame(settings_window)
        detection_region_frame.pack(pady=15)
        
        tk.Label(detection_region_frame, text="Detection Region:", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        if self.detection_region:
            x, y, w, h = self.detection_region
            region_text = f"({x}, {y}) - {w}x{h}"
        else:
            region_text = "Not set (using full screen)"
        region_label = tk.Label(detection_region_frame, text=region_text, fg="blue", font=("Arial", 9))
        region_label.pack(side=tk.LEFT, padx=5)
        
        def set_detection_region():
            settings_window.withdraw()  # Hide settings window
            
            # Step 1: Get top-left corner
            step1_window = tk.Toplevel()
            step1_window.title("Set Detection Region - Step 1/2")
            step1_window.geometry("450x180")
            step1_window.attributes('-topmost', True)
            
            step1_label = tk.Label(
                step1_window,
                text="Step 1: Move mouse to TOP-LEFT corner of detection area",
                font=("Arial", 12, "bold")
            )
            step1_label.pack(pady=20)
            
            time_label1 = tk.Label(
                step1_window,
                text="",
                font=("Arial", 16, "bold"),
                fg="red"
            )
            time_label1.pack(pady=10)
            
            top_left = [None, None]
            
            def countdown1(seconds):
                if seconds > 0:
                    time_label1.config(text=f"Capturing in {seconds}...")
                    step1_window.after(1000, lambda: countdown1(seconds - 1))
                else:
                    x, y = pyautogui.position()
                    top_left[0], top_left[1] = x, y
                    step1_window.destroy()
                    
                    # Step 2: Get bottom-right corner
                    step2_window = tk.Toplevel()
                    step2_window.title("Set Detection Region - Step 2/2")
                    step2_window.geometry("450x180")
                    step2_window.attributes('-topmost', True)
                    
                    step2_label = tk.Label(
                        step2_window,
                        text="Step 2: Move mouse to BOTTOM-RIGHT corner of detection area",
                        font=("Arial", 12, "bold")
                    )
                    step2_label.pack(pady=20)
                    
                    time_label2 = tk.Label(
                        step2_window,
                        text="",
                        font=("Arial", 16, "bold"),
                        fg="red"
                    )
                    time_label2.pack(pady=10)
                    
                    def countdown2(seconds):
                        if seconds > 0:
                            time_label2.config(text=f"Capturing in {seconds}...")
                            step2_window.after(1000, lambda: countdown2(seconds - 1))
                        else:
                            x2, y2 = pyautogui.position()
                            # Calculate region: ensure x2 > x1 and y2 > y1
                            x1, y1 = min(top_left[0], x2), min(top_left[1], y2)
                            x2, y2 = max(top_left[0], x2), max(top_left[1], y2)
                            width = x2 - x1
                            height = y2 - y1
                            
                            if width > 0 and height > 0:
                                self.detection_region = (x1, y1, width, height)
                                region_label.config(text=f"({x1}, {y1}) - {width}x{height}", fg="green")
                                self.detection_region_label.config(
                                    text=f"Detection Region: ({x1}, {y1}) - {width}x{height}",
                                    fg="green"
                                )
                                step2_window.destroy()
                                messagebox.showinfo("Success", f"Detection region set: ({x1}, {y1}) - {width}x{height}")
                                settings_window.deiconify()
                            else:
                                step2_window.destroy()
                                messagebox.showerror("Error", "Invalid region! Please select two different corners.")
                                settings_window.deiconify()
                    
                    countdown2(3)
            
            countdown1(3)
        
        set_region_btn = tk.Button(
            detection_region_frame,
            text="Set Region",
            command=set_detection_region,
            bg="#9C27B0",
            fg="white"
        )
        set_region_btn.pack(side=tk.LEFT, padx=5)
        
        # Info about detection region
        tk.Label(
            settings_window,
            text="⚠ Set a smaller region for faster detection and higher accuracy",
            fg="orange",
            font=("Arial", 8)
        ).pack(pady=5)
        
        # Buttons
        button_frame = tk.Frame(settings_window)
        button_frame.pack(pady=20)
        
        def save_settings():
            self.match_threshold = self.threshold_var.get()
            self.click_cooldown = self.cooldown_var.get()
            self.check_interval = self.interval_var.get()
            self.save_config()
            messagebox.showinfo("Settings", "Settings saved successfully!")
            settings_window.destroy()
        
        save_btn = tk.Button(
            button_frame,
            text="Save",
            command=save_settings,
            bg="#4CAF50",
            fg="white",
            width=12
        )
        save_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = tk.Button(
            button_frame,
            text="Cancel",
            command=settings_window.destroy,
            bg="#f44336",
            fg="white",
            width=12
        )
        cancel_btn.pack(side=tk.LEFT, padx=5)
            
    def stop_program(self):
        self.running = False
        self.save_config()  # Save before exiting
        self.root.quit()
        self.root.destroy()
        
    def detect_elemental(self):
        """
        Detects if the elemental attack number is 4 or 5 and clicks if found.
        Uses template matching first, falls back to OCR if templates aren't available.
        """
        detection_count = 0
        last_click_time = 0
        
        while self.running:
            # Skip detection if paused
            if self.paused:
                time.sleep(0.5)
                continue
                
            try:
                current_time = time.time()
                
                # Capture the screen (full screen or region if specified)
                if self.detection_region:
                    x, y, w, h = self.detection_region
                    # Grab only the specified region for faster processing
                    screenshot = ImageGrab.grab(bbox=(x, y, x + w, y + h))
                    offset_x, offset_y = x, y  # Store offset to adjust click coordinates later
                else:
                    screenshot = ImageGrab.grab()
                    offset_x, offset_y = 0, 0
                
                screenshot_np = np.array(screenshot)
                screenshot_cv = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)
                gray = cv2.cvtColor(screenshot_cv, cv2.COLOR_BGR2GRAY)
                
                detected = False
                click_x, click_y = None, None
                detected_number = None
                confidence = 0.0
                
                # Method 1: Template Matching (more accurate if templates are loaded)
                # Check for only_4.png FIRST (highest priority)
                if self.template_only_4 is not None:
                    result_only_4 = cv2.matchTemplate(gray, self.template_only_4, cv2.TM_CCOEFF_NORMED)
                    _, max_val_only_4, _, max_loc_only_4 = cv2.minMaxLoc(result_only_4)
                    
                    if max_val_only_4 >= self.match_threshold:
                        detected = True
                        detected_number = 4
                        confidence = max_val_only_4
                        print(f"Detected only_4.png with confidence: {max_val_only_4:.2f}")
                        # Adjust coordinates if using detection region
                        click_x = max_loc_only_4[0] + self.template_only_4.shape[1] // 2 + offset_x
                        click_y = max_loc_only_4[1] + self.template_only_4.shape[0] // 2 + offset_y
                
                # Check for number 5 (second priority)
                if not detected and len(self.templates_5) > 0:
                    for template_5 in self.templates_5:
                        result_5 = cv2.matchTemplate(gray, template_5, cv2.TM_CCOEFF_NORMED)
                        _, max_val_5, _, max_loc_5 = cv2.minMaxLoc(result_5)
                        
                        if max_val_5 >= self.match_threshold:
                            detected = True
                            detected_number = 5
                            confidence = max_val_5
                            print(f"Detected number 5 with confidence: {max_val_5:.2f}")
                            # Adjust coordinates if using detection region
                            click_x = max_loc_5[0] + template_5.shape[1] // 2 + offset_x
                            click_y = max_loc_5[1] + template_5.shape[0] // 2 + offset_y
                            break  # Stop after first match
                
                # Only check templates for number 4 if we didn't find a 5
                if not detected and len(self.templates_4) > 0:
                    best_match_4 = None
                    best_conf_4 = 0.0
                    best_loc_4 = None
                    high_confidence_threshold = 0.9  # Stop early if we find a very confident match
                    
                    for template_4 in self.templates_4:
                        result_4 = cv2.matchTemplate(gray, template_4, cv2.TM_CCOEFF_NORMED)
                        _, max_val_4, _, max_loc_4 = cv2.minMaxLoc(result_4)
                        
                        if max_val_4 > best_conf_4:
                            best_conf_4 = max_val_4
                            best_loc_4 = max_loc_4
                            best_match_4 = template_4
                            
                            # Early exit if we found a very high confidence match
                            if best_conf_4 >= high_confidence_threshold:
                                break
                    
                    if best_conf_4 >= self.match_threshold:
                        detected = True
                        detected_number = 4
                        confidence = best_conf_4
                        print(f"Detected number 4 with confidence: {best_conf_4:.2f}")
                        # Adjust coordinates if using detection region
                        click_x = best_loc_4[0] + best_match_4.shape[1] // 2 + offset_x
                        click_y = best_loc_4[1] + best_match_4.shape[0] // 2 + offset_y
                
                # Method 2: OCR fallback (if template matching fails or templates not available)
                if not detected:
                    try:
                        # Crop a region where the number likely appears
                        # Adjust these coordinates based on where the number appears on your screen
                        screen_width, screen_height = gray.shape[1], gray.shape[0]
                        
                        # Try multiple regions - adjust these based on your game UI
                        regions_to_check = [
                            # (x, y, width, height) - adjust these coordinates
                            (screen_width // 2, screen_height // 2 - 100, 200, 100),
                            (screen_width - 300, screen_height // 2 - 100, 250, 150),
                        ]
                        
                        for x, y, w, h in regions_to_check:
                            # Ensure coordinates are within bounds
                            x = max(0, min(x, screen_width - w))
                            y = max(0, min(y, screen_height - h))
                            region = gray[y:y+h, x:x+w]
                            
                            # Use OCR on this region
                            custom_config = r'--oem 3 --psm 10 -c tessedit_char_whitelist=0123456789'
                            text = pytesseract.image_to_string(region, config=custom_config)
                            
                            # Look for numbers 4 or 5
                            for char in text.strip():
                                if char == '4' or char == '5':
                                    detected = True
                                    detected_number = int(char)
                                    print(f"Detected number {char} via OCR in region ({x}, {y})")
                                    # Adjust coordinates if using detection region
                                    click_x = x + w // 2 + offset_x
                                    click_y = y + h // 2 + offset_y
                                    break
                            
                            if detected:
                                break
                    except Exception as ocr_error:
                        pass  # OCR failed, continue with next check
                
                # Perform click if detected and cooldown has passed
                if detected and (current_time - last_click_time) >= self.click_cooldown and click_x and click_y:
                    detection_count += 1
                    print(f"Clicking at ({click_x}, {click_y}) - Detection #{detection_count} (Number {detected_number})")
                    
                    # Click at detected location or use stored click coordinates
                    if self.click_coordinates:
                        pyautogui.click(self.click_coordinates[0], self.click_coordinates[1])
                        click_info = f"Clicked at ({self.click_coordinates[0]}, {self.click_coordinates[1]})"
                    else:
                        # Click at the center of detected number, or adjust to click on attack button
                        pyautogui.click(click_x, click_y)
                        click_info = f"Clicked at ({click_x}, {click_y})"
                    
                    last_click_time = current_time
                    count = detection_count  # Capture for lambda
                    conf_str = f" ({confidence:.2f})" if confidence > 0 else ""
                    self.root.after(0, lambda c=count, n=detected_number, info=click_info: self.status_label.config(
                        text=f"Elemental: Clicked! #{c} (Number {n}){conf_str}", fg="green"
                    ))
                    
            except Exception as e:
                print(f"Error in detection: {e}")
                import traceback
                traceback.print_exc()
                
            time.sleep(self.check_interval)  # Check at configured interval
            
    def detect_physical(self):
        """
        Placeholder for physical attack detection
        Similar logic can be implemented here
        """
        while self.running:
            # Skip detection if paused
            if self.paused:
                time.sleep(0.5)
                continue
            # Implement physical attack detection logic here
            time.sleep(self.check_interval)

if __name__ == "__main__":
    root = tk.Tk()
    app = ElementalAttackDetector(root)
    root.mainloop()

