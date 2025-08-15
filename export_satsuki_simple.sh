#!/usr/bin/env bash

# VF3 Simple Export Script
# Tests the refactored, modular approach

echo "🎌 Testing VF3 Simple Exporter..."
echo "📁 Input: data/satsuki.TXT"

OUTPUT_FILE="satsuki_simple_$(date +%Y%m%d_%H%M%S).glb"
echo "📦 Output: $OUTPUT_FILE"

# Run the simple exporter
blender --background --python export_vf3_simple.py -- data/satsuki.TXT "$OUTPUT_FILE"

# Check result
if [ -f "$OUTPUT_FILE" ]; then
    echo "✅ Export successful: $OUTPUT_FILE"
    echo "📊 File size: $(du -h "$OUTPUT_FILE" | cut -f1)"
    echo ""
    echo "🔍 Next steps:"
    echo "   1. Open $OUTPUT_FILE in a GLB viewer"
    echo "   2. Check if UV mapping is correct"
    echo "   3. Verify textures display properly"
else
    echo "❌ Export failed - no output file generated"
    echo "💡 Check the console output above for errors"
fi