
import utils
from dpm.utils import xtal
import xml.dom.minidom

def parse_ctruncate(filename='ctruncate.log'):
    info = utils.parse_file(filename, config='ctruncate.ini')
    if info.get('twinning_l_statistic') is not None:
        info['twinning_l_fraction'] = xtal.L2twin(info['twinning_l_statistic'][0])
    else:
        info['twinning_l_fraction'] = 0.0
    return info


def parse_sfcheck(filename='sfcheck.log'):
    info = utils.parse_file(filename, config='sfcheck.ini')
    doc = xml.dom.minidom.parse('sfcheck.xml')

    data_test = doc.getElementsByTagName('data_test')[0]
    for node in data_test.childNodes:
        for subnode in node.childNodes:
            if subnode is not None:
                key = str(node.nodeName).strip()
                if key in ['sg','job','err_message']:
                    info[key] = subnode.nodeValue
                elif key == "cell":
                    info[key] = map(float, subnode.nodeValue.split())
                elif key == "err_level":
                    info[key] = int(subnode.nodeValue)
                else:
                    info[key] = float(subnode.nodeValue)
    return {'sf_check': info}
    