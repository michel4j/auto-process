import  sys
import subprocess
import warnings
warnings.simplefilter("ignore") # ignore deprecation warnings

from autoprocess.parser.distl import parse_distl_string
from autoprocess.utils.misc import json


def run_distl(img):
    try:
        output = subprocess.check_output(['labelit.distl ', img])
        subprocess.check_output(['labelit.reset'])
        results = parse_distl_string(output)
        info = results['summary']
    except subprocess.CalledProcessError as e:
        sys.stderr.write(str(e) + '\n')
        info = {'error': str(e)}

    sys.stdout.write(json.dumps(info, indent=2)+'\n')

def run():
    if len(sys.argv) <2:
        sys.stderr.write('Image file not procided' + '\n')
        sys.exit(1)
    else:
        run_distl(sys.argv[1])
        