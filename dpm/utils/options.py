
import sys
import os
import dpm.errors
import getopt
from dpm.utils import xtal


def _uniquify(seq): 
    # order preserving
    seen = {}
    result = []
    for item in seq:
        if item in seen: continue
        seen[item] = 1
        result.append(item)
    return result


PROCESS_USAGE = """
auto.process [options] /path/to/set1.img /path/to/set2.img ... /path/to/setn.img

Description:
    Automatically process one or several native, SAD, MAD or multiple-pass 
    datasets to converted reflection files.

Options:
    --mad, -m : Process each set, scale together and generate separate outputs.
    --screen, -s : Process a few frames from characterize crystal from each set.
    --anom, -a : Process with Friedel's law False
    --backup, -b : Backup previous output directory if it exists
    --prefix=p1,p2,p3 : comma separated list of prefixes to use for output files. 
            Default is first part of image name
            prefix order should correspond to the order of the data sets
              for example for MAD data, use --prefix=peak,infl,remo
    --dir=/path : Directory to store processed results. Default is to create a  
            new one in the current directory.
    --zap, -z : Abandon saved state and start all over.
    --help, -h : display this message
    Default (no option): Process each set, scale together and merge into one 
        reflection file.
    
Data sets:
    Each data set can be represented by any frame from that set.
    If no datasets are provided, attempt to resume from a previous checkpoint file

Examples:
    auto.process --mad /path/to/dataset_{peak,infl,remo}_001.img
    auto.process /path/to/dataset_{hires,lores}_001.img
    auto.process --screen /foo/bar/test_001.img --dir=/foo/screen_output
"""

def process_options(params):
    try:
        opts, args = getopt.gnu_getopt(params, 
                                       "msahbt:z", 
                                       ["help", "dir=", "mad","screen","anom",
                                        "backup", "zap","task=", "prefix="])
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
        if o in ('-z', '--zap'):
            options['zap'] = True
        if o in ('-t', '--task'):
            st = a.split(',')
            if len(st) == 1:
                options['resume_from'] = (0, st[0].strip())
            elif len(st) == 2:
                options['resume_from'] = (int(st[0]), st[1].strip())
                
        if o in ('--prefix'):
            options['prefix'] = a.split(',')
            if len(options['prefix']) != len(options['images']):
                del options['prefix']       
    if options['mode'] == 'simple' and len(options['images']) > 1:
        options['mode'] = 'merge'

    return options

SCALE_USAGE = """
auto.scale [options]

Description:
    Resume or repeat a previous processing from the scaling step onward, with
    the same or different settings for resolution range or Friedel's law.
     
Options:
    --res=<res>, -r <res> : Manually set the high resolution limit for scaling.
    --anom, -a : Scale with Friedel's law False
    --backup, -b : Backup previous output if it exists
    --help, -h : display this message
    Default (no option): Resume previous processing from scaling step.

Examples:
    auto.scale -r 2.0
    auto.scale --anom
    
"""
def scale_options(params):
    try:
        opts, _ = getopt.gnu_getopt(params, "r:abih", ["res=", "anom", "backup", "inputs","help"])
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

INTEGRATE_USAGE = """
auto.integrate [options]

Description:
    Resume, repeat or optimize a previous processing from the integration step 
    onward, with the same or different settings for resolution, data range or 
    Friedel's law.

Options:
    --res=<res>, -r <res> : Manually set the high resolution limit for integration.
    --anom, -a : Set Friedel's law False
    --backup, -b : Backup previous output if it exists
    --frames=<start>-<end>, -f <start>-<end> : manually set the data range
    --opt -o : Optimize integration using refined parameters from previous run
    --help, -h : display this message
    Default (no option): Resume previous processing from scaling step.

Examples:
    auto.integrate -r 2.2 -f 5-180 -o
        Optimize the integration, restring to resolution 2.2, and only process
        frames 5 to 180
    auto.integrate --frames=20-120 --anom
        Repeat the integration considering only frames 20 to 120 with Friedel's 
        law False for all remainig steps
"""
def integrate_options(params):
    try:
        opts, _ = getopt.gnu_getopt(params, "r:abf:oh", ["res=", "anom", "backup", "frames=", "opt", "inputs","help"])
    except:
        print INTEGRATE_USAGE
        sys.exit(0)
          
    # Parse options
    options = {}    
    for o, a in opts:
        if o in ("-h","--help"):
            print INTEGRATE_USAGE
            sys.exit(0)
            
        if o in ("-a","--anom"):
            options['anomalous'] = True
        if o in ('-b', '--backup'):
            options['backup'] = True
        if o in ('-f', '--frames'):
            try:
                options['frames'] = map(int, a.split('-'))
            except:
                print INTEGRATE_USAGE
                sys.exit(0)        
            
        if o in ('-o', '--opt'):
            options['optimize'] = True   
        if o in ('-r', '--res'):
            try:
                options['resolution'] = float(a)
            except:
                print INTEGRATE_USAGE
                sys.exit(0)
    return options

STRATEGY_USAGE = """
auto.strategy [options]

Description:
    Resume or repeat previous processing from the strategy determination step 
    onward with the same or different settings for resolution and Friedel's law.

Options:
    --res=<res>, -r <res> : Manually set the high resolution limit for strategy.
    --anom, -a : Calculate strategy with Friedel's law False
    --backup, -b : Backup previous output if it exists
    --help, -h : display this message
    Default (no option): Resume previous processing from strategy step.
    
Examples:
    auto.strategy --res=1.5
    auto.strategy --anom
    auto.strategy -a -r 2.3
    
"""
def strategy_options(params):
    try:
        opts, _ = getopt.gnu_getopt(params, "r:abih", ["res=", "anom", "backup", "inputs","help"])
    except:
        print STRATEGY_USAGE
            
    # Parse options
    options = {}    
    for o, a in opts:
        if o in ("-h","--help"):
            print STRATEGY_USAGE
            sys.exit(0)
            
        if o in ("-a","--anom"):
            options['anomalous'] = True
        if o in ('-b', '--backup'):
            options['backup'] = True
        if o in ('-r', '--res'):
            try:
                options['resolution'] = float(a)
            except:
                print STRATEGY_USAGE
                sys.exit(0)
    return options

SYMMETRY_USAGE = """
auto.symmetry [options]

Description:
    Resume or repeat a previous processing from the spacegroup determination 
    step onward, with the same or different settings for resolution range or 
    spacegroup.
     
Options:
    --res=<res>, -r <res> : Manually set the high resolution limit.
    --spacegroup=<num>, -g <num>:  Manually set space group by number (see 
            below for valid spacegroup numbers)
    --backup, -b : Backup previous output if it exists
    --help, -h : display this message
    Default (no option): Resume previous processing from scaling step.

Examples:
    auto.symmetry -g 19
    auto.symmetry --spacegroup=19

Table of spacegroup numbers:
-------------------------------------------------------------------------------
BRAVAIS-
  TYPE                     [SPACE GROUP NUMBER,SYMBOL]
  aP      [1,P1]
  mP      [3,P2] [4,P2(1)]
 mC,mI    [5,C2]
  oP      [16,P222] [17,P222(1)] [18,P2(1)2(1)2] [19,P2(1)2(1)2(1)]
  oC      [21,C222] [20,C222(1)]
  oF      [22,F222]
  oI      [23,I222] [24,I2(1)2(1)2(1)]
  tP      [75,P4] [76,P4(1)] [77,P4(2)] [78,P4(3)] [89,P422] [90,P42(1)2]
          [91,P4(1)22] [92,P4(1)2(1)2] [93,P4(2)22] [94,P4(2)2(1)2]
          [95,P4(3)22] [96,P4(3)2(1)2]
  tI      [79,I4] [80,I4(1)] [97,I422] [98,I4(1)22]
  hP      [143,P3] [144,P3(1)] [145,P3(2)] [149,P312] [150,P321] [151,P3(1)12]
          [152,P3(1)21] [153,P3(2)12] [154,P3(2)21] [168,P6] [169,P6(1)]
          [170,P6(5)] [171,P6(2)] [172,P6(4)] [173,P6(3)] [177,P622]
          [178,P6(1)22] [179,P6(5)22] [180,P6(2)22] [181,P6(4)22] [182,P6(3)22]
  hR      [146,R3] [155,R32]
  cP      [195,P23] [198,P2(1)3] [207,P432] [208,P4(2)32] [212,P4(3)32]
          [213,P4(1)32]
  cF      [196,F23] [209,F432] [210,F4(1)32]
  cI      [197,I23] [199,I2(1)3] [211,I432] [214,I4(1)32]
-------------------------------------------------------------------------------   
"""
def symmetry_options(params):
    try:
        opts, _ = getopt.gnu_getopt(params, "r:g:bih", ["res=", "spacegroup=", "backup", "inputs","help"])
    except:
        print SYMMETRY_USAGE
        raise dpm.errors.InvalidOption(' '.join(params))
            
    # Parse options
    options = {}    
    for o, a in opts:
        if o in ("-h","--help"):
            print SYMMETRY_USAGE
            sys.exit(0)
            
        if o in ("-g","--spacegroup"):
            try:
                sg_num = int(a)
                assert sg_num in xtal.SPACE_GROUP_NAMES.keys()
                options['sg_overwrite'] = sg_num
            except ValueError:
                if o == '--spacegroup':
                    op = '%s=' % o
                else:
                    op = '%s ' % o
                print SYMMETRY_USAGE
                raise dpm.errors.InvalidOption('Invalid SpaceGroup Option: `%s%s`' % (op, a))

            except AssertionError:
                print SYMMETRY_USAGE
                raise dpm.errors.InvalidOption('Invalid SpaceGroup Number: %s' % (a))

                
        if o in ('-b', '--backup'):
            options['backup'] = True
        if o in ('-r', '--res'):
            try:
                options['resolution'] = float(a)
            except:
                print SYMMETRY_USAGE
                sys.exit(0)
    return options

INPUTS_USAGE = """
auto.inputs /path/to/set.img

Description:
    Generate XDS.INP file for running XDS manually

Example:
    auto.inputs  /foo/bar/test_001.img
"""