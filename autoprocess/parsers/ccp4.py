import xml.dom.minidom

from autoprocess.utils import xtal
from . import utils


def parse_ctruncate(filename='ctruncate.log'):
    info = utils.parse_file(filename, config='ctruncate.ini')
    if info.get('twinning_l_statistic') is not None:
        info['twinning_l_fraction'] = xtal.L2twin(info['twinning_l_statistic'][0])
    else:
        info['twinning_l_fraction'] = 0.0
    return info
