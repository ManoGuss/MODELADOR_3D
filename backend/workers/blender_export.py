"""Executed only by an installed Blender, with FORGE-owned request paths."""
import json
import sys
from pathlib import Path
import bpy

request = json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf-8'))
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = 1
bpy.ops.import_scene.gltf(filepath=request['input'])


def measure():
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    return {'meshes': len(meshes), 'vertices': sum(len(o.data.vertices) for o in meshes),
            'polygons': sum(len(o.data.polygons) for o in meshes),
            'bones': sum(len(o.data.bones) for o in bpy.context.scene.objects if o.type == 'ARMATURE'),
            'materials': len(bpy.data.materials), 'actions': len(bpy.data.actions),
            'dimensions': [list(o.dimensions) for o in meshes]}


before = measure()
if not before['meshes']:
    raise RuntimeError('Nenhuma mesh importada no Blender.')
bpy.ops.export_scene.fbx(filepath=request['output'], use_selection=False, object_types={'MESH', 'ARMATURE', 'EMPTY'},
                         global_scale=1.0, apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
                         axis_forward='-Z', axis_up='Y', add_leaf_bones=False, use_custom_props=True,
                         bake_anim=True, bake_anim_use_all_actions=False, path_mode='COPY', embed_textures=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=request['output'], use_anim=True)
after = measure()
if not after['meshes'] or before['vertices'] != after['vertices'] or before['bones'] != after['bones']:
    raise RuntimeError('Round trip FBX alterou contagem de vértices ou skeleton.')
source_dimensions = sorted(before['dimensions'])
result_dimensions = sorted(after['dimensions'])
if len(source_dimensions) != len(result_dimensions) or any(abs(a-b) > max(.001, abs(a)*.01) for p,q in zip(source_dimensions,result_dimensions) for a,b in zip(p,q)):
    raise RuntimeError('Round trip FBX alterou dimensões além de 1%.')
Path(request['report']).write_text(json.dumps({'blender': bpy.app.version_string, 'before': before, 'after': after,
                                             'validated': ['mesh', 'vertex_count', 'bone_count', 'dimensions'],
                                             'warnings': ['Equivalência visual de materiais, deformação e animações requer validação na engine.']}), encoding='utf-8')
