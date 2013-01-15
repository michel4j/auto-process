#!/usr/bin/env python

# enables  multi-tasking by splitting the INTEGRATE step of
# xds into independent jobs. Each job is carried out by the
# Fortran program mintegrate or mintegrate_par started by
# this script as a background process with a different set
# of input parameters.

import sys
import os
from dpm.service import cluster
    
if __name__ == '__main__':
    if len(sys.argv) != 6:
        print 'usage: \n\tforkintegrate fframe ni ntask niba0 maxcpu'
    else:        
        first = int(sys.argv[1])
        total = int(sys.argv[2])
        jobs =  int(sys.argv[3])
        minbatch = int(sys.argv[4])
        maxcpu = int(sys.argv[5])
        server = cluster.IntegrateServer(first, total, jobs, minbatch, maxcpu, os.getcwd())
        server.run()   
        if os.path.exists('mintegrate.tmp'):
            os.remove('mintegrate.tmp')
