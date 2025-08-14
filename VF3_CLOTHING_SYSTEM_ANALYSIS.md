# VF3 Clothing System Analysis - Critical Issues and Solutions

## Problem Statement

**CRITICAL ISSUE**: Our current export system is **additive** instead of **replacement-based** like the original VF3 system. This causes:

1. **Mesh conflicts**: Loading both `female.l_breast` AND `blazer_lb` (blazer left breast) simultaneously
2. **Incorrect DynamicVisual materials**: Skirts appearing skin-colored instead of fabric-colored
3. **Visual artifacts**: Clothing items overlap with underlying body parts instead of replacing them
4. **Performance issues**: Unnecessary geometry from hidden body parts

## VF3 Original System Behavior

In Virtual Figure 3, the clothing system works as follows:

### Replacement Logic
- When `blazer` is equipped:
  - `female.l_breast` Å® **DISABLED** 
  - `blazer_lb` (blazer left breast) Å® **ENABLED**
  - `female.r_breast` Å® **DISABLED**
  - `blazer_rb` (blazer right breast) Å® **ENABLED**

### Group Occupancy System
From our analysis of the 7-slot occupancy vector `[head, body, arms, hands, waist, legs, feet]`:

```
<skin> (base female body):
1,0,0,0,0,0,0:ciel.head
0,1,0,0,0,0,0:female.body  
0,0,1,0,0,0,0:female.arms
0,0,0,2,0,0,0:female.l_hand
0,0,0,1,0,0,0:female.r_hand
0,0,0,0,1,0,0:female.waist
0,0,0,0,0,1,0:female.legs
0,0,0,0,0,0,1:female.foots

<blazer> (clothing item):
0,3,3,0,0,0,0:ciel.blazer_vp
```

The blazer occupies slots `[body=3, arms=3]` which means it **replaces** the base body and arms in those slots.

## Current Implementation Problems

### 1. Additive Mesh Loading
**Current behavior**: Load ALL meshes from both `<skin>` and clothing `*_vp` blocks
**Correct behavior**: Load meshes from `<skin>` EXCEPT where clothing items override those slots

### 2. DynamicVisual Material Issues  
**Current behavior**: All DynamicVisual connectors get skin color
**Correct behavior**: DynamicVisual connectors should match the materials of the meshes they connect

Example: Skirt connectors should use fabric materials, not skin materials

### 3. Missing Replacement Logic
**Current behavior**: No conflict resolution between base body and clothing
**Correct behavior**: Clothing items should disable conflicting base body parts

## Required Solutions

### Solution 1: Implement Clothing Replacement Logic

```python
def resolve_clothing_conflicts(skin_attachments, clothing_items):
    """
    Resolve conflicts between base skin and clothing items.
    Clothing items should override base skin in occupied slots.
    """
    # Parse occupancy vectors for each clothing item
    # Disable base skin attachments in occupied slots
    # Return filtered attachment list
```

### Solution 2: Smart DynamicVisual Material Assignment

```python
def assign_dynamic_visual_materials(connector_mesh, connected_meshes):
    """
    Assign materials to DynamicVisual connectors based on what they connect to.
    - If connecting skin parts: use skin material
    - If connecting clothing: use clothing material  
    - If mixed: use dominant material or blend
    """
```

### Solution 3: Occupancy-Based Mesh Filtering

```python
def filter_attachments_by_occupancy(base_attachments, costume_items):
    """
    Filter base attachments based on costume occupancy vectors.
    
    Example:
    - Base: female.arms (occupies arms slot)
    - Blazer: occupies arms slot with value 3
    - Result: female.arms is DISABLED, blazer arms are ENABLED
    """
```

## Test Cases to Validate

### Test 1: Satsuki Naked vs Clothed
```bash
# Should show base female body parts
python3 export_ciel_to_gltf.py --desc data/satsuki.txt --naked --out satsuki_naked.glb

# Should show clothing INSTEAD OF base body in occupied slots  
python3 export_ciel_to_gltf.py --desc data/satsuki.txt --base-costume --out satsuki_clothed.glb
```

**Expected differences**:
- Naked: `female.l_breast`, `female.r_breast`, `female.arms`
- Clothed: `blazer_lb`, `blazer_rb`, `blazer arms` (NO female breast/arms)

### Test 2: DynamicVisual Material Consistency
- Naked model: All connectors should be skin-colored
- Clothed model: Skirt connectors should match skirt material, blazer connectors should match blazer material

### Test 3: No Mesh Overlap
- Clothed model should have NO overlapping geometry
- No "double thickness" where clothing and body occupy same space

## Implementation Priority

### Phase 1: Occupancy System (CRITICAL)
1. Parse occupancy vectors from `<skin>` and clothing blocks
2. Implement conflict resolution logic  
3. Filter attachments based on occupancy conflicts
4. Test with satsuki naked vs clothed

### Phase 2: Smart DynamicVisual Materials
1. Analyze which meshes each DynamicVisual connector bridges
2. Assign appropriate materials based on connected mesh types
3. Test skirt/clothing connector materials

### Phase 3: Advanced Clothing Features
1. Handle complex multi-piece garments (skirts with front/rear)
2. Support clothing layering (multiple items in same slot)
3. Handle accessory items that don't replace base parts

## File Analysis Required

### Key Files to Examine:
- `data/satsuki.txt` - Complete clothing definitions
- `data/female.txt` - Base body part definitions  
- Clothing `*_vp` blocks - Attachment and occupancy patterns
- DynamicVisual sections - Material and connection logic

### Questions to Answer:
1. How do occupancy values (0,1,2,3) map to replacement behavior?
2. Do higher occupancy values override lower ones?
3. How should bilateral items (left/right) handle conflicts?
4. What materials should DynamicVisual connectors use for clothing?

## Success Criteria

? **Naked export**: Shows complete female base body with skin-colored connectors
? **Clothed export**: Shows clothing items INSTEAD OF base body parts they replace  
? **No mesh conflicts**: No overlapping or duplicate geometry
? **Correct materials**: DynamicVisual connectors match appropriate mesh materials
? **Visual accuracy**: Matches original VF3 appearance when clothing is toggled
