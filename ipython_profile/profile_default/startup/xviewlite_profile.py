from databroker.v0 import Broker
from PyQt5.QtWidgets import QApplication
from PyQt5 import uic, QtCore
import sys
import sys
from xviewlite import xview
# from xview.spectra_db.db_io import get_spectrum_catalog
import os
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
plt.ion()

import sys
sys.stdout.write('\33]0;XView terminal\a')
sys.stdout.flush()

try:
    db = Broker.named('iss')
    print('db connected')
except Exception as e:
    print(f'Failed to open ISS databroker: {e}')
    db = None

db = Broker.named('iss')
app = QApplication(sys.argv)
app.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
xview_gui = xview.XviewGui()
# xview_gui = xview.XviewGui(db=None, db_proc=None, db_archive_catalog=None, db_catalog=None)

def xview():
    xview_gui.show()

xview()