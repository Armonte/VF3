#!/usr/bin/env bash

# VF3 Satsuki Export Script
# Exports Satsuki character with fixed UV mapping and textures

echo "🎌 Exporting Satsuki character from VF3..."
echo "📁 Input: data/satsuki.TXT"
echo "📦 Output: satsuki_export_$(date +%Y%m%d_%H%M%S).glb"

# Generate timestamped output filename
OUTPUT_FILE="satsuki_export_$(date +%Y%m%d_%H%M%S).glb"

# Run the Blender export
blender --background --python vf3_blender_exporter.py -- data/satsuki.TXT "$OUTPUT_FILE"

# Check if export was successful
if [ -f "$OUTPUT_FILE" ]; then
    echo "✅ Export successful: $OUTPUT_FILE"
    echo "📊 File size: $(du -h "$OUTPUT_FILE" | cut -f1)"
    echo ""
    echo "🔍 To view the result:"
    echo "   - Open $OUTPUT_FILE in a GLB viewer"
    echo "   - Check textures in Material Preview/Rendered mode"
    echo "   - Verify UV mapping is correct (no weird shapes)"
else
    echo "❌ Export failed - no output file generated"
    echo "💡 Check the console output above for errors"
fi