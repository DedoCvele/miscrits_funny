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

# Path to reference images (relative to script location)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ELEMENTAL_IMAGE_DIR = os.path.join(SCRIPT_DIR, "image check")
# Physical images are in parent directory
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
PHYSICAL_IMAGE_DIR = os.path.join(PARENT_DIR, "pysical_check")

# Elemental templates - priority 6, 5, 4
ELEMENTAL_6 = os.path.join(ELEMENTAL_IMAGE_DIR, "elemental_6.png")
ELEMENTAL_5 = os.path.join(ELEMENTAL_IMAGE_DIR, "elemental_5.jpg")
ELEMENTAL_4 = os.path.join(ELEMENTAL_IMAGE_DIR, "elemental_4.png")
# Physical templates - priority 6, 5, 4
PHYSICAL_6 = os.path.join(PHYSICAL_IMAGE_DIR, "pysical_6.jpg")
PHYSICAL_5 = os.path.join(PHYSICAL_IMAGE_DIR, "pysical_5.jpg")
PHYSICAL_4 = os.path.join(PHYSICAL_IMAGE_DIR, "pysical_4.png")
CONFIG_FILE = os.path.join(SCRIPT_DIR, "detector_config.json")

class ElementalAttackDetector:
    def __init__(self, root):
        self.root = root
        self.root.title("Elemental Attack Detector")
        self.root.geometry("400x380")
        self.root.resizable(False, False)
        
        self.running = False
        self.paused = False
        self.detection_thread = None
        self.mode = None
        self.click_coordinates = None  # Will store where to click
        self.elemental_detection_region = None  # Will store (x, y, width, height) for elemental detection area
        self.physical_detection_region = None  # Will store (x, y, width, height) for physical detection area
        
        # Feedback tracking
        self.last_detection = None  # Stores (number, mode, confidence, timestamp)
        self.feedback_data = []  # Stores feedback history
        
        # Configuration settings
        self.match_threshold = 0.7
        self.click_cooldown = 1.0
        self.check_interval = 0.3
        
        # Load saved configuration
        self.load_config()
        
        # Load template images for matching
        # Elemental templates - priority 6, 5, 4
        self.elemental_templates_6 = []
        self.elemental_templates_5 = []
        self.elemental_templates_4 = []
        # Physical templates - priority 6, 5, 4
        self.physical_templates_6 = []
        self.physical_templates_5 = []
        self.physical_templates_4 = []
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
                    # Load detection regions (support both old format and new format)
                    detection_reg = config.get('detection_region')  # Old format for backward compatibility
                    elemental_reg = config.get('elemental_detection_region')
                    physical_reg = config.get('physical_detection_region')
                    
                    if elemental_reg and len(elemental_reg) == 4:
                        self.elemental_detection_region = tuple(elemental_reg)
                    elif detection_reg and len(detection_reg) == 4:  # Backward compatibility
                        self.elemental_detection_region = tuple(detection_reg)
                    
                    if physical_reg and len(physical_reg) == 4:
                        self.physical_detection_region = tuple(physical_reg)
                    
                    # Load feedback data
                    self.feedback_data = config.get('feedback_data', [])
                    self.update_feedback_stats()
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
                    'elemental_detection_region': list(self.elemental_detection_region) if self.elemental_detection_region else None,
                    'physical_detection_region': list(self.physical_detection_region) if self.physical_detection_region else None,
                    'feedback_data': self.feedback_data
            }
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Could not save config: {e}")
    
    def load_templates(self):
        """Load the reference images for template matching"""
        try:
            # Load elemental templates - priority 6, 5, 4
            for template_path, template_list, num in [
                (ELEMENTAL_6, self.elemental_templates_6, 6),
                (ELEMENTAL_5, self.elemental_templates_5, 5),
                (ELEMENTAL_4, self.elemental_templates_4, 4)
            ]:
                if os.path.exists(template_path):
                    template = cv2.imread(template_path, cv2.IMREAD_COLOR)
                    if template is not None:
                        template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
                        template_list.append(template)
                        print(f"Loaded elemental template for {num}: {os.path.basename(template_path)}")
                else:
                    print(f"Warning: Elemental template not found: {template_path}")
            
            # Load physical templates - priority 6, 5, 4
            for template_path, template_list, num in [
                (PHYSICAL_6, self.physical_templates_6, 6),
                (PHYSICAL_5, self.physical_templates_5, 5),
                (PHYSICAL_4, self.physical_templates_4, 4)
            ]:
                if os.path.exists(template_path):
                    template = cv2.imread(template_path, cv2.IMREAD_COLOR)
                    if template is not None:
                        template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
                        template_list.append(template)
                        print(f"Loaded physical template for {num}: {os.path.basename(template_path)}")
                else:
                    print(f"Warning: Physical template not found: {template_path}")
            
            total_elemental = len(self.elemental_templates_6) + len(self.elemental_templates_5) + len(self.elemental_templates_4)
            total_physical = len(self.physical_templates_6) + len(self.physical_templates_5) + len(self.physical_templates_4)
            print(f"Loaded {total_elemental} elemental templates (6:{len(self.elemental_templates_6)}, 5:{len(self.elemental_templates_5)}, 4:{len(self.elemental_templates_4)})")
            print(f"Loaded {total_physical} physical templates (6:{len(self.physical_templates_6)}, 5:{len(self.physical_templates_5)}, 4:{len(self.physical_templates_4)})")
            
            if total_elemental == 0 and total_physical == 0:
                print("Warning: No template images loaded. Falling back to OCR-based detection")
        except Exception as e:
            print(f"Warning: Could not load template images: {e}")
            import traceback
            traceback.print_exc()
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
        
        self.stop_btn = tk.Button(
            control_frame,
            text="Stop",
            width=12,
            command=self.stop_detection,
            bg="#f44336",
            fg="white",
            font=("Arial", 9),
            state="disabled"
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
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
        
        # Feedback section
        feedback_frame = tk.Frame(self.root)
        feedback_frame.pack(pady=10)
        
        tk.Label(
            feedback_frame,
            text="Last Detection:",
            font=("Arial", 9, "bold")
        ).pack(side=tk.LEFT, padx=5)
        
        self.last_detection_label = tk.Label(
            feedback_frame,
            text="None",
            fg="gray",
            font=("Arial", 9)
        )
        self.last_detection_label.pack(side=tk.LEFT, padx=5)
        
        # Feedback buttons frame
        feedback_buttons_frame = tk.Frame(self.root)
        feedback_buttons_frame.pack(pady=5)
        
        self.good_btn = tk.Button(
            feedback_buttons_frame,
            text="✓ Good",
            width=10,
            command=self.feedback_good,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 9),
            state="disabled"
        )
        self.good_btn.pack(side=tk.LEFT, padx=5)
        
        self.bad_btn = tk.Button(
            feedback_buttons_frame,
            text="✗ Bad",
            width=10,
            command=self.feedback_bad,
            bg="#f44336",
            fg="white",
            font=("Arial", 9),
            state="disabled"
        )
        self.bad_btn.pack(side=tk.LEFT, padx=5)
        
        # Feedback stats label
        self.feedback_stats_label = tk.Label(
            self.root,
            text="Feedback: 0 good, 0 bad",
            fg="gray",
            font=("Arial", 7)
        )
        self.feedback_stats_label.pack(pady=2)
        
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
            text="Detection Regions: See Settings",
            fg="gray",
            font=("Arial", 8)
        )
        self.detection_region_label.pack(pady=2)
        self.update_detection_region_label()
        
        # Info label
        info_label = tk.Label(
            self.root, 
            text="Press Ctrl+F to exit | Settings to configure", 
            fg="gray", 
            font=("Arial", 7)
        )
        info_label.pack(pady=2)
    
    def update_detection_region_label(self):
        """Update the detection region label with current settings"""
        elemental_text = "Not set"
        physical_text = "Not set"
        
        if self.elemental_detection_region:
            x, y, w, h = self.elemental_detection_region
            elemental_text = f"({x}, {y}) - {w}x{h}"
        
        if self.physical_detection_region:
            x, y, w, h = self.physical_detection_region
            physical_text = f"({x}, {y}) - {w}x{h}"
        
        self.detection_region_label.config(
            text=f"Elemental: {elemental_text} | Physical: {physical_text}",
            fg="green" if (self.elemental_detection_region or self.physical_detection_region) else "gray"
        )
    
    def feedback_good(self):
        """Record positive feedback for the last detection"""
        if self.last_detection:
            number, mode, confidence, timestamp = self.last_detection
            feedback_entry = {
                'number': number,
                'mode': mode,
                'confidence': confidence,
                'feedback': 'good',
                'timestamp': timestamp
            }
            self.feedback_data.append(feedback_entry)
            self.save_config()
            self.update_feedback_stats()
            self.good_btn.config(state="disabled")
            self.bad_btn.config(state="disabled")
            self.last_detection_label.config(text=f"Number {number} ({mode}) - ✓ Good feedback recorded!", fg="green")
            print(f"[FEEDBACK] Good feedback recorded for {mode} number {number} (confidence: {confidence:.3f})")
    
    def feedback_bad(self):
        """Record negative feedback for the last detection"""
        if self.last_detection:
            number, mode, confidence, timestamp = self.last_detection
            feedback_entry = {
                'number': number,
                'mode': mode,
                'confidence': confidence,
                'feedback': 'bad',
                'timestamp': timestamp
            }
            self.feedback_data.append(feedback_entry)
            self.save_config()
            self.update_feedback_stats()
            self.good_btn.config(state="disabled")
            self.bad_btn.config(state="disabled")
            self.last_detection_label.config(text=f"Number {number} ({mode}) - ✗ Bad feedback recorded!", fg="red")
            print(f"[FEEDBACK] Bad feedback recorded for {mode} number {number} (confidence: {confidence:.3f})")
    
    def update_feedback_stats(self):
        """Update the feedback statistics display"""
        good_count = sum(1 for entry in self.feedback_data if entry.get('feedback') == 'good')
        bad_count = sum(1 for entry in self.feedback_data if entry.get('feedback') == 'bad')
        self.feedback_stats_label.config(text=f"Feedback: {good_count} good, {bad_count} bad")
    
    def update_detection_ui(self, status_text, status_color, number, mode, confidence):
        """Update the status label and enable feedback buttons"""
        self.status_label.config(text=status_text, fg=status_color)
        conf_str = f" (conf: {confidence:.2f})" if confidence > 0 else ""
        self.last_detection_label.config(
            text=f"Number {number} ({mode.capitalize()}){conf_str}",
            fg=status_color
        )
        self.good_btn.config(state="normal")
        self.bad_btn.config(state="normal")
        
    def start_elemental(self):
        if not self.running:
            self.running = True
            self.paused = False
            self.mode = "elemental"
            self.status_label.config(text="Elemental Mode: Running", fg="green")
            self.elemental_btn.config(state="disabled")
            self.physical_btn.config(state="disabled")
            self.pause_btn.config(state="normal", text="Pause")
            self.stop_btn.config(state="normal")
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
            self.stop_btn.config(state="normal")
            self.detection_thread = threading.Thread(target=self.detect_physical, daemon=True)
            self.detection_thread.start()
    
    def stop_detection(self):
        """Stop the current detection"""
        if self.running:
            self.running = False
            self.paused = False
            self.mode = None
            self.status_label.config(text="Stopped", fg="gray")
            self.elemental_btn.config(state="normal")
            self.physical_btn.config(state="normal")
            self.pause_btn.config(state="disabled", text="Pause", bg="#FF9800")
            self.stop_btn.config(state="disabled")
    
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
        settings_window.geometry("500x650")
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
        
        # Detection region selection
        detection_region_frame = tk.Frame(settings_window)
        detection_region_frame.pack(pady=15)
        
        tk.Label(detection_region_frame, text="Detection Region:", font=("Arial", 10, "bold")).pack()
        
        # Mode selection
        mode_frame = tk.Frame(detection_region_frame)
        mode_frame.pack(pady=5)
        
        tk.Label(mode_frame, text="Select Mode:", font=("Arial", 9)).pack(side=tk.LEFT, padx=5)
        region_mode_var = tk.StringVar(value="elemental")
        elemental_radio = tk.Radiobutton(mode_frame, text="Elemental", variable=region_mode_var, value="elemental", font=("Arial", 9))
        elemental_radio.pack(side=tk.LEFT, padx=5)
        physical_radio = tk.Radiobutton(mode_frame, text="Physical", variable=region_mode_var, value="physical", font=("Arial", 9))
        physical_radio.pack(side=tk.LEFT, padx=5)
        
        # Current region display
        region_display_frame = tk.Frame(detection_region_frame)
        region_display_frame.pack(pady=5)
        
        tk.Label(region_display_frame, text="Elemental:", font=("Arial", 9)).pack(side=tk.LEFT, padx=5)
        if self.elemental_detection_region:
            x, y, w, h = self.elemental_detection_region
            elemental_text = f"({x}, {y}) - {w}x{h}"
        else:
            elemental_text = "Not set (using full screen)"
        elemental_region_label = tk.Label(region_display_frame, text=elemental_text, fg="blue", font=("Arial", 8))
        elemental_region_label.pack(side=tk.LEFT, padx=5)
        
        tk.Label(region_display_frame, text="Physical:", font=("Arial", 9)).pack(side=tk.LEFT, padx=5)
        if self.physical_detection_region:
            x, y, w, h = self.physical_detection_region
            physical_text = f"({x}, {y}) - {w}x{h}"
        else:
            physical_text = "Not set (using full screen)"
        physical_region_label = tk.Label(region_display_frame, text=physical_text, fg="blue", font=("Arial", 8))
        physical_region_label.pack(side=tk.LEFT, padx=5)
        
        def update_region_display():
            """Update the region display labels"""
            if self.elemental_detection_region:
                x, y, w, h = self.elemental_detection_region
                elemental_region_label.config(text=f"({x}, {y}) - {w}x{h}", fg="green")
            else:
                elemental_region_label.config(text="Not set (using full screen)", fg="blue")
            
            if self.physical_detection_region:
                x, y, w, h = self.physical_detection_region
                physical_region_label.config(text=f"({x}, {y}) - {w}x{h}", fg="green")
            else:
                physical_region_label.config(text="Not set (using full screen)", fg="blue")
        
        def set_detection_region():
            selected_mode = region_mode_var.get()
            settings_window.withdraw()  # Hide settings window
            
            # Step 1: Get top-left corner
            step1_window = tk.Toplevel()
            step1_window.title("Set Detection Region - Step 1/2")
            step1_window.geometry("450x180")
            step1_window.attributes('-topmost', True)
            
            step1_label = tk.Label(
                step1_window,
                text=f"Step 1: Move mouse to TOP-LEFT corner of {selected_mode.capitalize()} detection area",
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
                        text=f"Step 2: Move mouse to BOTTOM-RIGHT corner of {selected_mode.capitalize()} detection area",
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
                                if selected_mode == "elemental":
                                    self.elemental_detection_region = (x1, y1, width, height)
                                    mode_name = "Elemental"
                                else:
                                    self.physical_detection_region = (x1, y1, width, height)
                                    mode_name = "Physical"
                                
                                update_region_display()
                                self.update_detection_region_label()
                                step2_window.destroy()
                                messagebox.showinfo("Success", f"{mode_name} detection region set: ({x1}, {y1}) - {width}x{height}")
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
        
    def detect_with_templates(self, templates_6, templates_5, templates_4, detection_region, mode_name):
        """
        Generic detection function that checks for numbers 6, 5, 4 in priority order.
        Returns (detected, detected_number, click_x, click_y, confidence)
        """
        # Capture the screen (full screen or region if specified)
        if detection_region:
            x, y, w, h = detection_region
            screenshot = ImageGrab.grab(bbox=(x, y, x + w, y + h))
            offset_x, offset_y = x, y
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
        
        # Debug for physical mode
        if mode_name == "physical":
            if detection_region:
                x, y, w, h = detection_region
                region_info = f"region=({x},{y},{w},{h})"
            else:
                region_info = "region=full screen"
            print(f"[PHYSICAL DEBUG] Starting detection - templates: 6={len(templates_6)}, 5={len(templates_5)}, 4={len(templates_4)}, threshold={self.match_threshold:.3f}, {region_info}")
        
        # Priority order: 6, 5, 4
        # Check for number 6 (highest priority)
        if len(templates_6) > 0:
            best_match_6 = None
            best_conf_6 = 0.0
            best_loc_6 = None
            
            for template_6 in templates_6:
                result_6 = cv2.matchTemplate(gray, template_6, cv2.TM_CCOEFF_NORMED)
                _, max_val_6, _, max_loc_6 = cv2.minMaxLoc(result_6)
                
                if max_val_6 > best_conf_6:
                    best_conf_6 = max_val_6
                    best_loc_6 = max_loc_6
                    best_match_6 = template_6
            
            if best_conf_6 >= self.match_threshold:
                detected = True
                detected_number = 6
                confidence = best_conf_6
                print(f"Detected {mode_name} number 6 with confidence: {best_conf_6:.2f}")
                click_x = best_loc_6[0] + best_match_6.shape[1] // 2 + offset_x
                click_y = best_loc_6[1] + best_match_6.shape[0] // 2 + offset_y
            elif mode_name == "physical":  # Always show for physical to debug
                print(f"[PHYSICAL] 6: best_conf={best_conf_6:.3f} < threshold={self.match_threshold:.3f} (diff: {self.match_threshold - best_conf_6:.3f})")
        
        # Check for number 5 (second priority)
        if not detected and len(templates_5) > 0:
            best_match_5 = None
            best_conf_5 = 0.0
            best_loc_5 = None
            
            for template_5 in templates_5:
                result_5 = cv2.matchTemplate(gray, template_5, cv2.TM_CCOEFF_NORMED)
                _, max_val_5, _, max_loc_5 = cv2.minMaxLoc(result_5)
                
                if max_val_5 > best_conf_5:
                    best_conf_5 = max_val_5
                    best_loc_5 = max_loc_5
                    best_match_5 = template_5
            
            if best_conf_5 >= self.match_threshold:
                detected = True
                detected_number = 5
                confidence = best_conf_5
                print(f"Detected {mode_name} number 5 with confidence: {best_conf_5:.2f}")
                click_x = best_loc_5[0] + best_match_5.shape[1] // 2 + offset_x
                click_y = best_loc_5[1] + best_match_5.shape[0] // 2 + offset_y
            elif mode_name == "physical":  # Always show for physical to debug
                print(f"[PHYSICAL] 5: best_conf={best_conf_5:.3f} < threshold={self.match_threshold:.3f} (diff: {self.match_threshold - best_conf_5:.3f})")
        
        # Check for number 4 (third priority)
        if not detected and len(templates_4) > 0:
            best_match_4 = None
            best_conf_4 = 0.0
            best_loc_4 = None
            
            for template_4 in templates_4:
                result_4 = cv2.matchTemplate(gray, template_4, cv2.TM_CCOEFF_NORMED)
                _, max_val_4, _, max_loc_4 = cv2.minMaxLoc(result_4)
                
                if max_val_4 > best_conf_4:
                    best_conf_4 = max_val_4
                    best_loc_4 = max_loc_4
                    best_match_4 = template_4
            
            if best_conf_4 >= self.match_threshold:
                detected = True
                detected_number = 4
                confidence = best_conf_4
                print(f"Detected {mode_name} number 4 with confidence: {best_conf_4:.2f}")
                click_x = best_loc_4[0] + best_match_4.shape[1] // 2 + offset_x
                click_y = best_loc_4[1] + best_match_4.shape[0] // 2 + offset_y
            elif mode_name == "physical":  # Always show for physical to debug
                print(f"[PHYSICAL] 4: best_conf={best_conf_4:.3f} < threshold={self.match_threshold:.3f} (diff: {self.match_threshold - best_conf_4:.3f})")
        
        # OCR fallback
        if not detected:
            if mode_name == "physical":
                print(f"[PHYSICAL] No template matches found, trying OCR fallback...")
            try:
                screen_width, screen_height = gray.shape[1], gray.shape[0]
                regions_to_check = [
                    (screen_width // 2, screen_height // 2 - 100, 200, 100),
                    (screen_width - 300, screen_height // 2 - 100, 250, 150),
                ]
                
                for x, y, w, h in regions_to_check:
                    x = max(0, min(x, screen_width - w))
                    y = max(0, min(y, screen_height - h))
                    region = gray[y:y+h, x:x+w]
                    
                    custom_config = r'--oem 3 --psm 10 -c tessedit_char_whitelist=0123456789'
                    text = pytesseract.image_to_string(region, config=custom_config)
                    
                    # Look for numbers 6, 5, or 4 (priority order)
                    for char in text.strip():
                        if char in ['6', '5', '4']:
                            detected = True
                            detected_number = int(char)
                            print(f"Detected {mode_name} number {char} via OCR in region ({x}, {y})")
                            click_x = x + w // 2 + offset_x
                            click_y = y + h // 2 + offset_y
                            break
                    
                    if detected:
                        break
            except Exception as ocr_error:
                if mode_name == "physical":
                    print(f"[PHYSICAL] OCR error: {ocr_error}")
        
        if mode_name == "physical":
            print(f"[PHYSICAL] Detection result: detected={detected}, number={detected_number}, click=({click_x}, {click_y}), confidence={confidence:.3f}")
        
        return detected, detected_number, click_x, click_y, confidence
    
    def detect_elemental(self):
        """
        Detects if the elemental attack number is 6, 5, or 4 (priority order) and clicks if found.
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
                
                # Use generic detection function
                detected, detected_number, click_x, click_y, confidence = self.detect_with_templates(
                    self.elemental_templates_6,
                    self.elemental_templates_5,
                    self.elemental_templates_4,
                    self.elemental_detection_region,
                    "elemental"
                )
                
                # Debug output
                if detected:
                    cooldown_remaining = max(0, self.click_cooldown - (current_time - last_click_time))
                    print(f"[DEBUG] Elemental detection: detected={detected}, number={detected_number}, click_x={click_x}, click_y={click_y}, cooldown_remaining={cooldown_remaining:.2f}")
                    if not click_x or not click_y:
                        print(f"[WARNING] Detection found but click coordinates are None! This should not happen.")
                else:
                    # Only print debug every 10 checks to avoid spam
                    if detection_count % 10 == 0:
                        print(f"[DEBUG] Elemental: No detection (templates_6={len(self.elemental_templates_6)}, templates_5={len(self.elemental_templates_5)}, templates_4={len(self.elemental_templates_4)})")
                
                # Perform click if detected and cooldown has passed
                if detected and (current_time - last_click_time) >= self.click_cooldown:
                    if click_x and click_y:
                        detection_count += 1
                        print(f"Clicking at ({click_x}, {click_y}) - Detection #{detection_count} (Number {detected_number})")
                        
                        # Click at detected location or use stored click coordinates
                        if self.click_coordinates:
                            pyautogui.click(self.click_coordinates[0], self.click_coordinates[1])
                            click_info = f"Clicked at ({self.click_coordinates[0]}, {self.click_coordinates[1]})"
                        else:
                            pyautogui.click(click_x, click_y)
                            click_info = f"Clicked at ({click_x}, {click_y})"
                        
                        last_click_time = current_time
                        count = detection_count
                        conf_str = f" ({confidence:.2f})" if confidence > 0 else ""
                        
                        # Store last detection for feedback
                        self.last_detection = (detected_number, "elemental", confidence, current_time)
                        
                        # Update UI with detection info and enable feedback buttons
                        self.root.after(0, lambda c=count, n=detected_number, conf=confidence: self.update_detection_ui(
                            f"Elemental: Clicked! #{c} (Number {n}){conf_str if conf > 0 else ''}",
                            "green",
                            n,
                            "elemental",
                            conf
                        ))
                    else:
                        print(f"[ERROR] Cannot click: detected={detected} but click_x={click_x}, click_y={click_y}")
                    
            except Exception as e:
                print(f"Error in detection: {e}")
                import traceback
                traceback.print_exc()
                
            time.sleep(self.check_interval)  # Check at configured interval
            
    def detect_physical(self):
        """
        Detects if the physical attack number is 6, 5, or 4 (priority order) and clicks if found.
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
                
                # Use generic detection function
                detected, detected_number, click_x, click_y, confidence = self.detect_with_templates(
                    self.physical_templates_6,
                    self.physical_templates_5,
                    self.physical_templates_4,
                    self.physical_detection_region,
                    "physical"
                )
                
                # Debug output
                if detected:
                    cooldown_remaining = max(0, self.click_cooldown - (current_time - last_click_time))
                    print(f"[DEBUG] Physical detection: detected={detected}, number={detected_number}, click_x={click_x}, click_y={click_y}, cooldown_remaining={cooldown_remaining:.2f}")
                    if not click_x or not click_y:
                        print(f"[WARNING] Detection found but click coordinates are None! This should not happen.")
                else:
                    # Print debug more frequently for physical to help diagnose
                    if detection_count % 5 == 0:
                        region_info = f"region={self.physical_detection_region}" if self.physical_detection_region else "region=full screen"
                        print(f"[DEBUG] Physical: No detection (templates_6={len(self.physical_templates_6)}, templates_5={len(self.physical_templates_5)}, templates_4={len(self.physical_templates_4)}, {region_info})")
                
                # Perform click if detected and cooldown has passed
                if detected and (current_time - last_click_time) >= self.click_cooldown:
                    if click_x and click_y:
                        detection_count += 1
                        print(f"Clicking at ({click_x}, {click_y}) - Detection #{detection_count} (Number {detected_number})")
                        
                        # Click at detected location or use stored click coordinates
                        if self.click_coordinates:
                            pyautogui.click(self.click_coordinates[0], self.click_coordinates[1])
                            click_info = f"Clicked at ({self.click_coordinates[0]}, {self.click_coordinates[1]})"
                        else:
                            pyautogui.click(click_x, click_y)
                            click_info = f"Clicked at ({click_x}, {click_y})"
                        
                        last_click_time = current_time
                        count = detection_count
                        conf_str = f" ({confidence:.2f})" if confidence > 0 else ""
                        
                        # Store last detection for feedback
                        self.last_detection = (detected_number, "physical", confidence, current_time)
                        
                        # Update UI with detection info and enable feedback buttons
                        self.root.after(0, lambda c=count, n=detected_number, conf=confidence: self.update_detection_ui(
                            f"Physical: Clicked! #{c} (Number {n}){conf_str if conf > 0 else ''}",
                            "blue",
                            n,
                            "physical",
                            conf
                        ))
                    else:
                        print(f"[ERROR] Cannot click: detected={detected} but click_x={click_x}, click_y={click_y}")
                    
            except Exception as e:
                print(f"Error in detection: {e}")
                import traceback
                traceback.print_exc()
                
            time.sleep(self.check_interval)  # Check at configured interval

if __name__ == "__main__":
    root = tk.Tk()
    app = ElementalAttackDetector(root)
    root.mainloop()

