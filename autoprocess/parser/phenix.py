import os
import re

from . import utils

_vers_m = re.search('.+/phenix-([\d.-]+)', os.environ.get('PHENIX', None))
if _vers_m:
    PHENIX_VERSION = "-%s" % _vers_m.group(1)
else:
    PHENIX_VERSION = ""


def parse_xtriage(filename='xtriage.log'):
    config = 'xtriage.ini%s' % PHENIX_VERSION
    info = utils.parse_file(filename, config, fallback='xtriage.ini')
    # info['completeness'] = info['completeness']*100.0
    return info
