#!/usr/bin/env python3
"""
Debug export with detailed logging to trace connector merging contamination.
"""

import os
import sys
import subprocess

def run_debug_export():
    """Run the export with enhanced logging and capture all output."""
    print("=== RUNNING DEBUG EXPORT WITH LOGGING ===")
    
    # First, add detailed logging to the exporter if not already added
    add_debug_logging_to_exporter()
    
    # Run the export and capture output
    cmd = [
        'blender', '--background', '--python', 'vf3_blender_exporter.py', 
        '--', 'data/satsuki.TXT', 'satsuki_debug_connector_merging.glb'
    ]
    
    print(f"Running command: {' '.join(cmd)}")
    
    try:
        # Run with real-time output capture
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # Print output in real-time and save to file
        log_lines = []
        while True:
            line = process.stdout.readline()
            if line:
                print(line.rstrip())
                log_lines.append(line)
            elif process.poll() is not None:
                break
        
        # Save full log
        with open('debug_export_log.txt', 'w') as f:
            f.writelines(log_lines)
        
        return_code = process.wait()
        print(f"\nExport completed with return code: {return_code}")
        
        # Analyze the log for connector merging issues
        analyze_export_log(log_lines)
        
    except Exception as e:
        print(f"❌ Failed to run export: {e}")

def add_debug_logging_to_exporter():
    """Add enhanced debug logging to the connector merging function."""
    print("Adding enhanced debug logging to exporter...")
    
    # Check if logging is already added
    with open('vf3_blender_exporter.py', 'r') as f:
        content = f.read()
    
    if 'ENHANCED DEBUG LOGGING' in content:
        print("Debug logging already present")
        return
    
    # Add logging to the connector merging function
    enhanced_logging = '''
    # ENHANCED DEBUG LOGGING FOR CONNECTOR MERGING
    print(f"      🔍 ENHANCED DEBUG: Processing connector {connector_name}")
    print(f"         Connector number extracted: {connector_number}")
    print(f"         Target categories from targeting logic: {target_categories}")
    print(f"         All available mesh objects: {[obj.name for obj in mesh_objects]}")
    '''
    
    # Find the location to insert logging
    target_line = 'target_categories = get_dynamic_merge_candidates(connector_number, existing_mesh_names)'
    replacement = target_line + enhanced_logging
    
    updated_content = content.replace(target_line, replacement, 1)
    
    if updated_content != content:
        with open('vf3_blender_exporter.py', 'w') as f:
            f.write(updated_content)
        print("✅ Enhanced debug logging added")
    else:
        print("⚠️ Could not find insertion point for debug logging")

def analyze_export_log(log_lines):
    """Analyze the export log for connector merging issues."""
    print("\n=== ANALYZING EXPORT LOG ===")
    
    connector_events = []
    current_connector = None
    
    for line in log_lines:
        line = line.strip()
        
        # Track connector processing
        if 'Processing DynamicVisual mesh' in line:
            parts = line.split(':')
            if len(parts) >= 2:
                mesh_info = parts[1].strip()
                current_connector = mesh_info
                connector_events.append(('processing', current_connector, line))
        
        # Track connector targeting
        elif 'Connector' in line and 'DYNAMIC merge targets' in line:
            connector_events.append(('targeting', current_connector, line))
        
        # Track merging decisions
        elif 'merged with' in line.lower():
            connector_events.append(('merge', current_connector, line))
        
        # Track fallback logic
        elif 'fallback' in line.lower():
            connector_events.append(('fallback', current_connector, line))
    
    print(f"Found {len(connector_events)} connector-related events:")
    for event_type, connector, line in connector_events:
        print(f"  [{event_type.upper()}] {line}")
    
    # Look for specific issues
    print("\n=== ISSUE ANALYSIS ===")
    
    elbow_contamination = [event for event in connector_events if 'connector_1' in event[2] and 'body' in event[2].lower()]
    if elbow_contamination:
        print("❌ FOUND ELBOW CONTAMINATION EVENTS:")
        for event in elbow_contamination:
            print(f"    {event[2]}")
    
    missing_targets = [event for event in connector_events if 'NO MATCHES' in event[2] or 'not found' in event[2].lower()]
    if missing_targets:
        print("❌ FOUND MISSING TARGET EVENTS:")
        for event in missing_targets:
            print(f"    {event[2]}")
    
    # Check for any connector that should target hands but is targeting body
    hand_targeting_issues = []
    for i, event in enumerate(connector_events):
        if event[0] == 'targeting' and 'connector' in event[2] and 'hand' in event[2]:
            # Look for the next merge event
            for j in range(i+1, len(connector_events)):
                next_event = connector_events[j]
                if next_event[0] == 'merge' and 'body' in next_event[2].lower():
                    hand_targeting_issues.append((event, next_event))
                    break
    
    if hand_targeting_issues:
        print("❌ FOUND HAND->BODY TARGETING ISSUES:")
        for target_event, merge_event in hand_targeting_issues:
            print(f"    Target: {target_event[2]}")
            print(f"    Merge:  {merge_event[2]}")

def check_blend_file_results():
    """Check what's in the generated blend file."""
    print("\n=== CHECKING BLEND FILE RESULTS ===")
    
    # Look for the debug blend file
    blend_files = [f for f in os.listdir('.') if f.endswith('debug.blend')]
    if blend_files:
        latest_blend = max(blend_files, key=os.path.getmtime)
        print(f"Found debug blend file: {latest_blend}")
        
        # We can't directly inspect the blend file without Blender, but we can
        # check if the export created a GLB file
        glb_file = 'satsuki_debug_connector_merging.glb'
        if os.path.exists(glb_file):
            size = os.path.getsize(glb_file)
            print(f"✅ GLB file created: {glb_file} ({size} bytes)")
        else:
            print("❌ No GLB file created - export may have failed")
    else:
        print("❌ No debug blend files found")

if __name__ == "__main__":
    run_debug_export()
    check_blend_file_results()