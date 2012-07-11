"""
BEST xml output parsing functions

"""
import xml.dom.minidom
import os
import utils
import re
import numpy

def parse_best_plot(filename):
    data = file(filename).read()
    info = {}
    max_osc = {}
    max_osc_data, pos = utils.cut_section("Maximal oscillation width", "DATA=CURVE2D", data)
    for m in re.finditer("(?P<shell>[\d-]+\.[\d-]+)\s+'\n(?P<curve>(\s*\d+\s+[\d-]+\.[\d-]+\n)+)", max_osc_data):
        max_osc[m.group('shell')] = numpy.fromstring(m.group('curve'), sep=' ').reshape((-1,2))
    
    info['delta_statistics'] = {}
    first = True
    for shell, curve in max_osc.items():
        if first:
            first = False
            info['delta_statistics']['angle'] = list(curve[:,0])
        info['delta_statistics'][shell] = list(curve[:,1])
        
    
    compl_osc_data, pos = utils.cut_section('Minimal oscillation ranges for different completenesses', 'DATA=CURVE2D', data)
    compl_osc = {}
    for m in re.finditer("linelabel\s+=\s+'compl\s+-(?P<percent>\d+\.)%'\n(%.+\n)*(?P<curve>(\s*\d+\s+\d+\n)+)", compl_osc_data):
       compl_osc[m.group('percent')] = numpy.fromstring(m.group('curve'), sep=' ').reshape((-1,2))
       
    info['completeness_statistics'] = {}
    first = True
    for percent, curve in compl_osc.items():
        if first:
            first = False
            info['completeness_statistics']['start_angle'] = list(curve[:,0])
        info['completeness_statistics'][percent] = list(curve[:,1])
       
    
#    exp_data, pos = utils.cut_section('Total exposure time vs resolution', 'DATA=CURVE2D', data)
#    exp_info = {}
#    for m in re.finditer("# Curve (?P<index>\d+)\n(%.+\n)*(?P<curve>(\s*\d+\.\d+\s+\d+\.\d+\n)+)", exp_data):
#        exp_info[m.group('index')] = numpy.fromstring(m.group('curve'), sep=' ').reshape((-1,2))
#       
#    info['exposure_statistics'] = {
#        'inv_res_sq': list(exp_info['1'][:,0]),
#        'time': list(exp_info['1'][:,1]),
#        'prediction': {
#            'inv_res_sq': list(exp_info['2'][:,0]),
#            'time': list(exp_info['2'][:,1]),
#        }
#    }

    return info

def extract_xml_table(xml_node, list_name):
    _table = []
    for subnode in xml_node.getElementsByTagName('list'):
        name = subnode.getAttribute('name')
        index = subnode.getAttribute('index')
        if name == list_name:
            _entry = {}
            for item in subnode.getElementsByTagName('item'):
                key = item.getAttribute('name')
                value = item.firstChild.nodeValue
                try:
                    value = float(value)
                except:
                    value = value
                _entry[key] = value
            # restrict keys to those in the first entry
            if len(_table) == 0 or set(_entry.keys()) == set(_table[0][1].keys()):
                _table.append((int(index), _entry))
    _sorted_table = utils.Table([v for _,v in sorted(_table)])
    final_table = {}
    for k in _sorted_table.keys():
        final_table[k] = _sorted_table[k]
    return final_table
    
        
def parse_best(filename_prefix='best'):
    """read BEST XML and PLOT file output returns a dictionary"""
    filename = '%s.xml' % filename_prefix
    summary = {}
    if not os.path.exists(filename):
        return summary
    doc = xml.dom.minidom.parse(filename)
    summary['runs'] = []
    summary['prediction_all'] = {}
    summary['prediction_hi'] = {}
    summary['details'] = {}


    best_version = doc.childNodes[1].getAttribute('version').split()

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
                    run[u'name'] = 'Run %d' % (int(index))
                    run[u'number'] = int(index)
                    for item in subnode.getElementsByTagName('item'):
                        key = item.getAttribute('name')
                        value = item.firstChild.nodeValue
                        if key != 'overlaps':
                            value = float(value)
                        run[key] = value
                    if best_version[0] == '3.4.4':
                        run['distance'] = summary['distance']
                    summary['runs'].append(run)
        elif name == 'statistical_prediction' and index == '1':
            summary['details']['shell_statistics'] = extract_xml_table(node,'resolution_bin')
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
        elif name == 'dc_optimal_time' and index == '1':
            summary['details']['time_statistics'] = extract_xml_table(node, 'compl_time_vs_resolution')
        
    #fix the attenuation
    if best_version[0] == '3.4.4':
        summary['attenuation'] = 100.0 - summary['transmission'])
        del summary['transmission']
    else:
        summary['attenuation'] = 100*(1.0 - summary['attenuation'])
    
    #parse the plot file if any
    plot_stats = parse_best_plot('%s.plot' % filename_prefix)
    summary['details'].update(plot_stats)
    return summary
