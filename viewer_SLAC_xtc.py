#!/usr/bin/env python
"""
For now I will hard code the datasource and paths
I just want a forward and back button (would be nice to use arrow keys)
print the timestamp to the command line
"""

import psana
import pyqtgraph as pg
import PyQt4.QtGui
import PyQt4.QtCore
import numpy as np
import sys
import h5py

import geometry_funcs as gf

"""
# get the data source
source = 'exp=cxif5315:run=165:dir=/nfs/cfel/cxi/scratch/data/2015/LCLS-2015-Liang-Feb-LF53/xtc/'

# get the data source
ds = psana.DataSource(source)

# loop through events
for evt in ds.events():
    evtID = evt.get(psana.EventId)
    print str(evtID)
"""

def data_as_slab(evt, detector_data_source_string = 'DetInfo(CxiDs2.0:Cspad.0)'):
    """
    0: 388        388: 2 * 388  2*388: 3*388  3*388: 4*388
    (0, 0, :, :)  (1, 0, :, :)  (2, 0, :, :)  (3, 0, :, :)
    (0, 1, :, :)  (1, 1, :, :)  (2, 1, :, :)  (3, 1, :, :)
    (0, 2, :, :)  (1, 2, :, :)  (2, 2, :, :)  (3, 2, :, :)
    ...           ...           ...           ...
    (0, 7, :, :)  (1, 7, :, :)  (2, 7, :, :)  (3, 7, :, :)
    """
    slab_shape   = (1480, 1552)
    cspad_np     = data_from_evt(evt, detector_data_source_string = detector_data_source_string)
    native_shape = cspad_np.shape
    cspad_ij     = np.zeros(slab_shape, dtype=cspad_np.dtype)
    for i in range(cspad_np.shape[0]):
        cspad_ij[:, i * native_shape[3]: (i+1) * native_shape[3]] = cspad_np[i].reshape((native_shape[1] * native_shape[2], native_shape[3]))
    
    return cspad_ij

def data_from_evt(evt, detector_data_source_string = 'DetInfo(CxiDs2.0:Cspad.0)'):
    cspad        = evt.get(psana.CsPad.DataV2, psana.Source(detector_data_source_string))
    cspad_np     = np.array([cspad.quads(j).data() for j in range(cspad.quads_shape()[0])])
    return cspad_np

class Application:
    """
    The main frame of the application
    """


    def __init__(self, expstr, runno, geom_fnam, buffersize = 100, darkcal = None):
        self.expstr = expstr
        self.runno  = runno
        
        # get the data source
        self.run = self.getrun(expstr, runno)
        
        self.geom_fnam  = geom_fnam
        
        self.buffersize = buffersize
        
        if darkcal is not None :
            self.darkcal    = gf.apply_geom(geom_fnam, darkcal)
        else :
            self.darkcal    = None
        
        self.index     = 0
        self.old_index = None
        self.old_runno = None
        
        ij, self.geom_shape    = gf.get_ij_psana_shaped(geom_fnam)
        self.i_map, self.j_map = ij[0], ij[1]  

        self.data      = np.zeros((buffersize,) + self.geom_shape, dtype=np.int16)
        self.temp_data = np.zeros((buffersize,) + (4, 8, 185, 388), dtype=np.int16)
        
        # online plugins
        self.load_data(self.run)
        self.initUI()

    def getrun(self, expstr = 'exp=cxif5315', runno = 165):
        source   = expstr + ':' + 'run=' + str(runno) + ':idx'
        self.ds  = psana.DataSource(source)
        run = self.ds.runs().next()
        # get the time stamps for this dataset
        self.times = run.times()
        return run

    def load_data(self, run, start_index = None):
        """
        load the next "self.buffersize" images in the dataset "ds"
        """
        if start_index is not None :
            if start_index != self.index:
                self.index = start_index

        if self.index == self.old_index and self.runno == self.old_runno :
            return 
        
        # get the buffer time stamps self.index : self.index + buffersize
        if self.index + self.buffersize < len(self.times):
            mytimes = self.times[self.index : self.index + self.buffersize]
        else : 
            print 'end of run. Loading: ', self.index, '--> ', len(self.times)
            mytimes = self.times[self.index : -1]
         
        # load the raw cspad data in this interval
        print '\nloading image buffer:' 
        for i in range(self.buffersize):
            evt  = run.event(mytimes[i])
            slab = data_from_evt(evt)
            self.temp_data[i] = slab
            
        for i in range(self.buffersize):
            # apply geometry
            update_progress(float(i + 1) / float(self.buffersize))
             
            self.data[i, self.i_map, self.j_map] = self.temp_data[i].ravel()
        
        # apply dark correction
        if self.darkcal is not None :
            self.data -= self.darkcal

        self.old_index = self.index
        self.old_runno = self.runno

    def initUI(self):
        # Always start by initializing Qt (only once per application)
        app = PyQt4.QtGui.QApplication([])
        
        # Define a top-level widget to hold everything
        w = PyQt4.QtGui.QWidget()
        
        pg.setConfigOption('background', 0.2)
        
        # Input validation
        ##################
        self.intregex = PyQt4.QtCore.QRegExp('[0-9]+')
        self.floatregex = PyQt4.QtCore.QRegExp('[0-9\.]+')
        
        self.qtintvalidator = PyQt4.QtGui.QRegExpValidator()
        self.qtintvalidator.setRegExp(self.intregex)
        self.qtfloatvalidator = PyQt4.QtGui.QRegExpValidator()
        self.qtfloatvalidator.setRegExp(self.floatregex)
        
        # 2D plot for the cspad and mask
        ################################
        self.imageW = pg.ImageView()
        
        print '\nsetting image data:'
        self.imageW.setImage(np.transpose(self.data, (0, 2, 1)))
        print 'Done'
        
        vlayout = PyQt4.QtGui.QVBoxLayout()
        vlayout.addWidget(self.imageW)
        
        hlayout = PyQt4.QtGui.QHBoxLayout()

        # add a next button
        ###################
        def next_buffer():
            self.index += self.buffersize
            self.load_data(self.run)
            print '\nsetting image data:'
            self.imageW.setImage(np.transpose(self.data, (0, 2, 1)), autoRange = False, autoLevels = False, autoHistogramRange = False)
            self.next_button.setText('load next ' + str(self.buffersize) + ' images ' + str(self.index) + '/' + str(len(self.times)))
            print 'Done'

        self.next_button = PyQt4.QtGui.QPushButton('load next ' + str(self.buffersize) + ' images ' + str(self.index) + '/' + str(len(self.times)))
        self.next_button.clicked.connect(next_buffer)
        hlayout.addWidget(self.next_button)
        
        # go to index line edit
        #######################
        def goto_index():
            self.index = int(self.index_lineedit.text())
            self.load_data(self.run)
            print '\nsetting image data:'
            self.imageW.setImage(np.transpose(self.data, (0, 2, 1)), autoRange = False, autoLevels = False, autoHistogramRange = False)
            self.next_button.setText('load next ' + str(self.buffersize) + ' images ' + str(self.index) + '/' + str(len(self.times)))
            print 'Done'

        # choose run
        ############
        self.runs_label = PyQt4.QtGui.QLabel()
        self.runs_label.setText('switch to run:')
        hlayout.addWidget(self.runs_label)

        self.runs_dropdownW = PyQt4.QtGui.QComboBox()
        run_list = np.arange(1, 209, 1).astype(np.str)
        for k in run_list:
            self.runs_dropdownW.addItem(k)
        
        def switch_data(text):
            self.runno = int(text)
            print 'switching to run:', str(text)
            self.run = self.getrun(self.expstr, str(text))
            self.load_data(self.run, start_index = 0)
            print '\nsetting image data:'
            self.imageW.setImage(np.transpose(self.data, (0, 2, 1)), autoRange = False, autoLevels = False, autoHistogramRange = False)
            self.next_button.setText('load next ' + str(self.buffersize) + ' images ' + str(self.index) + '/' + str(len(self.times)))
            print 'Done'
            # reset the label
            self.next_button.setText('load next ' + str(self.buffersize) + ' images ' + str(0) + '/' + str(len(self.times)))
        
        self.runs_dropdownW.activated[str].connect( switch_data )
        self.runs_dropdownW.setCurrentIndex(self.runno - 1)
        hlayout.addWidget(self.runs_dropdownW)


        self.index_label = PyQt4.QtGui.QLabel()
        self.index_label.setText('goto index:')
        self.index_lineedit = PyQt4.QtGui.QLineEdit()
        self.index_lineedit.setText('0')
        self.index_lineedit.editingFinished.connect(goto_index)
        self.index_lineedit.setValidator(self.qtintvalidator)
        hlayout.addWidget(self.index_label)
        hlayout.addWidget(self.index_lineedit)

        vlayout.addLayout(hlayout)
        
        w.setLayout(vlayout)
        w.resize(1200,1200)
        w.show()
        
        ## Start the Qt event loop
        app.exec_()

def update_progress(progress):
    barLength = 20 # Modify this to change the length of the progress bar
    status = ""
    if isinstance(progress, int):
        progress = float(progress)
    if not isinstance(progress, float):
        progress = 0
        status = "error: progress var must be float\r\n"
    if progress < 0:
        progress = 0
        status = "Halt...\r\n"
    if progress >= 1:
        progress = 1
        status = "Done...\r\n"
    block = int(round(barLength*progress))
    text = "\rPercent: [{0}] {1:.1f}% {2}".format( "#"*block + "-"*(barLength-block), progress*100, status)
    sys.stdout.write(text)
    sys.stdout.flush()



if __name__ == '__main__':
    # load darkcal
    darkcal = '/nfs/cfel/cxi/scratch/data/2015/LCLS-2015-Liang-Feb-LF53/processed/calib/darkcal/cxif5315-r0019-CxiDs1-darkcal.h5'
    f       = h5py.File(darkcal, 'r')
    darkcal = f['data/data'].value
    f.close()
     
    geom_fnam  = '/nfs/cfel/cxi/home/amorgan/analysis/Amyloid-LF53-viewer/cspad-cxif5315-cxi-taw4.geom'
    
    exp = 'exp=cxif5315'
    run = 165
    Application(exp, run, geom_fnam, buffersize = 20, darkcal = darkcal)
