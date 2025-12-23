# Installation Guide for Elemental Attack Detector

## Step 1: Install Python

If Python is not installed or not working properly:

1. **Download Python** from https://www.python.org/downloads/
   - Choose the latest Python 3.11 or 3.12 version
   - **IMPORTANT**: During installation, check the box "Add Python to PATH"

2. **Verify installation** by opening a new PowerShell/Command Prompt and running:
   ```
   python --version
   ```
   You should see something like `Python 3.11.x` or `Python 3.12.x`

## Step 2: Install Python Packages

Once Python is installed, open PowerShell/Command Prompt in this directory and run:

```bash
pip install -r requirements.txt
```

Or if that doesn't work:

```bash
python -m pip install -r requirements.txt
```

This will install:
- pillow (image processing)
- pyautogui (screen capture and clicking)
- pytesseract (OCR library)
- opencv-python (computer vision)
- numpy (numerical computing)
- keyboard (keyboard shortcuts)

## Step 3: Install Tesseract OCR

Tesseract OCR is required for the OCR-based detection method:

### Windows:
1. Download the installer from: https://github.com/UB-Mannheim/tesseract/wiki
2. Run the installer (e.g., `tesseract-ocr-w64-setup-5.x.x.exe`)
3. **IMPORTANT**: Note the installation path (usually `C:\Program Files\Tesseract-OCR`)
4. Add Tesseract to your PATH, or configure it in the script

### Configure Tesseract Path (if needed):
If Tesseract is not in your PATH, you may need to add this line near the top of `elemental_attack_detector.py`:
```python
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

## Step 4: Verify Installation

Run the setup checker:
```bash
python setup.py
```

Or run the main script:
```bash
python elemental_attack_detector.py
```

## Troubleshooting

- **"pip is not recognized"**: Make sure Python is installed and added to PATH
- **"Tesseract not found"**: Install Tesseract OCR and optionally set the path in the script
- **Permission errors**: Try running PowerShell/Command Prompt as Administrator

