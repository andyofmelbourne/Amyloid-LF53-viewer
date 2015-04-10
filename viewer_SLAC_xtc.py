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

def data_as_slab(evt, detector_data_source_string = 'DetInfo(CxiDs1.0:Cspad.0)'):
    """
    0: 388        388: 2 * 388  2*388: 3*388  3*388: 4*388
    (0, 0, :, :)  (1, 0, :, :)  (2, 0, :, :)  (3, 0, :, :)
    (0, 1, :, :)  (1, 1, :, :)  (2, 1, :, :)  (3, 1, :, :)
    (0, 2, :, :)  (1, 2, :, :)  (2, 2, :, :)  (3, 2, :, :)
    ...           ...           ...           ...
    (0, 7, :, :)  (1, 7, :, :)  (2, 7, :, :)  (3, 7, :, :)
    """
    slab_shape   = (1480, 1552)
    cspad        = evt.get(psana.CsPad.DataV2, psana.Source(detector_data_source_string))
    cspad_np     = np.array([cspad.quads(j).data() for j in range(cspad.quads_shape()[0])])
    native_shape = cspad_np.shape
    cspad_ij     = np.zeros(slab_shape, dtype=cspad_np.dtype)
    for i in range(cspad_np.shape[0]):
        cspad_ij[:, i * native_shape[3]: (i+1) * native_shape[3]] = cspad_np[i].reshape((native_shape[1] * native_shape[2], native_shape[3]))
    
    return cspad_ij

class Application:
    """
    The main frame of the application
    """

    def __init__(self, ds, geom_fnam, buffersize = 100)
        self.geom_fnam  = geom_fnam
        self.ds         = ds
        self.buffersize = buffersize

        self.index = None
        
        ij, self.geom_shape    = gf.get_ij_psana_shaped(geom_fnam)
        self.i_map, self.j_map = ij[0], ij[1]  

        self.data      = np.zeros((buffersize,) + self.geom_shape, dtype=np.int16)
        self.temp_data = np.zeros((buffersize,) + (32, 185, 388), dtype=np.int16)

        # online plugins
        self.load_data(ds)
        self.initUI()

    def load_data(self, ds, start_index = None):
        """
        load the next "self.buffersize" images in the dataset "ds"
        """
        if start_index is not None :
            if start_index != self.index:
                self.index = start_index
        
        # get the time stamps for this dataset
        run   = ds.runs()
        times = run.times()
        
        # get the buffer time stamps self.index : self.index + buffersize
        if self.index + self.buffersize < len(times):
            mytimes = times[self.index : self.index + self.buffersize]
        else : 
            print 'end of run. Loading: ', self.index, '--> ', len(times)
            mytimes = times[self.index : -1]
         
        # load the raw cspad data in this interval
        print '\nloading image buffer:' 
        for i in range(self.buffersize):
            evt  = run(mytimes[i])
            slab = data_as_slab(evt)
            self.temp_data[i] = slab
            
            # apply dark correction
            pass

            # apply geometry
            update_progress(float(i + 1) / float(self.buffersize))
                
            self.data[i, self.i_map, self.j_map] = self.temp_data[i].ravel()
        
        self.index += self.buffersize

    def initUI(self):
        # Always start by initializing Qt (only once per application)
        app = PyQt4.QtGui.QApplication([])
        
        # Define a top-level widget to hold everything
        w = PyQt4.QtGui.QWidget()
        
        pg.setConfigOption('background', 0.2)


        # Input validation
        self.intregex = PyQt4.QtCore.QRegExp('[0-9]+')
        self.floatregex = PyQt4.QtCore.QRegExp('[0-9\.]+')

        self.qtintvalidator = PyQt4.QtGui.QRegExpValidator()
        self.qtintvalidator.setRegExp(self.intregex)
        self.qtfloatvalidator = PyQt4.QtGui.QRegExpValidator()
        self.qtfloatvalidator.setRegExp(self.floatregex)
        
        # 2D plot for the cspad and mask
        self.imageW = pg.ImageView()
        
        print '\nsetting image data:'
        self.imageW.setImage(self.data)
        print 'Done'
        
        vlayout = PyQt4.QtGui.QVBoxLayout()
        vlayout.addWidget(self.imageW)

        hlayout = PyQt4.QtGui.QHBoxLayout()
        # drop down menu of run files
        self.files_dropdownW = PyQt4.QtGui.QComboBox()
        file_list = open('file_list_LF53.txt', 'r')
        fnam_list = []
        for line in file_list :
            fnam_list.append(line.rstrip())
        
        for k in fnam_list:
            self.files_dropdownW.addItem(k)
        
        def switch_data(text):
            if str(text) == self.h5_fnam :
                print 'no change to dataset'
                return
            self.h5_fnam   = str(text)
            self.old_index = None
            self.load_data(self.h5_fnam, 0)
            print '\nsetting image data:'
            self.imageW.setImage(self.data, autoRange = False, autoLevels = False, autoHistogramRange = False)
            print 'Done'
        
        self.files_dropdownW.activated[str].connect( switch_data )
        hlayout.addWidget(self.files_dropdownW)

        # add a next button
        def next_buffer():
            self.load_data(self.h5_fnam)
            print '\nsetting image data:'
            self.imageW.setImage(self.data, autoRange = False, autoLevels = False, autoHistogramRange = False)
            print 'Done'

        self.next_button = PyQt4.QtGui.QPushButton('load next ' + str(self.buffersize_chunks * self.chunksize) + ' images')
        self.next_button.clicked.connect(next_buffer)
        hlayout.addWidget(self.next_button)

        # go to index line edit
        def goto_index():
            new_index = int(self.index_lineedit.text())
            self.load_data(self.h5_fnam, new_index)
            print '\nsetting image data:'
            self.imageW.setImage(self.data, autoRange = False, autoLevels = False, autoHistogramRange = False)
            print 'Done'

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
    # get the data source
    source = 'exp=cxif5315:run=165:dir=/nfs/cfel/cxi/scratch/data/2015/LCLS-2015-Liang-Feb-LF53/xtc/'
    
    # get the data source
    ds = psana.DataSource(source)
    
    geom_fnam  = 'cspad-cxif5315-cxi-taw4.geom'
    
    Application(ds, geom_fnam, buffersize = 100)
