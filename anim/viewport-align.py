import bpy
from mathutils import Matrix
import bpy_extras

#3 Align Object in Camera Viewport
##
## Blender Python script by Josh R (GitHub user Botmasher)

# /!\ Caution - current implementation slows with vertex count
# /!\ (may loop over vertices multiple times)

# Base implementation
# - determine point at center of camera x,y
# - determine focal point for camera z
# - place object at point
# - scale object to fit within frustum
#   - account for all points (or just normals) in mesh

# TODO align non-mesh objects like text (or separate?)

def is_translatable(*objs):
    """Determine if the object exists and is movable"""
    for obj in objs:
        if not obj or not obj.location:
            return False
    return True

## TODO iterate on center_obj() for better alignment
##  FUTURE: determine when object scaled to fit within view
##      - requires point detection?
##      - allow adjusting scale within view (like calculate view size * 0.5)

## newer iteration on center align
def center_in_cam_view(obj=bpy.context.object, cam=bpy.context.scene.camera, distance=0.0, snap=False):
    if not is_translatable(obj, cam):
        return

    # move and rotate obj to cam
    obj.location = cam.location
    obj.rotation_euler = cam.rotation_euler
    v = (0.0, 0.0, -distance)

    # local move away cam using matrix translation
    # https://blender.stackexchange.com/questions/82265/move-object-along-local-axis-with-python-api
    if snap:
        # parent to camera
        obj.parent = cam
        obj.matrix_basis = Matrix.Translation(v)
    else:
        obj.matrix_basis *= Matrix.Translation(v)

    return obj

## test call
#center_in_cam_view(distance=5.0)

# Find object edges vs camera view edges

def get_frustum_loc(point, cam=bpy.context.scene.camera, scene=bpy.context.scene):
    """Determine location of a point within camera's rendered frame"""
    if not point or not cam or not scene:
        return
    # scene to use for frame size
    # Camera object
    # World space location (mathutils.Vector)
    uv_loc = bpy_extras.object_utils.world_to_camera_view(scene, cam, point)
    # returns a Vector magnitude 3 with valid cam positions between 0<=uv_loc<=1
    #   - values for index 0,1 greater than 1 are above top-right of frame
    #   - values at index 2 less than 0 are behind camera
    return uv_loc

def is_frustum_loc(point, cam=bpy.context.scene.camera, scene=bpy.context.scene):
    """Check if a point falls within camera's rendered frame"""
    if not point or not cam or not scene: return
    uv_loc = bpy_extras.object_utils.world_to_camera_view(scene, cam, point)
    return (0.0 <= uv_loc[0] <= 1.0 and 0.0 <= uv_loc[1] <= 1.0 and uv_loc[2] >= 0.0)

def has_mesh(obj):
    """Check if the object contains mesh data"""
    if hasattr(obj.data, 'vertices'):
        return True
    return False

def is_camera(obj):
    """Check if the object is a Camera"""
    if obj and hasattr(obj, 'type') and obj.type == 'CAMERA':
        return True
    return False

def get_edge_vertices_uv_xy(obj, cam):
    """Find the rightmost, leftmost, topmost and bottommost vertex in camera view
    Return render UV and the world XY coordinates for these extremes
    """
    if not has_mesh(obj) or not is_camera(cam): return
    edges = {'u': [None, None], 'v': [None, None], 'x': [None, None], 'y': [None, None]}
    for v in obj.data.vertices:
        v_uv = get_frustum_loc(obj.matrix_world * v.co, cam=cam)
        # TODO add vertex to edges if it is more positive or negative than stored extreme edges
        # zeroth value for L/bottom of render screen, first value for R/top render screen
        edge_units = [{'uv': 'u', 'xy': 'x'}, {'uv': 'v', 'xy': 'y'}]
        for i in range(len(edge_units)):
            uv, xy = *(edge_units[i]['uv'] + edge_units[i]['xy'])
            if edges[uv][0] is None or v_uv[i] < edges[uv][0]:
                edges[uv][0] = v_uv[i]
                edges[xy][0] = obj.matrix_world * v.co[i]
            if edges[uv][1] is None or v_uv[i] > edges[uv][1]:
                edges[uv][1] = v_uv[i]
                edges[xy][1] = obj.matrix_world * v.co[i]
    return edges

def scale_vertices_to_uv(obj, width_u, height_v):
    """Rescale object of known UV width and height to fit within render UV"""
    overscale_x = width - 1.0
    overscale_y = height - 1.0
    # needs scaled
    overscale = 0
    if overscale_x > 0 or overscale_y > 0:
        # use highest x or y to scale down uniformly
        overscale = overscale_y if overscale_y > overscale_x else overscale_x
        obj.scale /= 1 + (overscale * 2)    # double to account for both sides
    return (overscale_x, overscale_y)

def move_vertices_to_uv(obj, width_u, height_u, edges):
    """Move a viewport-sized object entirely within render UV"""
    # store object's extreme UV points and distances
    uv_edges_flat = edges['u'] + edges['v']
    dimensions_uv = {'w': width_u, 'h': height_u}
    #dimensions_xy = {'w': edges['x'][1] - edges['x'][0], 'h': edges['y'][1] - edges['y'][1]}

    # obj needs moved
    if max(uv_edges_flat, 1.0) > 1 or min(uv_edges_flat, 0.0) < 0:

        # new uv point at bottom left (leaving margin on all sides)
        target_uv = {}
        for d in dimensions_uv.keys():
            target_uv[d]['low'] = (1 - dimensions_uv[d]) / 2
            target_uv[d]['high'] = dimensions_uv[d]

        # new x,y point at bottom left = (obj_xy / obj_uv) * new_target_uv
        target_xy = {}
        for d in target_uv.keys():
            axis = 'x' if d == 'u' else 'y'
            target_xy[axis]['high'] = (edges[axis][1] / edges[d][1]) * target_uv[d]['high']
            target_xy[axis]['low'] = (edges[axis][0] / edges[d][0]) * target_uv[d]['low']

        new_delta_x = target_xy['x']['high'] - target_xy['x']['low']
        new_delta_y =target_xy['y']['high'] - target_xy['y']['low']
        new_x = obj.location.x + new_delta_x
        new_y = obj.location.y + new_delta_y

        obj.location = (new_x, new_y, obj.location.z)

    return obj

# Fit based on vertex extremes NOT object center
# - calculate obj vertex X-Y extremes
# - figure out their center and distance
# - use the VERTEX center to align object in cam
def fit_vertices_to_frustum(obj, cam, move=True, calls_remaining=10):
    if not has_mesh(obj) or not is_camera(cam) or len(obj.data.vertices) < 1:
        return

    # NOTE edges dict stores uv/xy keys with two-element array values storing low and high extremes
    #      { 'u': [], 'v': [], 'x': [], 'y': [] }
    edges = get_edge_vertices_uv_xy(obj, cam)
    if not edges: return

    # TODO then calculate this as a ratio of units needed to move
    # - how much must this object scale to fit within frustum?
    # - then, how much would it need to move for that scaled object to be entirely visible to current cam?
    width = edges['u'][1] - edges['u'][0]
    height = edges['v'][1] - edges['v'][0]

    scale_vertices_to_uv(obj, width, height)

    # call again to verify scaledown - double check scaled object fit
    #if move and calls_remaining > 0:
    #    # TODO instead of recursing calculate expected loc of scaledown points then update move dimensions
    #    # see correctly scaled move else branch below
    #    fit_vertices_to_frustum(obj, cam, calls_remaining=calls_remaining-1)
    #else:
    #    print("Failed to correctly size and position object to viewport - method exceeded expected number of recursive calls")
    #    return obj

    if move:
        move_vertices_to_uv(obj, width, height, edges)
    return obj

# test
fit_vertices_to_frustum(bpy.context.object, bpy.context.scene.camera)

# TODO allow stretch (non-uniform scale)
# TODO move instead of scale if object could fit
#   - may want to move if object center is outside frustum
#   - alternatively guard check if obj inside frustum in the first place
def fit_to_frustum(obj, cam=bpy.context.scene.camera, move_into_view=True, margin=0.0, distance=5.0, distort=False):
    if not has_mesh(obj) or not is_camera(cam):
        return
    vertex_extremes = [0.0, 0.0, 0.0]
    # calculate mesh vertices far outside of viewport
    # TODO rework calculations here to store XY excess only at this step
    overflow_high = 0.0
    move_loc = obj.location
    for vertex in obj.data.vertices:
        uvz = get_frustum_loc(obj.matrix_world * vertex.co, cam=cam)
        # shallow Z location closest to camera (negative is behind)
        if uvz[2] < 0 and abs(uvz[2]) > abs(vertex_extremes[2]):
            # TODO handle Z index behind cam
            # use high negative w to move object in front of cam and recurse for u,v
            # move into cam view and retry
            center_in_cam_view(obj=obj, cam=cam, distance=distance)
            return fit_to_frustum(obj, cam=cam, move_into_view=False, margin=margin, distance=distance, distort=distort)
        # cut off and store excess (outside range 0-1)
        overflows = [max(0, d - 1.0) if d > 0 else d for d in uvz]
        # keep track of highest excess found so far
        vertex_extremes = [overflows[i] if abs(overflows[i]) > abs(vertex_extremes[i]) else vertex_extremes[i] for i in range(len(vertex_extremes))]
    # farthest XY locations outside UV render frame
    overflow_high = max(abs(overflows[0]), abs(overflows[1]))

    # use high UV to rescale object
    # TODO check meshes entirely out of viewport (move into view?)
    # adjust calc so mesh ends up fully inside (see vertex loop at top of method)
    # EITHER    double change to account for both sides (e.g. top AND bottom)
    # OR        move in opposite direction
    overflow_high *= 2              # account for excess on both sides
    obj.scale /= 1 + overflow_high
    #obj.location = move_loc        # move for both sides

    print("\nObj vertices in render space: {0}".format(vertex_extremes))
    print("Attempting to adjust by {0}".format(overflow_high))

    ## TODO move realign
    ##  - center first, check again then move
    ##  - centering first above avoids dealing with outside values
    #for i in range(len(vertex_extremes)):
    #    move_loc[i] *= vertex_extremes[i]

    return vertex_extremes

# test
#fit_to_frustum(bpy.context.object, margin=1.0)
