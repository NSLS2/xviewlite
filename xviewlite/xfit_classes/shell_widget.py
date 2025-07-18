from PyQt5 import uic
import os

path = os.sys.path[-1] + '/ui/'
class Shell(*uic.loadUiType(path + 'ui_shell.ui')):
    def __init__(self):
        super().__init__()
        self.setupUi(self)


# if __name__ == '__main__':
#     app = QtWidgets.QApplication([])
#     window = Shell()
#     window.show()
#     exit(app.exec_())