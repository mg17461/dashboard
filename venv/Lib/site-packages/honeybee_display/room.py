"""Method to translate a Room to a VisualizationSet."""
from ladybug_display.visualization import VisualizationSet, ContextGeometry

from .face import _face_display_geometry, _add_display_shade


def room_to_vis_set(room, color_by='type'):
    """Translate a Honeybee Room to a VisualizationSet.

    Args:
        room: A Honeybee Room object to be converted to a VisualizationSet.
        color_by: Text for the property that dictates the colors of the Room
            geometry. (Default: type). Choose from the following:

            * type
            * boundary_condition

    Returns:
        A VisualizationSet object that represents the Room with a single ContextGeometry.
    """
    # get the basic properties for geometry conversion
    color_by_attr = 'type_color' if color_by.lower() == 'type' else 'bc_color'
    # convert all geometry into DisplayFace3D
    dis_geos = []
    for face in room.faces:
        dis_geos.extend(_face_display_geometry(face, color_by_attr))
    _add_display_shade(room, dis_geos, color_by_attr)
    # build the VisualizationSet and ContextGeometry
    con_geo = ContextGeometry(room.identifier, dis_geos)
    con_geo.display_name = room.display_name
    vis_set = VisualizationSet(room.identifier, [con_geo])
    vis_set.display_name = room.display_name
    return vis_set
