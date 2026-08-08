from matplotlib.legend_handler import HandlerBase
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D

class DoubleMarkerHandler(HandlerBase):
    def create_artists(self, legend, orig_handle,
                       xdescent, ydescent, width, height,
                       fontsize, trans):

        line = Line2D(
            [xdescent + width*0.2],
            [ydescent + height/2],
            marker=orig_handle.get_marker(),
            linestyle='',
            color=orig_handle.get_color(),
            markersize=orig_handle.get_markersize(),
            transform=trans,
        )

        box = Rectangle(
            (xdescent + width*0.65, ydescent + height*0.25),
            width*0.2,
            height*0.5,
            facecolor="red",
            edgecolor="black",
            transform=trans,
        )

        return [line, box]