"""
BEST xml output parsing functions

"""
import xml.dom.minidom
import os

def parse_best(filename):
    """read BEST XML output returns a dictionary"""
    summary = {}
    if not os.path.exists(filename):
        return summary
    doc = xml.dom.minidom.parse(filename)
    summary['runs'] = []
    summary['prediction_all'] = {}
    summary['prediction_hi'] = {}

    for node in doc.getElementsByTagName('table'):
        name = node.getAttribute('name')
        index = node.getAttribute('index')
        if name == 'data_collection_strategy' and index == '1':
            for subnode in node.getElementsByTagName('list'):
                name = subnode.getAttribute('name')
                index = subnode.getAttribute('index')
                if name == 'summary' and index == '1':
                    for item in subnode.getElementsByTagName('item'):
                        key = item.getAttribute('name')
                        value = item.firstChild.nodeValue
                        if key != 'resolution_reasoning':
                            value = float(value)
                        summary[key] = value
                if name == 'collection_run':
                    run = {}
                    run[u'number'] = int(index)
                    for item in subnode.getElementsByTagName('item'):
                        key = item.getAttribute('name')
                        value = item.firstChild.nodeValue
                        if key != 'overlaps':
                            value = float(value)
                        run[key] = value
                    summary['runs'].append(run)
        elif name == 'statistical_prediction' and index == '1':
            subnodes = node.getElementsByTagName('list')
            overall_bin = subnodes[-1]
            high_bin = subnodes[-2]
            for item in overall_bin.getElementsByTagName('item'):
                key = item.getAttribute('name')
                value = float(item.firstChild.nodeValue)
                summary['prediction_all'][key] = value

            for item in high_bin.getElementsByTagName('item'):
                key = item.getAttribute('name')
                value = float(item.firstChild.nodeValue)
                summary['prediction_hi'][key] = value

    #fix the attenuation
    summary['attenuation'] = 100*(1.0 - summary['attenuation'])
    return summary
