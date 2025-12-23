"""
Setup script to check dependencies and provide installation instructions
"""
import sys
import subprocess

def check_package(package_name, import_name=None):
    """Check if a Python package is installed"""
    if import_name is None:
        import_name = package_name
    try:
        __import__(import_name)
        print(f"[OK] {package_name} is installed")
        return True
    except ImportError:
        print(f"[X] {package_name} is NOT installed")
        return False

def check_tesseract():
    """Check if Tesseract OCR is installed"""
    try:
        result = subprocess.run(['tesseract', '--version'], 
                              capture_output=True, 
                              text=True, 
                              timeout=5)
        if result.returncode == 0:
            print("[OK] Tesseract OCR is installed")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    print("[X] Tesseract OCR is NOT installed")
    print("  Please install Tesseract OCR from: https://github.com/UB-Mannheim/tesseract/wiki")
    print("  On Windows, download and run the installer")
    return False

def main():
    print("Checking dependencies for Elemental Attack Detector...\n")
    
    packages = [
        ("pillow", "PIL"),
        ("pyautogui", "pyautogui"),
        ("pytesseract", "pytesseract"),
        ("opencv-python", "cv2"),
        ("numpy", "numpy"),
        ("keyboard", "keyboard"),
    ]
    
    missing = []
    for package, import_name in packages:
        if not check_package(package, import_name):
            missing.append(package)
    
    print()
    tesseract_ok = check_tesseract()
    
    print("\n" + "="*50)
    if missing:
        print("\nMissing Python packages. Install them with:")
        print(f"pip install {' '.join(missing)}")
        print("\nOr install all dependencies with:")
        print("pip install -r requirements.txt")
    elif not tesseract_ok:
        print("\nPython packages are installed, but Tesseract OCR is missing.")
        print("Please install Tesseract OCR to use OCR-based detection.")
    else:
        print("\n[OK] All dependencies are installed!")
        print("You can now run: python elemental_attack_detector.py")
    
    print("\nNote: If template matching doesn't work well, you may need to:")
    print("  1. Adjust the match_threshold value in the script (around line 143)")
    print("  2. Adjust the OCR region coordinates in detect_elemental()")
    print("  3. Set click_coordinates if you want to click a specific location")

if __name__ == "__main__":
    main()

