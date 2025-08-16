# VF3 Reverse Engineering - IDA Pro Function and Variable Renaming Guide

## What We're Doing

I'm systematically renaming functions, global variables, and local variables in IDA Pro to make the VF3 (Virtual Figure 3) codebase readable and understandable. This is a reverse engineering process to document how the game handles DynamicVisual tags and the costume system.

## The Process

### 1. **Function Discovery**
- Search for functions that reference key strings like "DynamicVisual:", "Costume:", "Material", "FaceArray"
- Use cross-references to find related functions
- Examine function decompilation to understand their purpose

### 2. **Function Renaming**
- Rename functions from `sub_XXXXXX` to descriptive names
- Use naming conventions that reflect the function's purpose
- Examples: `ParseDynamicVisualData`, `LoadCostumeAndPoseData`, `ResolveCostumeConflicts`

### 3. **Local Variable Renaming**
- Rename variables from `v1`, `v2`, `v3` to meaningful names
- Use descriptive names that reflect the variable's purpose
- Examples: `bone_name`, `vertex_index`, `occupancy_conflict`, `character_ptr`

### 4. **Global Variable Renaming**
- Rename global string constants from `aXXXXXX` to descriptive names
- Use `g_str` prefix for string globals
- Examples: `g_strDynamicVisual`, `g_strCostume`, `g_strMaterial`

## Key Areas of Focus

### **DynamicVisual System**
- Functions that parse vertex data, materials, and face arrays
- Bone binding and transformation logic
- Material assignment and UV coordinate handling

### **Costume System**
- Functions that load and process costume data
- Occupancy-based conflict resolution (7-slot system)
- Costume switching and application logic

### **Character Management**
- Character loading and validation
- Skin and costume data processing
- Transform application and bone management

## Naming Conventions Used

### **Functions**
- `Parse*` - Data parsing functions
- `Load*` - Data loading functions
- `Process*` - Data processing functions
- `Resolve*` - Conflict resolution functions
- `Validate*` - Validation functions
- `Find*` - Lookup/search functions

### **Variables**
- `*_ptr` - Pointer variables
- `*_index` - Index/counter variables
- `*_count` - Count variables
- `*_data` - Data structure variables
- `*_manager` - Manager object variables
- `*_conflict` - Conflict-related variables

### **Globals**
- `g_str*` - String constants
- `g_*` - Other global variables

## Current Progress

### **Functions Renamed: 43**
1. `ParseDynamicVisualData` - Main DynamicVisual parser
2. `LoadCostumeAndPoseData` - Costume/pose loader
3. `ProcessCostumeData` - Costume processor
4. `ResolveCostumeConflicts` - Conflict resolver
5. `LoadCharacterSkinAndCostumes` - Character loader
6. `ProcessCharacterData` - Character processor
7. `ParseDynamicVisualString` - String parser
8. `CountColonsInString` - Format detector
9. `ReadNextLineFromFile` - File reader
10. `LookupOrAddString` - String manager
11. `AssignStringIfEmpty` - String assigner
12. `FindCharacterIndex` - Character finder
13. `ValidateAndProcessCharacter` - Character validator
14. `InitializeProductsAndScene` - Main initializer
15. `ProcessRGBAValues` - RGBA color data processor
16. `AddOrFindInVector` - Vector/array management
17. `ProcessFaceData` - Face data processor (4 integers)
18. `ProcessBodyPartData` - Body part data processor
19. `FindBodyPartIndex` - Body part search function
20. `CompareBodyPartData` - Body part comparison
21. `AddBodyPartData` - Add body part to collection
22. `ProcessPositionData` - Position data processor
23. `InitializeCharacterStates` - Character state manager
24. `GetCharacterByIndex` - Character lookup by index
25. `CleanupCharacterData` - Character data cleanup
26. `CleanupCharacterResources` - Character resource cleanup
27. `AllocateCharacterArray` - Character array allocator
28. `ProcessTransformData` - Transform data processor
29. `CopyAndResizeArray` - Array copy and resize
30. `GetArrayElementOffset` - Array element offset calculator
31. `ExpandDynamicArray` - Dynamic array expansion
32. `ExpandCharacterResourceArray` - Character resource array expansion
33. `ScaleVector3D` - 3D vector scaling
34. `MultiplyVectors3D` - 3D vector component-wise multiplication
35. `CalculateDistance3D` - 3D distance calculation
36. `NormalizeRotationAngles` - Rotation angle normalization
37. `ProcessTransformAndCall` - Transform processing with virtual call
38. `EulerAnglesToRotationMatrix` - Euler angles to rotation matrix conversion
39. `SphericalToCartesian` - Spherical to Cartesian coordinate conversion
40. `SwapMatrixRows` - Matrix row/column swapping
41. `ManageObjectReference` - Object reference management
42. `ReleaseObjectReference` - Object reference release
43. `ParseDualPositionVertexData` - Complete dual-position vertex parser (BREAKTHROUGH!)

### **Key DynamicVisual System Discovery**

**BREAKTHROUGH**: Complete binary analysis of VF3's DynamicVisual system revealed:

1. **Dual Position System**: Each vertex has `pos1` (base) and `pos2` (fitted) coordinates
2. **40-byte Vertex Structure**: Bone hash, UV coords, index, pos1, bone type flags, additional flags
3. **Bone Type Classification**: H/P/B rotation channel flags stored per vertex
4. **Format Detection**: VF3 counts colons to detect format (1, 3, or 4 colons)
5. **Missing Implementation**: Our code only uses `pos1` - `pos2` location unknown but critical

**BREAKTHROUGH UPDATE**: Found `pos2` storage in `ParseDualPositionVertexData` (0x4112ce)!
- **pos1**: Stored at vertex_data_ptr + 36, 40, 44 (offsets +36/+40/+44)
- **pos2**: Stored at vertex_data_ptr + 48, 52, 56 (offsets +48/+52/+56) - FOUND!
- **Vertex Structure**: 76 bytes total (not 40 as previously thought)

**Next Priority**: Implement dual-position logic using discovered pos2 storage locations.

### **Global Variables Renamed: 7**
- `g_strDynamicVisual`, `g_strCostume`, `g_strCostumes`, `g_strCostumeSection`
- `g_strMaterial`, `g_strMaterialSection`, `g_strFaceArray`

## How to Repeat This Process

### **Step 1: Find Functions**
```ida
// Search for relevant strings
Search -> Text -> "DynamicVisual"
Search -> Text -> "Costume"
Search -> Text -> "Material"
Search -> Text -> "FaceArray"

// Get cross-references to find functions
Right-click string -> "List cross references to"
```

### **Step 2: Examine Functions**
```ida
// Decompile function to understand purpose
Right-click function -> "Decompile"
// Look for:
// - String comparisons
// - File operations
// - Data processing loops
// - Variable usage patterns
```

### **Step 3: Rename Functions**
```ida
// Rename function
Right-click function -> "Rename"
// Use descriptive names like:
// - ParseDynamicVisualData
// - LoadCostumeData
// - ResolveCostumeConflicts
```

### **Step 4: Rename Local Variables**
```ida
// Rename variables in decompiled view
// Look for patterns:
// - v1, v2, v3 -> meaningful names
// - v4, v5, v6 -> descriptive purposes
// - v7, v8, v9 -> function-specific names
```

### **Step 5: Rename Global Variables**
```ida
// Find global string references
// Rename from aXXXXXX to g_strXXXXXX
// Use descriptive names that reflect content
```

## What This Achieves

1. **Readable Code**: Functions and variables have meaningful names
2. **Understanding**: Clear picture of how VF3 systems work
3. **Documentation**: Living documentation of the codebase
4. **Maintenance**: Easier to modify and extend the code
5. **Collaboration**: Other developers can understand the code

## Next Steps for VF3 Analysis

### **Continue Renaming**
- Find more costume-related functions
- Identify occupancy system functions
- Rename mesh processing functions
- Document material system functions

### **System Understanding**
- Map the complete costume loading pipeline
- Understand DynamicVisual generation
- Document the 7-slot occupancy system
- Analyze real-time costume switching

### **Code Documentation**
- Create function call graphs
- Document data flow between systems
- Map variable usage patterns
- Create system architecture diagrams

## VF3 System Architecture (Discovered)

### **DynamicVisual Processing Pipeline**
```
ParseDynamicVisualData
„¥„Ÿ„Ÿ ParseDynamicVisualString (vertex parsing)
„¥„Ÿ„Ÿ Material section processing
„¤„Ÿ„Ÿ FaceArray section processing
```

### **Costume Loading Pipeline**
```
LoadCostumeAndPoseData
„¥„Ÿ„Ÿ LoadCharacterSkinAndCostumes
„¥„Ÿ„Ÿ ProcessCostumeData
„¤„Ÿ„Ÿ ResolveCostumeConflicts
```

### **Character Management System**
```
InitializeProductsAndScene
„¥„Ÿ„Ÿ LoadCharacterSkinAndCostumes
„¥„Ÿ„Ÿ ProcessCharacterData
„¤„Ÿ„Ÿ ValidateAndProcessCharacter
```

## Key Insights Discovered

1. **7-Slot Occupancy System**: VF3 uses a sophisticated slot-based system for costume conflicts
2. **DynamicVisual Generation**: The game generates connector meshes on-the-fly for seamless costume integration
3. **Bone Type Classification**: Special character codes (H, P, B) categorize bones and determine behavior
4. **String Management**: Hash table system for efficient string deduplication and lookup
5. **File Processing**: Line-by-line parsing with support for encrypted/encoded files

## Tools and Techniques Used

### **IDA Pro Features**
- String search and cross-reference analysis
- Function decompilation and analysis
- Variable renaming and documentation
- Call graph generation

### **Analysis Methods**
- Pattern recognition in variable usage
- Function call flow analysis
- String constant identification
- Data structure inference

This process transforms the VF3 binary from an unreadable mess of hex addresses into a comprehensible codebase that reveals how the game's costume and DynamicVisual systems actually work.
