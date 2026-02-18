import subprocess
import time
import glob
import os
import sys
import argparse

def capture_example(script_path, output_dir="screenshots"):
    """
    Launches a terminal script, waits, captures a screenshot, and closes the window.
    """
    filename = os.path.basename(script_path)
    name_no_ext = os.path.splitext(filename)[0]
    output_file = os.path.join(output_dir, f"{name_no_ext}.png")
    
    # Get absolute path for the script and the current working directory
    abs_script_path = os.path.abspath(script_path)
    cwd = os.getcwd()
    
    print(f"[{filename}] Launching...")
    
    # AppleScript to launch Terminal, run the script, and get the window ID.
    # We use 'do script' which returns a tab, then get the window of that tab.
    # process substitution is used to ensure we get the ID out cleanly.
    cmd = f"source venv/bin/activate && python {filename}"
    
    # Escaping for AppleScript
    # We need to escape backslashes and double quotes in the command
    safe_cmd = cmd.replace("\\", "\\\\").replace('"', '\\"')
    safe_cwd = cwd.replace("\\", "\\\\").replace('"', '\\"')
    
    applescript_launch = f'''
    tell application "Terminal"
        activate
        do script "cd \\"{safe_cwd}\\" && {safe_cmd}"
        delay 1
        set winId to id of front window
        return winId
    end tell
    '''
    
    try:
        result = subprocess.run(
            ['osascript', '-e', applescript_launch], 
            capture_output=True, 
            text=True, 
            check=True
        )
        window_id = result.stdout.strip()
        print(f"[{filename}] Window ID: {window_id}")
    except subprocess.CalledProcessError as e:
        print(f"[{filename}] Failed to launch: {e.stderr}")
        return False

    # Wait for the UI to stabilize and show data
    print(f"[{filename}] Waiting 12 seconds for UI to stabilize...")
    time.sleep(12)
    
    # Capture screenshot
    # Use absolute path to be safe
    abs_output_file = os.path.abspath(output_file)
    print(f"[{filename}] Capturing window {window_id} to {abs_output_file}...")
    
    try:
        # Check if window exists first? No easy way.
        # Just run capture.
        cmd = ['screencapture', '-l', str(window_id), abs_output_file]
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[{filename}] screencapture failed: {result.stderr}")
        else:
            if os.path.exists(abs_output_file):
                print(f"[{filename}] Screenshot saved successfully ({os.path.getsize(abs_output_file)} bytes).")
            else:
                print(f"[{filename}] screencapture returned 0 but file missing!")
                
    except subprocess.CalledProcessError as e:
        print(f"[{filename}] Failed to capture: {e}")
        # Try to close window anyway
    
    # Close the window
    print(f"[{filename}] Closing window...")
    applescript_close = f'''
    tell application "Terminal"
        close (every window whose id is {window_id})
    end tell
    '''
    try:
        subprocess.run(['osascript', '-e', applescript_close], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        # Sometimes closing fails if the window is already gone or busy, but usually fine
        print(f"[{filename}] Warning: Failed to close window cleanly: {e.stderr}")

    return True

def main():
    parser = argparse.ArgumentParser(description="Capture screenshots of Terminal UI examples")
    parser.add_argument("--pattern", default="example_*.py", help="Glob pattern for scripts")
    parser.add_argument("--test", action="store_true", help="Run only the first found script for testing")
    args = parser.parse_args()

    # Ensure screenshots dir exists
    if not os.path.exists("screenshots"):
        os.makedirs("screenshots")
        print("Created screenshots/ directory")

    files = sorted(glob.glob(args.pattern))
    
    if not files:
        print("No files found matching pattern.")
        sys.exit(1)

    if args.test:
        print("Running in TEST mode (one file only)")
        files = files[:1]

    print(f"Found {len(files)} scripts to capture.")
    
    for script in files:
        success = capture_example(script)
        if success:
            # Small cooldown between windows
            time.sleep(2)

if __name__ == "__main__":
    main()
