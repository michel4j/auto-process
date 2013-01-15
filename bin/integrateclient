#!/usr/bin/env python

# runs one instance of a distributed INTEGRATE client 

import sys
import os
from dpm.service import cluster
    
if __name__ == '__main__':
    
    if len(sys.argv) != 5:
        print 'usage: \n\tintegrateclient server port authkey njobs'
    else:
        address = sys.argv[1]
        port = int(sys.argv[2])
        authkey = sys.argv[3]
        njobs = int(sys.argv[4])
        client = cluster.JobClient(address, port, authkey, njobs, command="mintegrate_par")
        client.run()
