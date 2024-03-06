"""Method to translate a ShadeMesh to a VisualizationSet."""
from ladybug_display.geometry3d import DisplayMesh3D
from ladybug_display.visualization import VisualizationSet, ContextGeometry



def shade_mesh_to_vis_set(shade, color_by='type'):
    """Translate a Honeybee ShadeMesh to a VisualizationSet.

    Args:
        shade: A Honeybee ShadeMesh object to be converted to a VisualizationSet.
        color_by: Text for the property that dictates the colors of the Shade
            geometry. (Default: type). Choose from the following:

            * type
            * boundary_condition

    Returns:
        A VisualizationSet object that represents the ShadeMesh with a
        single ContextGeometry.
    """
    # get the basic properties for geometry conversion
    color_by_attr = 'type_color' if color_by.lower() == 'type' else 'bc_color'
    d_mod = 'SurfaceWithEdges'
    # convert all geometry into DisplayFace3D
    a_col = getattr(shade, color_by_attr)
    dis_geos = [DisplayMesh3D(shade.geometry, a_col, d_mod)]
    # build the VisualizationSet and ContextGeometry
    con_geo = ContextGeometry(shade.identifier, dis_geos)
    con_geo.display_name = shade.display_name
    vis_set = VisualizationSet(shade.identifier, [con_geo])
    vis_set.display_name = shade.display_name
    return vis_set
