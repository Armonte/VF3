#!/usr/bin/env python3
"""
Test VF3 -> Blender -> glTF export pipeline with Satsuki (naked)
"""

import os
import subprocess
import sys

def test_satsuki_blender_export():
    """Test the Blender-based VF3 export with naked Satsuki."""
    
    descriptor_path = "data/satsuki.TXT"
    output_path = "satsuki_naked_blender.glb"
    script_path = "vf3_blender_exporter.py"
    
    print(f"? Testing Blender VF3 export: {descriptor_path} -> {output_path}")
    
    # Check if descriptor exists
    if not os.path.exists(descriptor_path):
        print(f"? Descriptor file not found: {descriptor_path}")
        return False
    
    # Try to find Blender
    blender_paths = [
        "blender",  # In PATH
        "/usr/bin/blender",
        "/usr/local/bin/blender",
        "/opt/blender/blender",
        "/snap/bin/blender",
    ]
    
    blender_exe = None
    for path in blender_paths:
        try:
            result = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                blender_exe = path
                print(f"? Found Blender: {path}")
                break
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
    
    if not blender_exe:
        print("? Blender not found. Please install Blender")
        return False
    
    # Run Blender export
    cmd = [
        blender_exe,
        "--background",
        "--python", script_path,
        "--", descriptor_path, output_path
    ]
    
    print(f"? Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, timeout=600)  # 10 minute timeout for complex character
        
        if result.returncode == 0:
            if os.path.exists(output_path):
                size = os.path.getsize(output_path)
                print(f"? Export successful! Created {output_path} ({size} bytes)")
                print("? Try opening this file in Blender to check the armature and materials!")
                return True
            else:
                print("? Export completed but output file not found")
                return False
        else:
            print(f"? Blender export failed with return code {result.returncode}")
            return False
            
    except subprocess.TimeoutExpired:
        print("? Blender export timed out (>10 minutes)")
        return False
    except Exception as e:
        print(f"? Error running Blender: {e}")
        return False

if __name__ == "__main__":
    success = test_satsuki_blender_export()
    sys.exit(0 if success else 1)
