import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class Bone:
    name: str
    parent: Optional[str]
    translation: Tuple[float, float, float]
    rotation: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    scale: Tuple[float, float, float] = (1.0, 1.0, 1.0)


@dataclass
class Attachment:
    # If child_name is set, a synthetic child node under parent_bone is created at offset
    # and the mesh is attached to child_name; otherwise, attach directly to attach_bone
    attach_bone: str
    resource_id: str  # e.g., 'ciel.blazer', 'female.l_leg1'
    child_name: Optional[str] = None
    parent_bone: Optional[str] = None
    child_offset: Optional[Tuple[float, float, float]] = None


@dataclass
class Descriptor:
    path: str
    blocks: Dict[str, List[str]] = field(default_factory=dict)


FLOAT_TUPLE_RE = re.compile(r"\(([^\)]*)\)")


def _parse_tuple3(text: str) -> Tuple[float, float, float]:
    match = FLOAT_TUPLE_RE.search(text)
    if not match:
        raise ValueError(f"Expected tuple like (x,y,z) in: {text}")
    items = match.group(1).split(',')
    if len(items) != 3:
        raise ValueError(f"Expected 3 components in tuple: {text}")
    return (float(items[0]), float(items[1]), float(items[2]))


def _parse_tuple2(text: str) -> Tuple[float, float]:
    """Parse (x,y) tuple for UV coordinates."""
    text = text.strip()
    if text.startswith('('):
        text = text[1:]
    if text.endswith(')'):
        text = text[:-1]
    parts = text.split(',')
    if len(parts) >= 2:
        return (float(parts[0]), float(parts[1]))
    return (0.0, 0.0)


def parse_dynamic_visual_mesh(lines: List[str]) -> Optional[Dict]:
    """Parse DynamicVisual, Material, and FaceArray sections to create mesh data."""
    vertices = []
    vertex_bones = []
    faces = []
    face_materials = []  # CRITICAL FIX: Store face-to-material mapping
    materials = []
    
    mode = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if line == 'DynamicVisual:':
            mode = 'vertices'
            continue
        elif line == 'Material:':
            mode = 'material'
            continue
        elif line == 'FaceArray:':
            mode = 'faces'
            continue
        elif line.startswith('<'):
            break
            
        if mode == 'vertices':
            # Use VF3's exact colon counting algorithm from ParseDynamicVisualData (0x4109b2)
            parts = line.split(':')
            colon_count = len(parts) - 1  # VF3's CountColonsInString logic
            
            if colon_count == 1:
                # Format: bone:index
                bone = parts[0]
                try:
                    idx = int(parts[1])
                except:
                    continue
                # Use default position for basic format
                vertices.append(((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)))
                vertex_bones.append(bone)
                
            elif colon_count == 3:
                # Format: bone:index:pos1:pos2
                bone = parts[0]
                try:
                    idx = int(parts[1])
                    pos1 = _parse_tuple3(parts[2])
                    pos2 = _parse_tuple3(parts[3])
                except:
                    continue
                vertices.append((pos1, pos2))
                vertex_bones.append(bone)
                
            elif colon_count == 4:
                # Format: bone:index:pos1:pos2:bone_types
                bone = parts[0]
                try:
                    idx = int(parts[1])
                    pos1 = _parse_tuple3(parts[2])
                    pos2 = _parse_tuple3(parts[3])
                    bone_types = parts[4]  # H/P/B classification
                except:
                    continue
                vertices.append((pos1, pos2))
                vertex_bones.append(bone)
                
            elif colon_count >= 5:
                # Extended format: bone:index:pos1:pos2:uv:bone_types
                bone = parts[0]
                try:
                    idx = int(parts[1])
                    pos1 = _parse_tuple3(parts[2])
                    pos2 = _parse_tuple3(parts[3])
                    uv = _parse_tuple2(parts[4]) if len(parts) > 4 else (0.0, 0.0)
                    bone_types = parts[5] if len(parts) > 5 else ""
                except:
                    continue
                vertices.append((pos1, pos2))
                vertex_bones.append(bone)
                
        elif mode == 'material':
            # Format: (r,g,b,a)::
            if line.startswith('(') and ')' in line:
                materials.append(line)
                
        elif mode == 'faces':
            # Format: v1,v2,v3:material_index
            if ',' in line and ':' in line:
                face_part, mat_idx = line.split(':', 1)
                try:
                    indices = [int(x) for x in face_part.split(',')]
                    material_index = int(mat_idx)  # CRITICAL FIX: Parse and store material index
                    if len(indices) == 3:
                        faces.append(indices)
                        face_materials.append(material_index)  # CRITICAL FIX: Store face-to-material mapping
                except:
                    continue
    
    if vertices and faces:
        return {
            'vertices': vertices,
            'vertex_bones': vertex_bones,
            'faces': faces,
            'face_materials': face_materials,  # CRITICAL FIX: Include face-to-material mapping
            'materials': materials,
            'original_faces': True  # Flag to indicate this has original VF3 FaceArray data
        }
    return None


def read_descriptor(file_path: str) -> Descriptor:
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = [ln.rstrip('\n') for ln in f]

    blocks: Dict[str, List[str]] = {}
    current_name: Optional[str] = None
    current_lines: List[str] = []
    for ln in lines:
        s = ln.strip()
        if s.startswith('<') and s.endswith('>') and not s.startswith('</') and s != '</>':
            # Block start with a specific name (rare). Most are like <frame>, <skin>, etc.
            pass
        if s.startswith('<') and not s.startswith('</') and s.endswith('>'):
            # Named block start like <frame>
            name = s.strip('<>').strip()
            current_name = name
            current_lines = []
            continue
        if s == '</>':
            if current_name is not None:
                blocks[current_name] = current_lines[:]
            current_name = None
            current_lines = []
            continue
        if current_name is not None:
            current_lines.append(ln)

    return Descriptor(path=file_path, blocks=blocks)


def parse_frame_bones(descriptor: Descriptor) -> Dict[str, Bone]:
    frame = descriptor.blocks.get('frame', [])
    bones: Dict[str, Bone] = {}
    for raw in frame:
        s = raw.strip()
        if not s or s.startswith('class:'):
            continue
        # Format: name:parent:(tx,ty,tz):(rx,ry,rz):flags:(sx,sy,sz)
        parts = s.split(':')
        if len(parts) < 3:
            continue
        name = parts[0].strip()
        parent = parts[1].strip() or None
        
        # Parse translation (required)
        try:
            translation = _parse_tuple3(parts[2])
        except Exception:
            translation = (0.0, 0.0, 0.0)
        
        # Parse rotation (optional)
        rotation = (0.0, 0.0, 0.0)
        if len(parts) > 3 and parts[3].strip():
            try:
                rotation = _parse_tuple3(parts[3])
            except Exception:
                rotation = (0.0, 0.0, 0.0)
        
        # Parse scale (optional, usually at index 5)
        scale = (1.0, 1.0, 1.0)
        if len(parts) > 5 and parts[5].strip():
            try:
                scale = _parse_tuple3(parts[5])
            except Exception:
                scale = (1.0, 1.0, 1.0)
        
        bones[name] = Bone(name=name, parent=parent, translation=translation, rotation=rotation, scale=scale)
    return bones


def parse_defaultcos(descriptor: Descriptor) -> List[str]:
    block = descriptor.blocks.get('defaultcos', [])
    names: List[str] = []
    for raw in block:
        s = raw.strip()
        if not s:
            continue
        # e.g. 'ciel.blazer'
        names.append(s)
    return names


def parse_skin_entries(descriptor: Descriptor) -> List[Tuple[str, str]]:
    # Returns list of (group_vector, identifier)
    block = descriptor.blocks.get('skin', [])
    entries: List[Tuple[str, str]] = []
    for raw in block:
        s = raw.strip()
        if not s:
            continue
        if ':' not in s:
            continue
        vec, ident = s.split(':', 1)
        entries.append((vec.strip(), ident.strip()))
    return entries


def _parse_attachment_line(raw: str) -> Optional[Attachment]:
    # Supported forms:
    # - bone:resource
    # - bone:::resource
    # - child:parent:(dx,dy,dz):resource
    s = raw.strip()
    if not s or s.startswith('class:'):
        return None
    if s.startswith('DynamicVisual:') or s.startswith('Material:') or s.startswith('FaceArray:'):
        return None
    if s.startswith('<') or s.startswith('</'):
        return None
    if ':' not in s:
        return None
    
    # Filter out lines that are just coordinate data or face indices
    if re.match(r'^[\d\s,\.\-\(\)]+$', s):
        return None
    
    parts = [p.strip() for p in s.split(':')]
    # Attempt to identify by length and tuple presence
    # Case 1: bone:resource
    if len(parts) == 2:
        # Additional validation: resource should not look like coordinates
        if re.match(r'^[\d\s,\.\-\(\)]+$', parts[1]):
            return None
        return Attachment(attach_bone=parts[0], resource_id=parts[1])
    # Case 2: bone:::resource len>=4 and parts[1]=='' and parts[2]==''
    if len(parts) >= 4 and parts[1] == '' and parts[2] == '':
        # Additional validation: resource should not look like coordinates
        if re.match(r'^[\d\s,\.\-\(\)]+$', parts[3]):
            return None
        return Attachment(attach_bone=parts[0], resource_id=parts[3])
    # Case 3: child:parent:(dx,dy,dz):resource
    if len(parts) >= 4 and parts[2].startswith('('):
        try:
            offs = _parse_tuple3(parts[2])
        except Exception:
            offs = (0.0, 0.0, 0.0)
        # Additional validation: resource should not look like coordinates
        if re.match(r'^[\d\s,\.\-\(\)]+$', parts[3]):
            return None
        return Attachment(attach_bone=parts[0], resource_id=parts[3], child_name=parts[0], parent_bone=parts[1], child_offset=offs)
    # Fallback: ignore lines like indices
    return None


def parse_attachment_block_lines(lines: List[str]) -> List[Attachment]:
    attachments: List[Attachment] = []
    for raw in lines:
        att = _parse_attachment_line(raw)
        if att is not None:
            attachments.append(att)
    return attachments


def _load_other_descriptor(prefix: str) -> Optional[Descriptor]:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(base_dir, 'data', f'{prefix}.TXT')
    if os.path.isfile(candidate):
        return read_descriptor(candidate)
    # Try lowercase.txt too
    candidate2 = os.path.join(base_dir, 'data', f'{prefix}.txt')
    if os.path.isfile(candidate2):
        return read_descriptor(candidate2)
    return None


def resolve_identifier_to_attachments(identifier: str, context_desc: Descriptor) -> Tuple[List[Attachment], Optional[Dict]]:
    # identifier like 'ciel.head' or 'female.arms' or 'rbt.defaultvisual'
    print(f"DEBUG: Resolving identifier '{identifier}'")
    if '.' not in identifier:
        return ([], None)
    prefix, suffix = identifier.split('.', 1)
    # Ignore malformed identifiers like 'ciel.' with empty suffix
    if not suffix:
        return ([], None)
    
    # Try current descriptor first
    if suffix in context_desc.blocks:
        attachments = parse_attachment_block_lines(context_desc.blocks[suffix])
        print(f"DEBUG: Found {len(attachments)} attachments in current descriptor for '{suffix}'")
        # Also check for DynamicVisual data
        dynamic_mesh = parse_dynamic_visual_mesh(context_desc.blocks[suffix])
        return (attachments, dynamic_mesh)
    
    # Try other descriptor file (e.g., female.TXT)
    other = _load_other_descriptor(prefix)
    if other:
        # Handle special grouped identifiers that map to multiple blocks in female.TXT
        grouped_mappings = {
            'arms': ['arms'],      # Maps to <arms> block containing l_arm1, l_arm2, r_arm1, r_arm2
            'legs': ['legs'],      # Maps to <legs> block containing l_leg1, l_leg2, r_leg1, r_leg2
            'foots': ['foots'],    # Maps to <foots> block containing l_foot, r_foot
            'body': ['body'],      # Maps to <body> block containing body, l_breast, r_breast
            'waist': ['waist'],    # Maps to <waist> block
        }
        
        # Check if this is a grouped identifier
        if suffix.lower() in grouped_mappings:
            all_attachments = []
            dynamic_mesh = None
            for block_name in grouped_mappings[suffix.lower()]:
                if block_name in other.blocks:
                    block_attachments = parse_attachment_block_lines(other.blocks[block_name])
                    print(f"DEBUG: Found grouped block '{block_name}' with {len(block_attachments)} attachments")
                    all_attachments.extend(block_attachments)
                    # Parse DynamicVisual data if present
                    block_dynamic = parse_dynamic_visual_mesh(other.blocks[block_name])
                    if block_dynamic:
                        print(f"DEBUG: Found DynamicVisual mesh with {len(block_dynamic['vertices'])} vertices, {len(block_dynamic['faces'])} faces")
                        dynamic_mesh = block_dynamic  # For now, just use the last one found
            print(f"DEBUG: Total attachments from grouped identifier '{suffix}': {len(all_attachments)}")
            return (all_attachments, dynamic_mesh)
        
        # Try direct block match
        if suffix in other.blocks:
            attachments = parse_attachment_block_lines(other.blocks[suffix])
            print(f"DEBUG: Found {len(attachments)} attachments in other descriptor for '{suffix}'")
            dynamic_mesh = parse_dynamic_visual_mesh(other.blocks[suffix])
            return (attachments, dynamic_mesh)
    
    print(f"DEBUG: No matching block found for '{suffix}', creating placeholder")
    # Else treat as direct mesh name to attach on an inferred bone later; return placeholder
    # We infer bone by suffix (e.g., 'head' -> 'head', 'body' -> 'body').
    inferred_bone = suffix if suffix in context_desc.blocks.get('frame', []) else suffix
    return ([Attachment(attach_bone=inferred_bone, resource_id=identifier)], None)


def collect_active_attachments(descriptor: Descriptor) -> Tuple[List[Attachment], List[Dict]]:
    attachments: List[Attachment] = []
    clothing_dynamic_meshes: List[Dict] = []
    
    # Base skin
    for _, ident in parse_skin_entries(descriptor):
        atts, dyn_mesh = resolve_identifier_to_attachments(ident, descriptor)
        attachments.extend(atts)
        if dyn_mesh:
            clothing_dynamic_meshes.append(dyn_mesh)
    
    # Default costumes
    for full in parse_defaultcos(descriptor):
        if '.' not in full:
            continue
        prefix, item = full.split('.', 1)
        item_block = descriptor.blocks.get(item)
        if not item_block:
            continue
        # Find vp target on the first mapping line in the item block
        for raw in item_block:
            s = raw.strip()
            if not s or ':' not in s or s.startswith('class:'):
                continue
            _, vp_ident = s.split(':', 1)
            vp_ident = vp_ident.strip()
            # vp_ident like 'ciel.blazer_vp'
            if '.' in vp_ident:
                _, vp_name = vp_ident.split('.', 1)
            else:
                vp_name = vp_ident
            vp_block = descriptor.blocks.get(vp_name)
            if vp_block:
                attachments.extend(parse_attachment_block_lines(vp_block))
                # CRITICAL: Also parse DynamicVisual data from clothing blocks!
                clothing_dyn_mesh = parse_dynamic_visual_mesh(vp_block)
                if clothing_dyn_mesh:
                    print(f"DEBUG: Found clothing DynamicVisual mesh in {vp_name} with {len(clothing_dyn_mesh['vertices'])} vertices")
                    clothing_dynamic_meshes.append(clothing_dyn_mesh)
            break
    
    # CRITICAL: Parse ALL *_vp blocks with DynamicVisual data
    # Many important connectors (like leg-to-foot) are in *_vp blocks not referenced in defaultcos
    processed_vp_blocks = set()
    
    # First, track which *_vp blocks were already processed in defaultcos
    for full in parse_defaultcos(descriptor):
        if '.' in full:
            prefix, item = full.split('.', 1)
            item_block = descriptor.blocks.get(item)
            if item_block:
                for raw in item_block:
                    s = raw.strip()
                    if ':' in s and not s.startswith('class:'):
                        _, vp_ident = s.split(':', 1)
                        vp_ident = vp_ident.strip()
                        if '.' in vp_ident:
                            _, vp_name = vp_ident.split('.', 1)
                        else:
                            vp_name = vp_ident
                        if vp_name.endswith('_vp'):
                            processed_vp_blocks.add(vp_name)
                        break
    
    print(f"DEBUG: Already processed *_vp blocks: {processed_vp_blocks}")
    
    # Now process remaining *_vp blocks with DynamicVisual data
    additional_dynamic_count = 0
    for block_name, block_lines in descriptor.blocks.items():
        if (block_name.endswith('_vp') and 
            block_name not in processed_vp_blocks and 
            any('DynamicVisual:' in line for line in block_lines)):
            
            additional_dyn_mesh = parse_dynamic_visual_mesh(block_lines)
            if additional_dyn_mesh:
                additional_dynamic_count += 1
                print(f"DEBUG: Found additional DynamicVisual mesh in {block_name} with {len(additional_dyn_mesh['vertices'])} vertices")
                clothing_dynamic_meshes.append(additional_dyn_mesh)
    
    if additional_dynamic_count > 0:
        print(f"DEBUG: Found {additional_dynamic_count} additional *_vp blocks with DynamicVisual data")
    
    return attachments, clothing_dynamic_meshes


def find_mesh_file(resource_id: str) -> Optional[str]:
    # resource_id like 'ciel.blazer' �� data/ciel/blazer.X or .x
    if '.' not in resource_id:
        return None
    prefix, name = resource_id.split('.', 1)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    folder = os.path.join(base_dir, 'data', prefix)
    if not os.path.isdir(folder):
        return None
    for ext in ('.X', '.x'):
        candidate = os.path.join(folder, f'{name}{ext}')
        if os.path.isfile(candidate):
            return candidate
    return None


def build_world_transforms(bones: Dict[str, Bone], extra_nodes: List[Attachment]) -> Dict[str, Tuple[float, float, float]]:
    # Build map of node name to world-space translation (ignore rotation/scale for minimal export)
    # Start with bone-local translations from <frame>
    local: Dict[str, Tuple[float, float, float]] = {b.name: b.translation for b in bones.values()}
    parent: Dict[str, Optional[str]] = {b.name: b.parent for b in bones.values()}
    # Add child nodes from attachments (e.g., skirt_f under waist with offset)
    for att in extra_nodes:
        if att.child_name and att.parent_bone and att.child_offset is not None:
            # Apply parent bone scaling to child frame offset
            parent_bone = bones.get(att.parent_bone)
            if parent_bone and parent_bone.scale != (1.0, 1.0, 1.0):
                scaled_offset = (
                    att.child_offset[0] * parent_bone.scale[0],
                    att.child_offset[1] * parent_bone.scale[1], 
                    att.child_offset[2] * parent_bone.scale[2]
                )
                local[att.child_name] = scaled_offset
                print(f"DEBUG: Scaled {att.child_name} offset from {att.child_offset} to {scaled_offset} using {att.parent_bone} scale {parent_bone.scale}")
            else:
                local[att.child_name] = att.child_offset
            parent[att.child_name] = att.parent_bone

    world: Dict[str, Tuple[float, float, float]] = {}

    def accumulate(n: str) -> Tuple[float, float, float]:
        if n in world:
            return world[n]
        p = parent.get(n)
        t = local.get(n, (0.0, 0.0, 0.0))
        if p is None or p == '' or p not in local:
            world[n] = t
            return t
        pt = accumulate(p)
        wt = (pt[0] + t[0], pt[1] + t[1], pt[2] + t[2])
        world[n] = wt
        return wt

    for n in list(local.keys()):
        accumulate(n)
    return world


