import  sys
import os
import subprocess
import warnings
import numpy
warnings.simplefilter("ignore") # ignore deprecation warnings

from autoprocess.parser.distl import parse_distl_string
from autoprocess.utils.misc import json


def run_distl(img, rastering=False):
    try:
        args = [
            'distl.signal_strength',
            'distl.res.outer={}'.format(3.0 if rastering else 1.0),
            'distl.res.inner=10.0',
            img,
        ]
        output = subprocess.check_output(args, env=os.environ.copy())
        results = parse_distl_string(output)
        info = results['summary']

    except subprocess.CalledProcessError as e:
        sys.stderr.write(str(e.output) + '\n')
        info = {'error': str(e.output), 'score': 0.0}

    sys.stdout.write(json.dumps(info, indent=2)+'\n')

def run():
    if len(sys.argv) <2:
        sys.stderr.write('Image file not procided' + '\n')
        sys.exit(1)
    else:
        run_distl(sys.argv[1])
        