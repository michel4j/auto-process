import re, os, sys
import commands

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
        

def run_distl(img, directory=None):
    if directory is None:
        directory = os.getcwd()
    sts, output = commands.getstatusoutput('labelit.distl %s' % img)
    if sts == 0: # success:
        results = _get_json_output(output)
        _save_json_output(os.path.join(directory, os.path.join(directory, 'distl.json')), results)
    else:
        results = _get_error_output(output)    
    return results

if __name__ == '__main__':
    if len(sys.argv) == 3:
        img = os.path.abspath(sys.argv[1])
        directory = os.path.abspath(sys.argv[2])
    elif len(sys.argv) == 2:
        img = os.path.abspath(sys.argv[1])
        directory = None
    else:
        err = 'Invalid arguments'
        print _get_error_output(err)
        sys.exit(0)       
    run_distl(img, directory)