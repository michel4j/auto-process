
import sys
import os
import getopt
import dpm.errors

PROCESS_USAGE = """
auto.process [options] /path/to/set1.img /path/to/set2.img ... /path/to/setn.img

options:
    --mad, -m : Process each set, scale together and generate separate reflection files.
    --screen, -s : Process a few frames from characterize crystal from each set.
    --anom, -a : Process with Friedel's law False
    --backup, -b : Backup previous output directory if it exists
    --prefix=p1,p2,p3 : comma separated list of prefixes to use for output files. 
            Default is first part of image name
            prefix order should correspond to the order of the data sets
              for example for MAD data, use --prefix=peak,infl,remo
    --dir=/path : Directory to store processed results. Default is to create a  new one in the current directory.
    --inputs, -i: generate XDS.INP only and quit
    --help, -h : display this message
    Default (no option): Process each set, scale together and merge into one reflection file.
    
 data sets:
    Each data set can be represented by any frame from that set.
"""


SCALE_USAGE = """
auto.scale [options]

options:
    --res=<res>, -r <res> : Manually set the high resolution limit for scaling.
    --anom, -a : Scale with Friedel's law False
    --backup, -b : Backup previous output if it exists
    --help, -h : display this message
    Default (no option): Resume previous processing from scaling step.
    
"""

def _uniquify(seq): 
    # order preserving
    seen = {}
    result = []
    for item in seq:
        if item in seen: continue
        seen[item] = 1
        result.append(item)
    return result

def process_options(params):
    try:
        opts, args = getopt.gnu_getopt(params, "msahbi", ["help", "dir=", "mad","screen","anom", "backup", "prefix=", "inputs"])
        assert len(args) >= 1
    except:
        print PROCESS_USAGE
            
    # Parse options
    options = {
        'anomalous' : False,
        'mode': 'simple',
        'backup': False,
        }
    # expand filenames and remove duplicates maintaning ordering
    options['images'] = []
    args = map(os.path.abspath, args)
    options['images'] = _uniquify(args)
    
    for o, a in opts:
        if o in ("-h","--help"):
            print PROCESS_USAGE
            sys.exit(0)
            
        if o in ("-a","--anom"):
            options['anomalous'] = True
        
        if o in ('-s','--screen'):
            options['mode'] = 'screen'
        elif o in ("-m", "--mad"):
            if len(options['images']) > 1:
                options['mode'] = 'mad'
            options['anomalous'] = True

        if o in ('--dir'):
            options['directory'] = os.path.abspath(a)
        if o in ('-b', '--backup'):
            options['backup'] = True
        if o in ('--prefix'):
            options['prefix'] = a.split(',')
            if len(options['prefix']) != len(options['images']):
                del options['prefix']       
    if options['mode'] == 'simple' and len(options['images']) > 1:
        options['mode'] = 'merge'

    return options

def scale_options(params):
    try:
        opts, args = getopt.gnu_getopt(params, "r:abih", ["res=", "anom", "backup", "inputs","help"])
    except:
        print SCALE_USAGE
            
    # Parse options
    options = {}    
    for o, a in opts:
        if o in ("-h","--help"):
            print SCALE_USAGE
            sys.exit(0)
            
        if o in ("-a","--anom"):
            options['anomalous'] = True
        if o in ('-b', '--backup'):
            options['backup'] = True
        if o in ('-r', '--res'):
            try:
                options['resolution'] = float(a)
            except:
                print SCALE_USAGE
                sys.exit(0)
    return options