"""Method to translate a Aperture to a VisualizationSet."""
from ladybug_display.geometry3d import DisplayFace3D
from ladybug_display.visualization import VisualizationSet, ContextGeometry


def aperture_to_vis_set(aperture, color_by='type'):
    """Translate a Honeybee Aperture to a VisualizationSet.

    Args:
        aperture: A Honeybee Aperture object to be converted to a VisualizationSet.
        color_by: Text for the property that dictates the colors of the Aperture
            geometry. (Default: type). Choose from the following:

            * type
            * boundary_condition

    Returns:
        A VisualizationSet object that represents the Aperture with a
        single ContextGeometry.
    """
    # get the basic properties for geometry conversion
    color_by_attr = 'type_color' if color_by.lower() == 'type' else 'bc_color'
    d_mod = 'SurfaceWithEdges'
    # convert all geometry into DisplayFace3D
    dis_geos = []
    a_col = getattr(aperture, color_by_attr)
    dis_geos.append(DisplayFace3D(aperture.geometry, a_col, d_mod))
    for shd in aperture.shades:
        s_col = getattr(shd, color_by_attr)
        dis_geos.append(DisplayFace3D(shd.geometry, s_col, d_mod))
    # build the VisualizationSet and ContextGeometry
    con_geo = ContextGeometry(aperture.identifier, dis_geos)
    con_geo.display_name = aperture.display_name
    vis_set = VisualizationSet(aperture.identifier, [con_geo])
    vis_set.display_name = aperture.display_name
    return vis_set
