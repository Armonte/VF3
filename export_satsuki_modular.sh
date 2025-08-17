#!/usr/bin/env bash

# VF3 Modular Exporter Test Script
# Tests the refactored modular version against the original

echo "🎌 Testing VF3 Modular Exporter..."
echo "📁 Input: data/hisui.TXT"

OUTPUT_FILE="hisui_modular_$(date +%Y%m%d_%H%M%S).glb"
echo "📦 Output: $OUTPUT_FILE"

# Run the modular exporter
blender --background --python vf3_blender_exporter_modular.py -- data/hisui.TXT "$OUTPUT_FILE"

# Check result
if [ -f "$OUTPUT_FILE" ]; then
    echo "✅ Modular export successful: $OUTPUT_FILE"
    echo "📊 File size: $(du -h "$OUTPUT_FILE" | cut -f1)"
    echo ""
    echo "🔍 Next steps:"
    echo "   1. Compare file size with original export (~458K)"
    echo "   2. Open $OUTPUT_FILE in a GLB viewer"
    echo "   3. Verify textures and materials match original"
    echo "   4. Check for any differences in geometry"
else
    echo "❌ Modular export failed - no output file generated"
    echo "💡 Check the console output above for errors"
fi