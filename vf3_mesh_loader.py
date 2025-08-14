"""
VF3 Mesh Loader
Pure modular implementation for loading .X files and other mesh formats.
Uses the complete XFile parser from vf3_xfile_parser.py
"""

import os
import sys
import trimesh
import numpy as np
from typing import Dict, Optional, List, Any

from vf3_xfile_parser import load_mesh_with_materials, load_mesh_simple as xfile_load_simple


def load_mesh_simple(path: str) -> Optional[trimesh.Trimesh]:
    """
    Load mesh file with fallback support for different formats.
    Uses the complete XFile parser for .X files.
    """
    if not os.path.exists(path):
        return None
    
    # Use the complete XFile parser for .X files
    if path.lower().endswith('.x'):
        try:
            return xfile_load_simple(path)
        except Exception as e:
            print(f"XFile parser failed for {path}: {e}")
            return None
    
    # Fallback to trimesh for other formats
    try:
        mesh = trimesh.load(path)
        if isinstance(mesh, trimesh.Trimesh):
            return mesh
        elif hasattr(mesh, 'geometry') and mesh.geometry:
            # If it's a scene, get the first geometry
            first_geom = list(mesh.geometry.values())[0]
            if isinstance(first_geom, trimesh.Trimesh):
                return first_geom
    except Exception as e:
        print(f"Trimesh failed to load {path}: {e}")
    
    return None


def load_mesh_with_full_materials(path: str) -> dict:
    """
    Load mesh with complete material and texture information.
    Uses the complete XFile parser with materials for .X files.
    """
    if not os.path.exists(path):
        return {'mesh': None, 'materials': [], 'textures': []}
    
    # Use the complete XFile parser with materials for .X files
    if path.lower().endswith('.x'):
        try:
            return load_mesh_with_materials(path)
        except Exception as e:
            print(f"XFile parser with materials failed for {path}: {e}")
            return {'mesh': None, 'materials': [], 'textures': []}
    
    # Fallback for other formats (no materials)
    try:
        mesh = load_mesh_simple(path)
        return {
            'mesh': mesh,
            'materials': [],
            'textures': []
        }
    except Exception as e:
        print(f"Failed to load mesh {path}: {e}")
        return {'mesh': None, 'materials': [], 'textures': []}