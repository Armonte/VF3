#!/usr/bin/env bash

# VF3 Naked Satsuki Export - No costume items, just base female body + head
# This helps debug missing geometry issues

echo "🎌 Exporting Naked Satsuki (base female body only)..."
echo "📁 Input: data/satsuki_naked.TXT"

# First, create a naked descriptor file with base female body parts
cat > data/satsuki_naked.TXT << 'EOF'
<scene>
Name:naked satsuki test
Charactor:(-0.08,1.08,0.21):satsuki
Costume:
Pose:
body:(50.0,-104.0,0.0)
head:(53.0,52.0,0.0)
r_arm1:(50.0,-104.0,0.0)
l_arm1:(50.0,-104.0,0.0)
r_arm2:(50.0,-104.0,0.0)
l_arm2:(50.0,-104.0,0.0)
r_hand:(50.0,-104.0,0.0)
l_hand:(50.0,-104.0,0.0)
waist:(50.0,-104.0,0.0)
r_leg1:(50.0,-104.0,0.0)
l_leg1:(50.0,-104.0,0.0)
r_leg2:(50.0,-104.0,0.0)
l_leg2:(50.0,-104.0,0.0)
r_foot:(50.0,-104.0,0.0)
l_foot:(50.0,-104.0,0.0)
Eyes:
EyeInfo:

# Base skin components (from satsuki.TXT)
skin
1,0,0,0,0,0,0:satsuki.head
0,1,0,0,0,0,0:female.body
0,0,1,0,0,0,0:female.arms
0,0,0,2,0,0,0:female.l_hand
0,0,0,1,0,0,0:female.r_hand
0,0,0,0,1,0,0:female.waist
0,0,0,0,0,1,0:female.legs
0,0,0,0,0,0,1:female.foots
EOF

OUTPUT_FILE="satsuki_naked_$(date +%Y%m%d_%H%M%S).glb"
echo "📦 Output: $OUTPUT_FILE"

# Run the modular exporter on naked satsuki
blender --background --python vf3_blender_exporter_modular.py -- data/satsuki_naked.TXT "$OUTPUT_FILE"

# Check result
if [ -f "$OUTPUT_FILE" ]; then
    echo "✅ Naked export successful: $OUTPUT_FILE"
    echo "📊 File size: $(du -h "$OUTPUT_FILE" | cut -f1)"
    echo ""
    echo "🔍 Analysis:"
    echo "   - This should show just female base body parts"
    echo "   - Check if waist/hip geometry is complete"
    echo "   - Compare with clothed version to see what's missing"
    echo "   - Expected: head + body + arms + hands + waist + legs + feet"
else
    echo "❌ Naked export failed - no output file generated"
    echo "💡 Check the console output above for errors"
fi