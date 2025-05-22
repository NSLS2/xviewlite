import os
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import pkg_resources

from PyQt5 import  QtWidgets, QtCore, uic
from PyQt5.QtCore import QSettings, QThread
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QMenu
from PyQt5.Qt import Qt
# from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, \
#     NavigationToolbar2QT as NavigationToolbar

from sys import platform
from pymatgen.io.feff.sets import MPXANESSet, MPEXAFSSet, FEFFDictSet
from xraydb import atomic_symbol
from larch.xafs.feffutils import get_feff_pathinfo
from xviewlite.xfit_classes.lightshow_pymatgen_bug_fix import FEFFDictSet_modified
from xviewlite.xfit_classes.plotting_tools import MplCanvas, create_pyqtgraph_widget
from xviewlite.xfit_classes.pyqtgraph_widget import create_pyqtgraph_widget
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT
from larch.xafs import xftf
from larch.xafs.feffdat import ff2chi, feffpath
from larch.symboltable import Group
from pathlib import Path
from pyqtgraph import mkPen

from matplotlib.figure import Figure
# from xas.xasproject import XASDataSet
# from isstools.elements.figure_update import update_figure
# from isstools.dialogs.BasicDialogs import message_box
# from xas.file_io import load_binned_df_from_file, load_binned_df_and_extended_data_from_file
import copy
from xviewlite.dialogs.FileMetadataDialog import FileMetadataDialog
from xviewlite.xfit_classes.workers import Worker_Retrive_MatProj_Data as worker_matproj
from xviewlite.xfit_classes.workers import Worker_Run_Feff_Calculation as worker_feff
from xviewlite.xfit_classes.utils import read_lineEdit_and_perform_sanity_check, get_default_feff_parameters, Shell
from scipy.interpolate import interp1d

if platform == 'darwin':
    ui_path = pkg_resources.resource_filename('xview', 'ui/ui_xfit.ui')
else:
    ui_path = pkg_resources.resource_filename('xview', 'ui/ui_xfit.ui')


ATOMIC_SYMBOL_DICT = {'element': [atomic_symbol(i) for i in range(20, 93)]}
EDGES = {'edges': ['K', 'L3', 'L2', 'L1', 'M5']}

STRUCTURE_FOLDER = os.path.join(pkg_resources.resource_filename('xviewlite', ''), 'structure_data')
os.makedirs(STRUCTURE_FOLDER, exist_ok=True)


class UIXFIT(*uic.loadUiType(ui_path)):
    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent = parent

        self.pushButton_search_matproj.clicked.connect(self.search_the_structure_from_materials_project)
        self.pushButton_run_feff.clicked.connect(self.perform_feff_calculation)
        self.pushButton_list_path.clicked.connect(self.populate_scattering_paths)
        self.material_project_data = {}
        self.structure_found = False
        self.path_added = False
        self.treeWidget_paths_dict = {}
        self.create_plot_item_for_simulated_chi()
        self.create_plot_item_for_simulated_ft()
        self.pushButton_add_scattering_path.clicked.connect(self.plot_scattering_path)

        windows = ['sine', 'hanning', 'parzen', 'welch', 'gaussian', 'kaiser']

        for key in ['', '_sim']:
            getattr(self, 'comboBox_window' + key).addItems(windows)

        self.pushButton_add_shells_to_fit.clicked.connect(self.add_selected_paths_tofit)
        self.shells = {}

        self.create_plot_item_for_fit_chi()
        self.create_plot_item_for_fit_ft()
        self.chi_data = None
        self.pushButton_make_ft.clicked.connect(self.plot_raw_chi_ft)

    #################################################################################################
    ## This section of code make search from the materials project database and populates the entires


    def search_materials_structure(self, formula='FeO'):
        print("Searching Materials...")

        self.thread_worker_matproj = QThread()
        self.worker_matproj = worker_matproj(formula=formula)
        self.worker_matproj.moveToThread(self.thread_worker_matproj)
        self.thread_worker_matproj.started.connect(self.worker_matproj.run)
        self.worker_matproj.finished.connect(self.thread_worker_matproj.quit)
        self.worker_matproj.finished.connect(self.populate_materials_structure)
        self.thread_worker_matproj.finished.connect(self.get_finished_status)
        self.worker_matproj.finished.connect(self.worker_matproj.deleteLater)
        self.thread_worker_matproj.start()


    def get_finished_status(self):
        print('Search complete')

    def populate_materials_structure(self):
        if self.worker_matproj.worker_document is not None:
            self.documents = self.worker_matproj.worker_document

        if len(self.documents) > 0:

            _labels = ['mp-ID', 'Formula', 'structure', 'E full(eV)', "Experimentally Observed"]
            self.clear_treeWidget(tree_widget=self.treeWidget_structure, labels=_labels)
            _parent = self.treeWidget_structure
            self._treeWidget = {}
            print("Loading Structure...\n")
            for key, doc in self.documents.items():
                _name_list = [doc.material_id.string,
                              doc.formula_pretty,
                              f"{doc.symmetry.crystal_system}",
                              f"{doc.energy_above_hull:2.3f}",
                              f"{not doc.theoretical}"]
                _status, _status_experimentally_observed = self.check_if_feff_files_will_be_good(doc)  # Must be removed when pymatgen update the code
                self._treeWidget[doc.material_id.string] = self._make_item(parent=_parent, item_list=_name_list)
                if _status:
                    self._treeWidget[doc.material_id.string].setBackground(0, QColor('yellow'))
                if _status_experimentally_observed:
                    self._treeWidget[doc.material_id.string].setBackground(4, QColor('lime'))
            self.structure_found = True
        else:
            print('No strucutre found')

    def check_if_feff_files_will_be_good(self, document):
        for el, amt in document.composition.items():
            if amt == 1:
                status = False
            else:
                status = True
        return status, not document.theoretical


    def clear_treeWidget(self, tree_widget=None, labels=None):
        tree_widget.clear()
        tree_widget.setHeaderLabels(labels)
        for i in range(len(labels)):
            tree_widget.setColumnWidth(i, 150)
        tree_widget.setSortingEnabled(True)


    def _make_item(self, parent=None, item_list=None):
        _item = QtWidgets.QTreeWidgetItem(parent, item_list)
        _item.setFlags(_item.flags() | Qt.ItemIsTristate | Qt.ItemIsUserCheckable)
        _item.setCheckState(0, Qt.Unchecked)
        return _item

    def search_the_structure_from_materials_project(self):
        _formula = self.lineEdit_formula.text()
        self.material_project_data[_formula] = self.search_materials_structure(_formula)

    ## This section of code make search from the materials project database and populates the entires
    #################################################################################################

    #################################################################################################
    ## This section of code perform feff calculation on selected entry and populates the feffpaths

    def make_feff_folder(self, absorbing_atom_valid_input, edge_valid_input, absorbing_atom, edge):
        task_finished = False
        if absorbing_atom_valid_input and edge_valid_input:
            self.treeWidget_paths_dict['paths'] = {}
            for key in self._treeWidget.keys():
                if self._treeWidget[key].checkState(0) == 2:
                    self.treeWidget_paths_dict['paths'][key] = os.path.join(STRUCTURE_FOLDER,
                                                                            self.documents[key].formula_pretty, key)
                    default_feff_parameters = get_default_feff_parameters(title=self.documents[key].material_id.string)
                    feff_dict = FEFFDictSet_modified(absorbing_atom=absorbing_atom,
                                            structure=self.documents[key].structure,
                                            spectrum="EXAFS",
                                            config_dict=default_feff_parameters,
                                            edge=edge,
                                            radius=7.5)
                    feff_dict.write_input(self.treeWidget_paths_dict['paths'][key])
                    task_finished = True
        if not task_finished:
            print("Select at least one Structure!")


    def run_feff(self, path_dict):
        print("Searching Material...\n")

        self.thread_feff_runner = QThread()
        self.worker_feff = worker_feff(feff_path=path_dict)
        self.worker_feff.moveToThread(self.thread_feff_runner)
        self.thread_feff_runner.started.connect(self.worker_feff.run)
        self.worker_feff.finished.connect(self.thread_feff_runner.quit)
        # self.worker_feff.finished.connect(self.populate_materials_structure)
        # self.thread_feff_runner.finished.connect(self.get_finished_status)
        self.worker_feff.finished.connect(self.worker_feff.deleteLater)

        self.thread_feff_runner.start()


    def perform_feff_calculation(self):
        absorbing_atom, absorbing_atom_valid_input = read_lineEdit_and_perform_sanity_check(
            lineEdit=self.lineEdit_absorbing_atom,
            reference_dictionary=ATOMIC_SYMBOL_DICT,
            message="Provide Valid Absorbing atom!")
        edge, edge_valid_input = read_lineEdit_and_perform_sanity_check(lineEdit=self.lineEdit_edge,
                                                                        reference_dictionary=EDGES,
                                                                        message="Provide Valid Edge!")

        self.make_feff_folder(absorbing_atom_valid_input=absorbing_atom_valid_input,
                              edge_valid_input=edge_valid_input,
                              absorbing_atom=absorbing_atom,
                              edge=edge)

        self.run_feff(self.treeWidget_paths_dict['paths'])


    def populate_scattering_paths(self):

        _labels = ['ID', 'Feff File', 'R', 'Coordination Number', 'Weight', 'Legs', 'Geometry']
        self.clear_treeWidget(tree_widget=self.treeWidget_scattering_path, labels=_labels)
        _parent = self.treeWidget_scattering_path

        self.treeWidget_paths_dict['widgets'] = {}
        self.treeWidget_paths_dict['feff_info'] = {}

        for key in self.treeWidget_paths_dict['paths'].keys():
            self.treeWidget_paths_dict['feff_info'][key] = get_feff_pathinfo(self.treeWidget_paths_dict['paths'][key])

            self.treeWidget_paths_dict['widgets'][key] = {}
            for path in self.treeWidget_paths_dict['feff_info'][key].paths:
                _name_list = [f"{key}",
                              f"{path.filename}",
                              f"{path.reff:1.3f}",
                              f"{path.degen:.0f}",
                              f"{path.cwratio:3.2f}",
                              f"{path.nleg}",
                              f"{path.geom}"]

                self.treeWidget_paths_dict['widgets'][key][path.filename] = self._make_item(parent=_parent,
                                                                                            item_list=_name_list)
        self.path_added = True


        ## This section of code perform feff calculation on selected entry and populates the feffpaths
        #################################################################################################

        ##################################################################################################
        ###################### plotting tools #####################################


    def create_plot_item_for_simulated_chi(self, number_of_references=1):

        self.canvas_sim_chi = MplCanvas(parent=self)
        _navi = NavigationToolbar2QT(self.canvas_sim_chi, parent=self)
        self.verticalLayout_sim_chi.addWidget(_navi)
        self.verticalLayout_sim_chi.addWidget(self.canvas_sim_chi)

    def create_plot_item_for_simulated_ft(self):

        self.canvas_sim_ft = MplCanvas(parent=self)
        _navi = NavigationToolbar2QT(self.canvas_sim_ft, parent=self)
        self.verticalLayout_sim_ft.addWidget(_navi)
        self.verticalLayout_sim_ft.addWidget(self.canvas_sim_ft)

    #################################################################################################################
    ### This section of code plot the selected paths

    def create_chi_and_ft(self):
        self.sim_chi_ft = {}
        for dic in self.feff_paths.keys():
            for key in self.feff_paths[dic].keys():
                self.sim_chi_ft[dic][key] = ff2chi(self.feff_paths[dic][key])

            self.sim_chi_ft[dic]['summation'] = ff2chi(self.feff_paths[dic])

        _feff = []
        for key in self.feff_paths.keys():
            _feff.append(self.feff_paths[key].values())
        self.sim_chi_ft['summation'] = ff2chi(_feff)

    def plot_scattering_path(self):

        self.canvas_sim_chi.axes.cla()
        self.canvas_sim_ft.axes.cla()

        self.treeWidget_paths_dict['selected_feff_data'] = {}
        __kweight = self.spinBox_kweight_sim.value()
        __window = self.comboBox_window_sim.currentText()
        __kmin = self.doubleSpinBox_kmin_sim.value()
        __kmax = self.doubleSpinBox_kmax_sim.value()

        __sum_chi = 0
        __sum_k = 0
        count = 0
        for key in self.treeWidget_paths_dict['widgets'].keys():
            self.treeWidget_paths_dict['selected_feff_data'][key] = {}
            for k, value in self.treeWidget_paths_dict['widgets'][key].items():
                if value.checkState(0) == 2:
                    __path = os.path.join(self.treeWidget_paths_dict['paths'][key], k)
                    _feffpath = feffpath(filename=__path)
                    _group = ff2chi([_feffpath])
                    __sum_k += _group.k
                    __sum_chi += _group.chi
                    count += 1
                    xftf(_group.k, _group.chi, kweight=__kweight, window=__window, kmin=__kmin, kmax=__kmax,
                         group=_group)
                    self.treeWidget_paths_dict['selected_feff_data'][key][k] = [_feffpath, _group]
                    self.canvas_sim_chi.axes.plot(_group.k, _group.chi * _group.k ** __kweight, label=f"{key} {k}")
                    self.canvas_sim_ft.axes.plot(_group.r, _group.chir_mag, label=f"{key} {k}")

        __sum = Group()
        __sum.k = __sum_k / count
        __sum.chi = __sum_chi
        xftf(__sum.k, __sum.chi, kweight=__kweight, window=__window, kmin=__kmin, kmax=__kmax, group=__sum)
        self.canvas_sim_chi.axes.plot(__sum.k, __sum.chi * __sum.k ** __kweight, label=f"sum", linewidth=2)
        self.canvas_sim_ft.axes.plot(__sum.r, __sum.chir_mag, label=f"sum", linewidth=2)

        self.canvas_sim_chi.axes.legend()
        self.canvas_sim_chi.draw()
        self.canvas_sim_ft.axes.legend()
        self.canvas_sim_ft.draw()


##################Add selected shells to the fit###################################

    def clear_shell_widgets(self):
        if self.horizontalLayout_param.count() > 1:
            index = self.horizontalLayout_param.count() - 2
            while (index >= 0):
                widget = self.horizontalLayout_param.itemAt(index).widget()
                widget.setParent(None)
                index -= 1

    def populate_shells_with_fit_params(self, parameters=None):

        _parameters = parameters

        _variables = ['r', 'n', 'ss', 'c3', 'c4', 'e', 's02']

        for i, key in enumerate(self.shells.keys()):
            for _var in _variables:
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + _var + '_value').setValue(
                    _parameters.valuesdict()[f'{_var}_{i:d}'])

        self.pushButton_fit.setEnabled(True)


    def read_feff_and_interpolate(self, shell_keys):
        new_k = np.arange(0, 20.01, 0.05)
        keys_data = ['mag_feff', 'pha_feff', 'real_phc', 'lam']

        _buffer = {}
        _buffer['k'] = new_k
        for shell_key in shell_keys:
            for key_data in keys_data:
                x = getattr(self.shells[shell_key]['parameter']._feffdat, 'k')
                y = getattr(self.shells[shell_key]['parameter']._feffdat, key_data)
                function = interp1d(x, y, kind='cubic')
                _buffer[key_data] = function(new_k)
            self.shells[shell_key]['feff_data'] = pd.DataFrame(_buffer)


    def add_selected_paths_tofit(self):

        self.clear_shell_widgets()
        self.shells = {}
        count = 0
        for key in self.treeWidget_paths_dict['selected_feff_data'].keys():
            for i, k in enumerate(self.treeWidget_paths_dict['selected_feff_data'][key].keys()):
                self.shells['Shell_' + str(count + 1)] = {}
                self.shells['Shell_' + str(count + 1)]['widget'] = Shell()
                self.horizontalLayout_param.insertWidget(i, self.shells['Shell_' + str(count + 1)]['widget'])
                self.shells['Shell_' + str(count + 1)]['widget'].groupBox.setTitle(f'Shell {count + 1} {key} {k} ')
                self.shells['Shell_' + str(count + 1)]['parameter'] = \
                self.treeWidget_paths_dict['selected_feff_data'][key][k][0]
                count += 1

        self.spinBox_shells.setValue(count)
        self.populate_shells_with_default_params(self.shells.keys())
        self.read_feff_and_interpolate(self.shells.keys())

    def populate_shells_with_default_params(self, keys):

        for i, key in enumerate(keys):
            if i == 0:
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'r_value').setValue(
                    self.shells[key]['parameter'].reff)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'r_max').setValue(
                    self.shells[key]['parameter'].reff * 1.05)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'r_min').setValue(
                    self.shells[key]['parameter'].reff * 0.95)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'n_value').setValue(
                    self.shells[key]['parameter'].degen)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'n_max').setValue(
                    self.shells[key]['parameter'].degen * 1.05)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'n_min').setValue(
                    self.shells[key]['parameter'].degen * 0.95)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'ss_value').setValue(0.05)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'ss_max').setValue(0.2)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'ss_min').setValue(0.01)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'c3_value').setValue(0)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'c3_max').setValue(0.02)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'c3_min').setValue(0)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'c4_value').setValue(0)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'c4_max').setValue(0.02)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'c4_min').setValue(0)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'e_value').setValue(0)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'e_max').setValue(20)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'e_min').setValue(-20)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 's02_value').setValue(0.8)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 's02_max').setValue(1.0)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 's02_min').setValue(0.7)
            else:
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'r_value').setValue(
                    self.shells[key]['parameter'].reff)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'r_max').setValue(
                    self.shells[key]['parameter'].reff * 1.05)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'r_min').setValue(
                    self.shells[key]['parameter'].reff * 0.95)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'n_value').setValue(
                    self.shells[key]['parameter'].degen)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'n_max').setValue(
                    self.shells[key]['parameter'].degen * 1.05)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'n_min').setValue(
                    self.shells[key]['parameter'].degen * 0.95)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'ss_value').setValue(0.05)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'ss_max').setValue(0.2)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'ss_min').setValue(0.01)
                getattr(self.shells[key]['widget'], 'lineEdit_' + 'ss').setText(f'ss_{i - 1:d}')
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'c3_value').setValue(0)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'c3_max').setValue(0.02)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'c3_min').setValue(0)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'c4_value').setValue(0)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'c4_max').setValue(0.02)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'c4_min').setValue(0)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'e_value').setValue(0)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'e_max').setValue(20)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 'e_min').setValue(-20)
                getattr(self.shells[key]['widget'], 'lineEdit_' + 'e').setText(f'e_0')
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 's02_value').setValue(0.8)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 's02_max').setValue(1.0)
                getattr(self.shells[key]['widget'], 'doubleSpinBox_' + 's02_min').setValue(0.7)
                getattr(self.shells[key]['widget'], 'lineEdit_' + 's02').setText(f's02_0')

    def clear_shell_widgets(self):
        if self.horizontalLayout_param.count() > 1:
            index = self.horizontalLayout_param.count() - 2
            while (index >= 0):
                widget = self.horizontalLayout_param.itemAt(index).widget()
                widget.setParent(None)
                index -= 1



    def create_plot_item_for_fit_chi(self):
        plt_item, _ref = create_pyqtgraph_widget(layout=self.verticalLayout_chi,
                                                 title="EXAFS Chi",
                                                 number_of_references=2)

        self.raw_chi_ref = _ref[1]
        self.fit_chi_ref = _ref[2]

    def create_plot_item_for_fit_ft(self):

        plt_item, _ref = create_pyqtgraph_widget(layout=self.verticalLayout_ft,
                                                 title="Fourier Transform",
                                                 number_of_references=4)

        self.raw_ft_mag_ref = _ref[1]
        self.raw_ft_img_ref = _ref[2]
        self.fit_ft_mag_ref = _ref[3]
        self.fit_ft_img_ref = _ref[4]


    def plot_raw_chi_ft(self):

        __kweight = self.spinBox_kweight.value()
        __window = self.comboBox_window.currentText()
        __kmin = self.doubleSpinBox_kmin.value()
        __kmax = self.doubleSpinBox_kmax.value()

        __chi = self.chi_data.chi * self.chi_data.k ** __kweight
        self.chi_data.for_fit = __chi
        __group = Group()
        xftf(self.chi_data.k, self.chi_data.chi, kweight=__kweight, kmin=__kmin, kmax=__kmax, window=__window,
             group=__group)

        pen = mkPen(color='b', width=2, style=Qt.PenStyle.SolidLine)

        self.raw_chi_ref.setData(self.chi_data.k, __chi, pen=pen, clear=True)
        self.raw_ft_mag_ref.setData(__group.r, __group.chir_mag, pen=pen, clear=True)
        self.raw_ft_img_ref.setData(__group.r, __group.chir_im, pen=pen, clear=True)

        self.fit_chi_ref.clear()
        self.fit_ft_mag_ref.clear()
        self.fit_ft_img_ref.clear()