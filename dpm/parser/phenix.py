
import utils

def parse_xtriage(filename='xtriage.log'):
    info = utils.parse_file(filename, config='xtriage.ini')
    info['completeness'] = info['completeness']*100.0
    return info
    