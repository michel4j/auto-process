
import sys
import os
import autoprocess.errors
import getopt
from autoprocess.utils import xtal


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
    --nonchiral, -x: Allow processing non-chiral spacegroups such as some small
            molecules. Default assumes only chiral molecules such as proteins.
    --solve-small=<formula> : Attempt to solve the small molecule structure 
            using the provided formula. Formula examples are C6H12O6, Mg1O6H12. 
            No spaces and note the lower case second letter for 2-letter symbols.
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

def process_options(params, usage=PROCESS_USAGE):
    try:
        opts, args = getopt.gnu_getopt(params, 
                        "msahbt:xz", 
                        ["help", "dir=", "mad","screen","anom", "nonchiral",
                         "backup", "zap","task=", "prefix=", "solve-small="])
    except:
        print usage
            
    # Parse options
    options = {
        'anomalous' : False,
        'mode': 'simple',
        'backup': False,
        'chiral': True,
        }
    # expand filenames and remove duplicates maintaning ordering
    options['images'] = []
    args = map(os.path.abspath, args)
    options['images'] = _uniquify(args)
    
    for o, a in opts:
        if o in ("-h","--help"):
            print usage
            sys.exit(0)
            
        if o in ("-a","--anom"):
            options['anomalous'] = True
            
        if o in ("-x","--nonchiral"):
            options['chiral'] = False
        
        if o in ("--solve-small",):
            options['solve-small'] = a
            
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
    --exclude=<start>-<end>,<start>-<end>,..., -x <start>-<end>,<start>-<end>,... 
        : exclude data ranges
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
        opts, _ = getopt.gnu_getopt(params, "r:abf:ohx:", ["res=", "anom", "backup", "frames=", "opt", "inputs","help", "exclude="])
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
        if o in ('-x', '--exclude'):
            try:
                options['exclude'] = [map(int, x.split('-')) for x in a.split(',')]
            except:
                print INTEGRATE_USAGE
                sys.exit(0)
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
    --xalign="<v1>,<v2>", -x "<v1>,<v2>": Calculate Phi and Kappa angles for re-orienting crystal in
        coordinate system. If this option is omitted, the calculations will be
        done for all combinations of principal reciprocal axes. 
        Two crystal vectors are required and could be provided in any one of the
        following forms and their combinations:
            principal cell axes: "a", "b", "c", "a*", "b*", or "c*"
            reciprocal vectors in parenthesis: "(h k l)"
            real-space vectors in square brackets: "[x y z]"
        Examples:
            --xalign="a*,b*", --xalign="[1 0 0],[0 1 1]"
    --method=<0|1>, -m <0|1> : The method to be used for re-orienting the crystal.
        0: This is the default. v1 is aligned parallel to the omega axis, and v2 
           is placed in the plane containing the omega axis and the beam.
        1: v1 is perpendicular to both the beam and the omega axis, and v2 is
           placed in the plane containing the v1 and the omega axis.
    --help, -h : display this message
    Default (no option): Resume previous processing from strategy step.
    
Examples:
    auto.strategy --res=1.5
    auto.strategy --anom
    auto.strategy -a -r 2.3
    
"""
def strategy_options(params):    
    try:
        opts, args = getopt.gnu_getopt(params, "r:x:m:abih", ["res=", "xalign=", "method=", "anom", "backup", "inputs","help"])
    except:
        print STRATEGY_USAGE
            
    # Parse options
    options = {}
    xalign_options = {'vectors': ("",""), 'method': 0}
    for o, a in opts:
        if o in ("-h","--help"):
            print STRATEGY_USAGE
            sys.exit(0)
            
        if o in ("-a","--anom"):
            options['anomalous'] = True
        if o in ('-b', '--backup'):
            options['backup'] = True
        if o in ('-x', '--xalign'):
            xalign_options['vectors'] = tuple([v.strip() for v in a.split(',')])
        if o in ('-m', '--method'):
            try:
                xalign_options['method'] = int(a)
                assert xalign_options['method'] in (0, 1)
            except:
                raise autoprocess.errors.InvalidOption('Invalid method specified. Values must be "0" or "1": `%s%s`' % (o, a))
                sys.exit(0)                
            
        if o in ('-r', '--res'):
            try:
                options['resolution'] = float(a)
            except:
                print STRATEGY_USAGE
                sys.exit(0)
    options['xalign'] = xalign_options
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
    --nonchiral, -x: Allow processing non-chiral spacegroups such as some small
            molecules. Default assumes only chiral molecules such as proteins.
    --help, -h : display this message
    Default (no option): Resume previous processing from scaling step.

Examples:
    auto.symmetry -g 19
    auto.symmetry --spacegroup=19

"""
def symmetry_options(params):
    try:
        opts, _ = getopt.gnu_getopt(params, "r:g:bihx", ["res=", "spacegroup=", "backup", "inputs","help","nonchiral"])
    except:
        print SYMMETRY_USAGE
        raise autoprocess.errors.InvalidOption(' '.join(params))
            
    # Parse options
    options = {} 
    for o, a in opts:
        if o in ("-x","--nonchiral"):
            options['chiral'] = False
       
    for o, a in opts:
        if o in ("-h","--help"):
            print SYMMETRY_USAGE
            print xtal.get_sg_table(options.get('chiral', True))
            sys.exit(0)
                       
        if o in ("-g","--spacegroup"):
            try:
                sg_num = int(a)
                assert sg_num in xtal.SG_SYMBOLS.keys()
                if sg_num not in xtal.CHIRAL_SPACE_GROUPS:
                    options['chiral'] = False
                options['sg_overwrite'] = sg_num
            except ValueError:
                if o == '--spacegroup':
                    op = '%s=' % o
                else:
                    op = '%s ' % o
                print SYMMETRY_USAGE
                print xtal.get_sg_table(options.get('chiral', True))
                raise autoprocess.errors.InvalidOption('Invalid SpaceGroup Option: `%s%s`' % (op, a))

            except AssertionError:
                print SYMMETRY_USAGE
                print xtal.get_sg_table(options.get('chiral', True))
                raise autoprocess.errors.InvalidOption('Invalid SpaceGroup Number: %s' % (a))

                
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