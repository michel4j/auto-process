import os
import subprocess
import sys

from autoprocess.parsers.distl import parse_distl_string
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
        results = parse_distl_string(output.decode('utf8'))
        info = results['summary']

    except subprocess.CalledProcessError as e:
        sys.stderr.write(str(e.output) + '\n')
        info = {'error': str(e.output), 'score': 0.0}

    sys.stdout.write(json.dumps(info, indent=2) + '\n')


def run(args):
    run_distl(args.image, rastering=args.rastering)
