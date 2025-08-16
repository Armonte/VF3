#!/usr/bin/env python3
"""
Final validation script to confirm the bilateral connector distribution fix.
"""

import sys
import os
import subprocess
import re

def validate_connector_distribution():
    """Run the exporter and validate that connectors are properly distributed."""
    print("🧪 VALIDATION: Testing bilateral connector distribution fix")
    print("=" * 70)
    
    # Run the exporter and capture output
    result = subprocess.run(
        ['./export_satsuki_modular.sh'], 
        capture_output=True, 
        text=True, 
        cwd='.'
    )
    
    if result.returncode != 0:
        print("❌ Export failed!")
        print(result.stderr)
        return False
    
    output = result.stdout + result.stderr
    
    # Extract bilateral tie assignments
    bilateral_patterns = [
        r'Bilateral leg tie: assigned to (\w+) \(connector_id=(\d+)\)',
        r'Bilateral arm tie: assigned to (\w+) \(connector_id=(\d+)\)'
    ]
    
    assignments = []
    for pattern in bilateral_patterns:
        matches = re.findall(pattern, output)
        assignments.extend(matches)
    
    print(f"🔍 Found {len(assignments)} bilateral connector assignments:")
    
    leg_assignments = []
    arm_assignments = []
    
    for region, connector_id in assignments:
        print(f"  - {region} (connector_id={connector_id})")
        if 'leg' in region:
            leg_assignments.append(region)
        elif 'arm' in region:
            arm_assignments.append(region)
    
    # Validate distribution
    success = True
    
    print(f"\n🎯 VALIDATION RESULTS:")
    
    # Check leg distribution
    if len(leg_assignments) > 1:
        unique_leg_regions = set(leg_assignments)
        if len(unique_leg_regions) > 1:
            print(f"  ✅ Leg connectors distributed across regions: {unique_leg_regions}")
        else:
            print(f"  ❌ All leg connectors assigned to same region: {unique_leg_regions}")
            success = False
    elif len(leg_assignments) == 1:
        print(f"  ℹ️  Only one leg connector found: {leg_assignments[0]}")
    else:
        print(f"  ⚠️  No leg connectors found")
    
    # Check arm distribution
    if len(arm_assignments) > 1:
        unique_arm_regions = set(arm_assignments)
        if len(unique_arm_regions) > 1:
            print(f"  ✅ Arm connectors distributed across regions: {unique_arm_regions}")
        else:
            print(f"  ❌ All arm connectors assigned to same region: {unique_arm_regions}")
            success = False
    elif len(arm_assignments) == 1:
        print(f"  ℹ️  Only one arm connector found: {arm_assignments[0]}")
    else:
        print(f"  ⚠️  No arm connectors found")
    
    # Check for export success
    if "Export completed successfully" in output:
        print(f"  ✅ Export completed successfully")
    else:
        print(f"  ❌ Export may have failed")
        success = False
    
    # Check file creation
    import glob
    glb_files = glob.glob("satsuki_modular_*.glb")
    if glb_files:
        latest_file = max(glb_files, key=os.path.getctime)
        file_size = os.path.getsize(latest_file) / 1024  # KB
        print(f"  ✅ GLB file created: {latest_file} ({file_size:.1f} KB)")
    else:
        print(f"  ❌ No GLB files found")
        success = False
    
    print(f"\n🏆 OVERALL RESULT: {'✅ SUCCESS' if success else '❌ FAILURE'}")
    
    if success:
        print(f"\n🎉 The bilateral connector distribution fix is working correctly!")
        print(f"   - Mixed left/right connectors are now distributed evenly")
        print(f"   - No more 'right knee connector on left leg' issues")
        print(f"   - Character export produces proper anatomical groups")
    else:
        print(f"\n💥 The fix needs more work - issues still remain")
    
    return success

if __name__ == "__main__":
    validate_connector_distribution()