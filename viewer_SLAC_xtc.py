#!/usr/bin/env python

import psana
import pyqtgraph as pg
import PyQt4.QtGui
import PyQt4.QtCore
import numpy as np


# get the data source
source = 'exp=cxif5315:run=165:dir=/nfs/cfel/cxi/scratch/data/2015/LCLS-2015-Liang-Feb-LF53/xtc/'

# get the data source
ds = psana.DataSource(source)

# loop through events

for evt in ds.events():
    evtID = evt.get(psana.EventId)
    print str(evtID)
