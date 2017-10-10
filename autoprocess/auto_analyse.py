import re, os, sys
import subprocess
import warnings
warnings.simplefilter("ignore") # ignore deprecation warnings

from autoprocess.parser.distl import parse_distl_string
from autoprocess.utils.misc import json
    

def _save_json_output(filename, data):
    if not data: return
    f = open(filename,'w')
    f.write(data)
    f.close()
        
def _get_json_output(text):
    data = parse_distl_string(text)
    info = data.get('summary', None)
    return json.dumps(info)

 
def _get_error_output(err, code=1, traceback=None):
    info = {'error': {'code': code, 'message': err, 'traceback':traceback}}
    return json.dumps(info)
        

def run_distl(img, directory=None, output_file=None):
    if directory is None:
        directory = os.getcwd()
    else:
        if not os.path.isdir(directory):
            os.mkdir(directory)
        os.chdir(directory)

    output = subprocess.check_output(['labelit.distl ', img])
    results = _get_json_output(output)
    sys.stdout.write(results+'\n')

    out = subprocess.check_output(['labelit.reset'])

def run():
    if len(sys.argv) > 1:
        img = os.path.abspath(sys.argv[1])
    else:
        results = _get_error_output('Invalid Parameters.')
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
        