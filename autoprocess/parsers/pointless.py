"""
Parsers for POINTLESS output xml files

"""
import xml.dom.minidom

import autoprocess.errors
from autoprocess.utils import xtal


def parse_pointless(filename="pointless.xml"):
    """
    read Pointless XML output and return  a dictionay
    
    """
    try:
        doc = xml.dom.minidom.parse(filename)
        summary_el = doc.getElementsByTagName('BestSolution')[0]
        sg_list = doc.getElementsByTagName('Spacegroup')
    except:
        raise autoprocess.errors.ParserError('POINTLESS output is invalid')
    sg_candidates = []
    sg_dict = {}

    # extract all the tested candidates
    for sg_el in sg_list:
        sg_name = (sg_el.getElementsByTagName('SpacegroupName')[0].firstChild.nodeValue).strip()
        sg_number = int(sg_el.getElementsByTagName('SGnumber')[0].firstChild.nodeValue)
        sg_prob = float(sg_el.getElementsByTagName('TotalProb')[0].firstChild.nodeValue)
        sg_sys_abs_prob = float(sg_el.getElementsByTagName('SysAbsProb')[0].firstChild.nodeValue)
        rdx_list = (sg_el.getElementsByTagName('ReindexMatrix')[0].firstChild.nodeValue).split()
        rt = [int(rdx_list[i]) for i in range(len(rdx_list))]
        rdx_matrix = (rt[0], rt[3], rt[6], 0, rt[1], rt[4], rt[7], 0, rt[2], rt[5], rt[8], 0)
        # hxds = kptless, kxds = hptless, lxds = -lptless
        # rdx_matrix = ( rt[1], rt[4], rt[7], 0, rt[0], rt[3], rt[6], 0, -rt[2], -rt[5], -rt[8], 0)
        el = {}
        el['name'] = sg_name
        el['number'] = sg_number
        el['probability'] = sg_prob
        el['sys_abs_prob'] = sg_sys_abs_prob
        el['reindex_matrix'] = rdx_matrix
        el['reindex_operator'] = sg_el.getElementsByTagName('ReindexOperator')[0].firstChild.nodeValue
        sg_candidates.append(el)
        sg_dict[sg_name] = sg_number

    sg_candidates.sort(key=lambda el: (el['probability'], el['sys_abs_prob'], el['number']))
    best_candidate = sg_candidates[0]

    # summary for the best solution
    if summary_el.getAttribute('Type') == 'pointgroup':
        summary = {
            'type': 'point group',
            'sg_name': best_candidate['name'],
            'sg_number': best_candidate['number'],
            'reindex_operator': best_candidate['reindex_operator'],
            'confidence': float(summary_el.getElementsByTagName('Confidence')[0].firstChild.nodeValue),
            'probability': best_candidate['probability'],
            'reindex_matrix': best_candidate['reindex_matrix']
        }
    else:
        name = summary_el.getElementsByTagName('GroupName')[0].firstChild.nodeValue
        rdx_list = (summary_el.getElementsByTagName('ReindexMatrix')[0].firstChild.nodeValue).split()
        rt = [int(rdx_list[i]) for i in range(len(rdx_list))]
        rdx_matrix = (rt[0], rt[3], rt[6], 0, rt[1], rt[4], rt[7], 0, rt[2], rt[5], rt[8], 0)

        summary = {
            'type': 'space group',
            'sg_name': name,
            'sg_number': sg_dict[name],
            'reindex_operator': summary_el.getElementsByTagName('ReindexOperator')[0].firstChild.nodeValue,
            'confidence': float(summary_el.getElementsByTagName('Confidence')[0].firstChild.nodeValue),
            'probability': float(summary_el.getElementsByTagName('TotalProb')[0].firstChild.nodeValue),
            'reindex_matrix': rdx_matrix
        }

    # extract the unit cell
    # FIXME: Does not work
    lattice_el = doc.getElementsByTagName('LatticeSymmetry')[0]
    cell_el = lattice_el.getElementsByTagName('cell')[0]
    unit_cell = (
        float(cell_el.getElementsByTagName('a')[0].firstChild.nodeValue),
        float(cell_el.getElementsByTagName('b')[0].firstChild.nodeValue),
        float(cell_el.getElementsByTagName('c')[0].firstChild.nodeValue),
        float(cell_el.getElementsByTagName('alpha')[0].firstChild.nodeValue),
        float(cell_el.getElementsByTagName('beta')[0].firstChild.nodeValue),
        float(cell_el.getElementsByTagName('gamma')[0].firstChild.nodeValue),
    )
    summary['unit_cell'] = unit_cell

    summary['character'] = xtal.get_character(summary['sg_number'])
    summary['candidates'] = sg_candidates

    return summary
