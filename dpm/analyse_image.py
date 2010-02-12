import re, os, sys, signal
import commands

sys.path.append(os.environ['DPM_PATH'])
from dpm.parser.distl import parse_distl
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
        
def _get_json_output():
    data = parse_distl('distl.log')
    info = {
        'success': True,
        'message': 'Image Analysis Completed Successfully',
        'output': data,
        'warnings': None,
        'errors': None,
    }
    return json.dumps(info)

def _get_error_output(err):
    info = {
        'success': False,
        'message': 'Image Analysis Failed',
        'output': None,
        'warnings': None,
        'errors': err,
    }
    return json.dumps(info)
        

def run_distl(img, directory):
    os.chdir(os.path.abspath(directory))
    sts, err = commands.getstatusoutput('labelit.distl %s > distl.log' % img)
    if sts == 0: # success:
        results = _get_json_output()
        _save_json_output(os.path.join(directory, 'distl.json'), results)
    else:
        results = _get_error_output(err)    
    print results

if __name__ == '__main__':
    if len(sys.argv) == 3:
        img = os.path.abspath(sys.argv[1])
        directory = os.path.abspath(sys.argv[2])
    elif len(sys.argv) == 2:
        img = os.path.abspath(sys.argv[1])
        directory = '/tmp'
    else:
        err = 'Invalid arguments'
        print _get_error_output(err)
        sys.exit(0)       
    run_distl(img, directory)