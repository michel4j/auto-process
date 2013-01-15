#!/usr/bin/env python

# enables  multi-tasking by splitting the COLSPOT step of
# xds into independent jobs. Each job is carried out by the
# Fortran program mcolspot or mcolspot_par started by
# this script as a background process with a different set
# of input parameters.

import sys
import os
from dpm.service import cluster
    
if __name__ == '__main__':
    
    if len(sys.argv) != 3:
        print 'usage: \n\tforkcolspot ntask maxcpu'
    else:
        ntask = int(sys.argv[1])
        maxcpu = int(sys.argv[2])
        server = cluster.ColspotServer(ntask, maxcpu, os.getcwd())
        server.run()
        if os.path.exists('mcolspot.tmp'):
            os.remove('mcolspot.tmp')
