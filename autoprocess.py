#!/usr/bin/env python

"""
autoprocess [options] /path/to/set1.img /path/to/set2.img ... /path/to/setn.img

options:
    --mad, -m : Process each set, scale together and generate separate reflection files.
    --screen, -s : Process a few frames from characterize crystal from each set.
    --anom, -a : Process with Friedel's law False
    --prefix=p1,p2,p3 : comma separated list of prefixes to use for output files. 
            Default 1,2,3,...,n
            prefix order should correspond to the order of the data sets
              for example for MAD data, use --prefix=peak,infl,remo
    --dir=/path : Directory to store processed results. Subdirectories will be created inside.
            Default current directory.
    --help, -h : display this message
    Default (no option): Process each set, scale together and merge into one reflection file.
    
 data sets:
    Each data set can be represented by any frame from that set.
"""

import sys
import os
import getopt

dpm_path = os.environ.get('DPM_PATH',None)
if dpm_path is None:
    print 'ERROR: DPM_PATH environment variable not set.'
    sys.exit(1)
else:
    sys.path.append(dpm_path)
    
from dpm.autoxds.process import AutoXDS
from dpm.utils.log import log_to_console

def usage():
    print __doc__
    
    
def main():
    try:
        opts, args = getopt.gnu_getopt(sys.argv[1:], "msah", ["help", "dir=", "mad","screen","anom","prefix="])
    except getopt.error, msg:
        print "ERROR: ", msg
        usage()
        sys.exit(1)            
            
    # Parse options
    options = {}
    options['directory'] = os.path.abspath('./')
    options['prefix'] = []
    for o, a in opts:
        if o in ("-h","--help"):
            usage()
            sys.exit(0)
        if o in ("-m", "--mad"):
            options['command'] = 'mad'
            options['anomalous'] = True
        if o in ("-a","--anom"):
            options['anomalous'] = True
        if o in ('-s','--screen'):
            options['command'] = 'screen'
        if o in ('--dir'):
            options['directory'] = a
        if o in ('--prefix'):
            options['prefix'] = a.split(',')
            
    if len(options['prefix']) < len(args):
        for i in xrange(len(options['prefix']), len(args)):
            options['prefix'].append("%d" % (i+1))
                
    if len(args) == 0:
        print "ERROR: no image sets provided."
        usage()
        sys.exit(1)
    
    # Check that images from arguments actually exist on disk
    for img in args:
        if not ( os.path.isfile(img) and os.access(img, os.R_OK) ):
            print "ERROR: File '%s' does not exist, or is not readable." % img
            sys.exit(1)
            
    # Check that working directory exists
    if not ( os.path.isdir( options['directory'] ) and os.access( options['directory'], os.W_OK) ):
        print    "ERROR: Directory '%s' does not exist, or is not writable." % options['directory']
        sys.exit(1)
        
    options['images'] = args
           
    app = AutoXDS( options )
    app.run()      
    app.save_xml('process.xml')
    app.save_log('process.log')
       
if __name__ == "__main__":
    try:
        log_to_console()
        main()
    except KeyboardInterrupt:
        sys.exit(1)
