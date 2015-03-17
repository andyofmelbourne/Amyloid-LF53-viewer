#!/usr/bin/env python

import sys
import time
import numpy as np
import math
import zmq
import pickle
import signal
import pyqtgraph as pg
import PyQt4.QtGui
import PyQt4.QtCore
import copy
import os
import h5py
import ConfigParser
from datetime import datetime

import geometry_funcs as gf


class Application:
    """
    The main frame of the application
    """

    def __init__(self, h5_fnam, h5_path = '/data', geom_fnam = None, buffersize_chunks = 8, chunksize = 22):
        self.h5_fnam = h5_fnam
        self.h5_path = h5_path
        self.index   = 100
        self.buffersize_chunks = buffersize_chunks
        self.chunksize = chunksize
        self.geom_fnam  = geom_fnam
        
        ij, self.geom_shape    = gf.get_ij_psana_shaped(geom_fnam)
        self.i_map, self.j_map = ij[0], ij[1]  

        self.data      = np.zeros((buffersize_chunks * chunksize + 1,) + self.geom_shape, dtype=np.int16)
        self.temp_data = np.zeros((chunksize,) + (32, 185, 388), dtype=np.int16)

        # online plugins
        self.load_data(self.h5_fnam)
        self.initUI()

    def load_data(self, fnam):
        start_index = self.chunksize * self.buffersize_chunks * self.index 
        h5_file = h5py.File(fnam, 'r')
        h5_data = h5_file[self.h5_path]
        print '\nloading image buffer:', fnam
        for i in range(self.buffersize_chunks):
            
            self.temp_data = h5_data[ start_index + i * self.chunksize : start_index + (i+1) * self.chunksize]
            
            for j in range(self.chunksize):
                progress = float(i * self.chunksize + j + 1) / float(self.buffersize_chunks * self.chunksize)
                #update_progress(progress)
                
                self.data[i * self.chunksize + j, self.i_map, self.j_map] = self.temp_data[j].ravel()
        h5_file.close()
        
        print 'calculating the average (last image):'
        av = np.zeros_like(self.data[0], dtype=np.float32)
        for i in range(self.data.shape[0]-1):
            av += self.data[i]
        av = av / float(self.data.shape[0] - 1)
        self.data[-1] = av.astype(self.data.dtype)
        self.index += 1

    def initUI(self):
        # Always start by initializing Qt (only once per application)
        app = PyQt4.QtGui.QApplication([])
        
        # Define a top-level widget to hold everything
        w = PyQt4.QtGui.QWidget()
        
        pg.setConfigOption('background', 0.2)
        
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
            self.load_data(str(text))
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
    h5_fnam    = 'LF53_data_nfs/cxif5315-r0162.h5'
    h5_path    = '/Configure:0000/Run:0000/CalibCycle:0000/CsPad::ElementV2/CxiDs2.0:Cspad.0/data'
    geom_fnam  = 'cspad-cxif5315-cxi-taw4.geom'
    buffersize_chunks = 16  # 22 is the chunk size for this dataset
    Application(h5_fnam, h5_path, geom_fnam, buffersize_chunks = buffersize_chunks)
