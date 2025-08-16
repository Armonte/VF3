#!/usr/bin/env python3
"""
Test script to debug connector bone group splitting fix
"""

import sys
import os

# Add VF3 modules to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

def test_connector_split():
    print("🔧 Testing connector bone group splitting fix...")
    
    # Use the debug script to test with the satsuki complete arms file
    debug_file = "/mnt/c/dev/loot/VF3/satsuki_complete_arms_debug.blend"
    
    if not os.path.exists(debug_file):
        print(f"❌ Debug blend file not found: {debug_file}")
        print("Available blend files:")
        for f in os.listdir(current_dir):
            if f.endswith('.blend'):
                print(f"  {f}")
        return False
    
    print(f"✅ Found debug blend file: {debug_file}")
    
    # Run a fresh export test with the bone splitting logic
    test_command = f'timeout 120 blender --background --python debug_connector_targeting.py -- {debug_file}'
    print(f"Running: {test_command}")
    os.system(test_command)
    
    return True

if __name__ == "__main__":
    test_connector_split()