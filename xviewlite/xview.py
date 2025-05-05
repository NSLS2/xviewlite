import sys
from importlib import resources
from PyQt5 import  QtWidgets, uic

from .xviewlite.xasproject.xasproject import XASProject

from widgets import widget_xview_data, widget_xview_project
if sys.platform == 'darwin':
    with resources.path('xviewlite.ui', 'ui_xview-mac.ui') as path:
        ui_path = str(path)
        print('mac')
else:
    with resources.path('xviewlite.ui', 'ui_xview.ui') as path:
        ui_path = str(path)

class XviewGui(*uic.loadUiType(ui_path)):
    def __init__(self,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.project = XASProject()

        self.widget_data = widget_xview_data.UIXviewData( parent=self)
        self.layout_data.addWidget(self.widget_data)

        self.widget_project = widget_xview_project.UIXviewProject(parent=self)
        self.layout_project.addWidget(self.widget_project)

    def set_figure(self, axis, canvas, label_x='', label_y=''):
        axis.legend(fontsize='small')
        axis.grid(alpha=0.4)
        axis.set_ylabel(label_y, size='13')
        axis.set_xlabel(label_x, size='13')
        canvas.draw_idle()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    main = XviewGui()
    main.show()
    sys.exit(app.exec_())
