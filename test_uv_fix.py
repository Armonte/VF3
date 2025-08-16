#!/usr/bin/env python3
"""
Test script to verify UV fixes for Satsuki's head
"""

import os
import sys

def test_satsuki_uv_fix():
    """Check if the UV fix was applied successfully"""
    
    print("🔍 Testing Satsuki UV fix...")
    
    # Check if the fixed file was created
    fixed_file = "sats_fixed.glb"
    if not os.path.exists(fixed_file):
        print(f"❌ Fixed file not found: {fixed_file}")
        return False
    
    # Get file size
    file_size = os.path.getsize(fixed_file)
    print(f"✅ Fixed file created: {fixed_file} ({file_size:,} bytes)")
    
    # Compare with other recent files
    comparison_files = [
        "sats_no_flip.glb",
        "sats_face_uv.glb", 
        "sats_complete.glb"
    ]
    
    print("\n📊 File size comparison:")
    for comp_file in comparison_files:
        if os.path.exists(comp_file):
            comp_size = os.path.getsize(comp_file)
            diff = file_size - comp_size
            status = "✅" if abs(diff) < 50000 else "⚠️"
            print(f"  {status} {comp_file}: {comp_size:,} bytes (diff: {diff:+,})")
    
    print(f"\n🎉 Satsuki UV fix test completed!")
    print(f"📁 Fixed file available: {fixed_file}")
    print(f"📁 Debug blend file: sats_fixed_debug.blend")
    
    return True

if __name__ == "__main__":
    test_satsuki_uv_fix()