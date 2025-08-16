"""
VF3 Occupancy System
Handles the 7-slot occupancy vector system for clothing replacement logic.
"""

from typing import List, Dict, Any, Optional


def parse_occupancy_vector(occ_str: str) -> List[int]:
    """Parse occupancy string like '0,3,3,0,0,0,0' into list of integers."""
    try:
        return [int(x) for x in occ_str.split(',')]
    except ValueError:
        return [0, 0, 0, 0, 0, 0, 0]  # Default if parsing fails


def filter_attachments_by_occupancy_with_dynamic(skin_attachments: List[Dict[str, Any]], clothing_attachments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    CRITICAL: Implement VF3's replacement system with DynamicVisual mesh filtering.
    Higher occupancy values override lower ones in same slot.
    
    The 7-slot occupancy vector: [head, body, arms, hands, waist, legs, feet]
    """
    print(f"OCCUPANCY FILTER: Processing {len(skin_attachments)} skin + {len(clothing_attachments)} clothing attachments")
    
    # Track the winner for each slot (0-6)
    slot_winners: Dict[int, Dict[str, Any]] = {}
    
    # Process all attachments (skin + clothing)
    all_attachment_groups = [
        ('SKIN', skin_attachments),
        ('CLOTHING', clothing_attachments)
    ]
    
    for group_name, attachment_list in all_attachment_groups:
        for attachment_data in attachment_list:
            occupancy = attachment_data['occupancy']
            source = attachment_data['source']
            attachments = attachment_data['attachments']
            dynamic_mesh = attachment_data.get('dynamic_mesh')
            
            # Handle special case: if all occupancy values are 0, treat as occupying a special "default" slot
            has_any_occupancy = any(occ > 0 for occ in occupancy)
            if not has_any_occupancy:
                # For zero-occupancy entries (like robots), assign to a special slot -1
                slot_idx = -1
                occ_value = 1
                current_winner = slot_winners.get(slot_idx)
                
                if current_winner is None or occ_value >= current_winner['occupancy']:
                    action = "REPLACED" if current_winner else "occupied"
                    slot_winners[slot_idx] = {
                        'occupancy': occ_value,
                        'source': source,
                        'attachments': attachments,
                        'dynamic_mesh': dynamic_mesh
                    }
                    print(f"  {group_name}: Special slot {slot_idx} {action} by {source} (zero-occupancy)")
            else:
                # Normal processing for non-zero occupancy
                for slot_idx, occ_value in enumerate(occupancy):
                    if occ_value > 0:  # This source occupies this slot
                        current_winner = slot_winners.get(slot_idx)
                        
                        # SPECIAL CASE: Handle bilateral body parts (both hands should be included in naked mode)
                        is_bilateral_body_part = (
                            slot_idx == 3 and  # hands slot
                            group_name == 'SKIN' and
                            ('female.l_hand' in source or 'female.r_hand' in source)
                        )
                        
                        if is_bilateral_body_part and current_winner and group_name == 'SKIN':
                            # For bilateral body parts in skin mode, merge instead of replace
                            print(f"  {group_name}: Slot {slot_idx} - Merging bilateral part {source} with existing {current_winner['source']}")
                            current_winner['attachments'].extend(attachments)
                            
                            # Merge DynamicVisual data for bilateral parts
                            if dynamic_mesh:
                                if not current_winner['dynamic_mesh']:
                                    current_winner['dynamic_mesh'] = dynamic_mesh
                                else:
                                    # Merge the two DynamicVisual meshes
                                    existing_mesh = current_winner['dynamic_mesh']
                                    merged_vertices = existing_mesh['vertices'] + dynamic_mesh['vertices']
                                    merged_faces = existing_mesh['faces'] + [
                                        [f[0] + len(existing_mesh['vertices']), f[1] + len(existing_mesh['vertices']), f[2] + len(existing_mesh['vertices'])]
                                        for f in dynamic_mesh['faces']
                                    ]
                                    merged_vertex_bones = existing_mesh.get('vertex_bones', []) + dynamic_mesh.get('vertex_bones', [])
                                    
                                    current_winner['dynamic_mesh'] = {
                                        'vertices': merged_vertices,
                                        'faces': merged_faces,
                                        'vertex_bones': merged_vertex_bones
                                    }
                                    print(f"    DynamicVisual: Merged {len(dynamic_mesh['vertices'])} vertices from {source} with existing mesh")
                        elif current_winner is None:
                            # First source to occupy this slot
                            slot_winners[slot_idx] = {
                                'occupancy': occ_value,
                                'source': source,
                                'attachments': attachments,
                                'dynamic_mesh': dynamic_mesh,
                                'layers': [{'source': source, 'attachments': attachments, 'occupancy': occ_value}]
                            }
                            print(f"  {group_name}: Slot {slot_idx} occupied by {source} with occupancy {occ_value}")
                        elif occ_value > current_winner['occupancy']:
                            # VF3 Occupancy Rules:
                            # - Occupancy 2: ADDITIVE (costume + underwear both kept)
                            # - Occupancy 3: REPLACEMENT (only costume kept, underwear discarded)
                            
                            if occ_value == 2:
                                # ADDITIVE: Keep both base and costume (e.g., skirt + underwear)
                                if 'layers' not in current_winner:
                                    current_winner['layers'] = [{'source': current_winner['source'], 'attachments': current_winner['attachments'], 'occupancy': current_winner['occupancy']}]
                                
                                # Add new layer on top, keeping base layer
                                current_winner['layers'].append({'source': source, 'attachments': attachments, 'occupancy': occ_value})
                                
                                # Update primary winner to highest occupancy
                                current_winner.update({
                                    'occupancy': occ_value,
                                    'source': source,
                                    'attachments': attachments,
                                    'dynamic_mesh': dynamic_mesh
                                })
                                print(f"  {group_name}: Slot {slot_idx} ADDITIVE by {source} with occupancy {occ_value} (keeping base layer)")
                                
                            elif occ_value >= 3:
                                # REPLACEMENT: Completely replace base with costume (e.g., blazer replaces skin)
                                current_winner.update({
                                    'occupancy': occ_value,
                                    'source': source,
                                    'attachments': attachments,
                                    'dynamic_mesh': dynamic_mesh
                                })
                                # Remove layers to indicate complete replacement
                                if 'layers' in current_winner:
                                    del current_winner['layers']
                                print(f"  {group_name}: Slot {slot_idx} REPLACED by {source} with occupancy {occ_value} (discarding base layer)")
                            
                            else:
                                # For occupancy 1 or unknown, default to replacement
                                current_winner.update({
                                    'occupancy': occ_value,
                                    'source': source,
                                    'attachments': attachments,
                                    'dynamic_mesh': dynamic_mesh
                                })
                                if 'layers' in current_winner:
                                    del current_winner['layers']
                                print(f"  {group_name}: Slot {slot_idx} DEFAULT REPLACED by {source} with occupancy {occ_value}")
                        else:
                            print(f"  {group_name}: Slot {slot_idx} - {source} (occupancy {occ_value}) loses to existing winner (occupancy {current_winner['occupancy']})")
    
    # Collect final results
    final_attachments = []
    final_dynamic_meshes = []
    seen_dynamic_meshes = set()  # Track sources to avoid duplicates
    seen_attachment_sources = set()  # Track attachment sources to avoid duplicates
    
    for slot_idx, winner in slot_winners.items():
        # Process according to VF3 occupancy rules
        if 'layers' in winner:
            # ADDITIVE (occupancy 2): Include all layers (base + costume)
            print(f"  FINAL: Slot {slot_idx} ADDITIVE with {len(winner['layers'])} layers:")
            for layer_idx, layer in enumerate(winner['layers']):
                layer_source = layer['source']
                layer_attachments = layer['attachments']
                
                # Add all layer attachments, but avoid duplicates from same source across layers
                if layer_source not in seen_attachment_sources:
                    final_attachments.extend(layer_attachments)
                    seen_attachment_sources.add(layer_source)
                    print(f"    Layer {layer_idx}: {len(layer_attachments)} attachments from {layer_source} (occupancy {layer['occupancy']})")
                else:
                    print(f"    Layer {layer_idx}: attachments from {layer_source} (DUPLICATE - SKIPPED)")
        else:
            # REPLACEMENT (occupancy 3) or single layer: Include only winner
            source_key = winner['source']
            if source_key not in seen_attachment_sources:
                final_attachments.extend(winner['attachments'])
                seen_attachment_sources.add(source_key)
                if winner['occupancy'] >= 3:
                    print(f"  FINAL: Slot {slot_idx} REPLACEMENT -> {len(winner['attachments'])} attachments from {winner['source']} (base discarded)")
                else:
                    print(f"  FINAL: Slot {slot_idx} SINGLE -> {len(winner['attachments'])} attachments from {winner['source']}")
            else:
                if winner['occupancy'] >= 3:
                    print(f"  FINAL: Slot {slot_idx} REPLACEMENT -> attachments from {winner['source']} (DUPLICATE - SKIPPED)")
                else:
                    print(f"  FINAL: Slot {slot_idx} SINGLE -> attachments from {winner['source']} (DUPLICATE - SKIPPED)")
        
        # Handle dynamic mesh (always from top layer)
        if winner['dynamic_mesh']:
            # Use source as key to deduplicate DynamicVisual meshes from same source
            source_key = winner['source']
            if source_key not in seen_dynamic_meshes:
                # Add source information to the DynamicVisual data for material assignment
                dynamic_mesh_with_source = winner['dynamic_mesh'].copy()
                dynamic_mesh_with_source['source_info'] = {'source': winner['source']}
                final_dynamic_meshes.append(dynamic_mesh_with_source)
                seen_dynamic_meshes.add(source_key)
                print(f"    DynamicVisual from {winner['source']} (ADDED)")
            else:
                print(f"    DynamicVisual from {winner['source']} (DUPLICATE - SKIPPED)")
    
    print(f"OCCUPANCY FILTER: Final result: {len(final_attachments)} attachments, {len(final_dynamic_meshes)} dynamic meshes (deduplicated)")
    
    return {
        'attachments': final_attachments,
        'dynamic_meshes': final_dynamic_meshes
    }
