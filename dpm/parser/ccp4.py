
import utils
import xml.dom.minidom

def parse_ctruncate(filename='ctruncate.log'):
    return utils.parse_file(filename, config='ctruncate.ini')


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
    