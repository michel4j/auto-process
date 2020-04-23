import os
import re

from . import parser

PHENIX_VERSION = os.environ.get('PHENIX_VERSION', '')


def parse_xtriage(filename='xtriage.log'):
    info = parser.parse(filename, 'xtriage')
    return info
