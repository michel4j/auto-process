import re, os, sys
import commands
import warnings
warnings.simplefilter("ignore") # ignore deprecation warnings

from dpm.parser.distl import parse_distl_string
import dpm.utils

try: 
    import json
except ImportError: 
    import simplejson as json
    

def _save_json_output(filename, data):
    if not data: return
    f = open(filename,'w')
    f.write(data)
    f.close()
        
def _get_json_output(text):
    data = parse_distl_string(text)
    info = {
        'result': data.get('summary', None),
        'error': None,
    }
    return json.dumps(info)

#FIXME specify more generic error codes to use accross BCM/DPM, similar to those used by device base
 
def _get_error_output(err, code=1, traceback=None):
    info = {
        'result': None,
        'error': {'code': code, 'message': err, 'traceback':traceback}
    }
    return json.dumps(info)
        

def run_distl(img, directory=None, output_file=None):
    if directory is None:
        directory = os.getcwd()
    else:
        if not os.path.isdir(directory):
            os.mkdir(directory)
    os.chdir(directory)
    sts, output = commands.getstatusoutput('labelit.distl %s' % img)
    if sts == 0: # success:
        results = _get_json_output(output)
        if output_file is not None:
            _save_json_output(output_file, results)
        sys.stdout.write(results+'\n')
    else:
        exm = re.compile('Exception: (.+)$')
        m = exm.search(output)
        if m:
            results = _get_error_output(m.group(0), traceback=output, code=2)       
        else:
            results = _get_error_output("labelit.distl exited prematurely.", traceback=output, code=2)       
        if output_file is not None:
            _save_json_output(output_file, results)
        sys.stderr.write(results+'\n')
    return

if __name__ == '__main__':
    if len(sys.argv) > 1:
        img = os.path.abspath(sys.argv[1])
    else:
        results =  _get_error_output('Invalid Parameters.')        
        sys.stderr.write(results+'\n')
        sys.exit(1)   
        
    if len(sys.argv) > 2:
        directory = os.path.abspath(sys.argv[2])
    else:
        directory = None
        
    if len(sys.argv) > 3:
        output_file = os.path.join(directory, sys.argv[3])
    else:
        output_file = None
        
    run_distl(img, directory, output_file)
        