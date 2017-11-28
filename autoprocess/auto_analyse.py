import  sys
import os
import subprocess
import warnings
import numpy
warnings.simplefilter("ignore") # ignore deprecation warnings

from autoprocess.parser.distl import parse_distl_string
from autoprocess.utils.misc import json


def run_distl(img):
    os.chdir(os.path.dirname(img))
    try:
        output = subprocess.check_output(['labelit.distl ', img], env=os.environ.copy())
        subprocess.check_output(['labelit.reset'], env=os.environ.copy())
        results = parse_distl_string(output)
        info = results['summary']

        bragg = info['bragg_spots']
        ice = 1 / (1.0 + info['ice_rings'])
        saturation = info['saturation'][1]
        sc_x = numpy.array([bragg, saturation, ice])
        sc_w = numpy.array([5, 10, 0.2])
        score = numpy.exp((sc_w * numpy.log(sc_x)).sum() / sc_w.sum())

        info['score'] = score
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
        