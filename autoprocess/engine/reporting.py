import os
import re
import textwrap

from autoprocess.utils.prettytable import PrettyTable
from autoprocess.utils import xtal, misc, log
from autoprocess.utils.misc import json, Table, SortedDict
from autoprocess.utils import htmlreport

_logger = log.get_module_logger(__name__)

AUTOXDS_SCREENING, AUTOXDS_PROCESSING = range(2)

def text_heading(txt, level=1):
    if level in [1,2]:
        _pad = ' '*((78 - len(txt))//2)
        txt = '%s%s%s' % (_pad, txt, _pad)
        if level == 2:
            _banner = '-'*78
        else:
            _banner = '*'*78
            txt = txt.upper()
        _out = '\n%s\n%s\n%s\n\n' % (_banner, txt, _banner)
    elif level == 3:
        _pad = '*'*((74 - len(txt))//2)
        _out = '\n%s  %s  %s\n\n' % (_pad, txt, _pad)
    elif level == 4:
        _out = '\n%s:\n' % (txt.upper(),)
    else:
        _out = txt
    return _out

def add_margin(txt, size=1):
    _margin = ' '*size
    return '\n'.join([_margin+s for s in txt.split('\n')]) 


def format_section(section, level=1, invert=False, fields=[], show_title=True):
    _section = section
    if show_title:
        file_text = text_heading(_section['title'], level)
    else:
        file_text = ''
        
    if _section.get('table'):
        _key = 'table'
    elif _section.get('table+plot') :
        _key = 'table+plot'
    else:
        return ''
    pt = PrettyTable()
    if not invert:
        for i, d in enumerate(_section[_key]):
            dd = SortedDict(d)
            values = dd.values()
            if i == 0:
                keys = dd.keys()
                pt.add_column(keys[0], keys[1:],'l')
            pt.add_column(values[0], values[1:], 'r')
    else:
        for i, d in enumerate(_section[_key]):
            dd = SortedDict(d)
            values = dd.values()
            if i == 0:
                keys = dd.keys()
                pt.field_names = keys
            pt.add_row(values)
        pt.align = "r"
    if len(fields) == 0:
        file_text += pt.get_string()
    else:
        file_text += pt.get_string(fields=fields)
    file_text +='\n'
    if _section.get('notes'):
        all_notes = _section.get('notes').split('\n')
        notes = []
        for note in all_notes:
            notes += textwrap.wrap( note, width=60, subsequent_indent="    ")
        file_text += '\n'.join(notes)
    file_text += '\n'
    return file_text

def get_log_data(datasets, options={}):
    if options.get('anomalous', False):
        adj = 'Anomalous'
    else:
        adj = 'Native'
    info = {}
    
    _section = {}
    _section['title'] = '%s Data Processing Summary' % adj
    _sum_keys = ['Dataset','Score [a]', 'Wavelength (A)',    'Space Group [b]',
                  'Unit Cell (A)', '        (deg)', 
                  'Cell Volume (A^3)', 'Resolution (A)[c]', 'All Reflections',
                  'Unique Reflections', 'Multiplicity', 'Completeness',
                  'I/sigma(I) [d]', 'CC(1/2) [f]',
                  'R-meas [e]', 'Mosaicity', 'sigma(spot) (pix)', 'sigma(angle) (deg)','No. Ice rings',
                  ]
    _section['table'] = []
    resol_method = {
        0: 'Based on detector edge',
        1: 'Based on I/sigma(I) > 0.5 ',
        2: 'Based on CC(1/2) significant at 0.1% level.',
        3: 'Calculated by DISTL (see Zang et al, J. Appl. Cryst. (2006). 39, 112-119',
        4: 'Manualy chosen',
    }
    data_items = datasets.items()
    if options.get('mode') == 'merge':
        data_items.append( ('*combined*', data_items[0][1]) )
        # update the combined data with the weighted average cell
        cell_weights = []
        for _, dset in data_items[:-1]:
            cell_weights.append((dset.results['correction']['summary']['unit_cell'],
                                 dset.results['correction']['total_reflections']))
        avgcell, avgcell_esd = xtal.average_cell(cell_weights)
        dset = data_items[-1][1]
        dset.results['correction']['summary']['unit_cell'] = avgcell
        dset.results['correction']['summary']['unit_cell_esd'] = avgcell_esd
        
    for dataset_name, dset in data_items:
        #if options.get('mode') == 'merge' and dataset_name != '*combined*':
        #    continue
        dres= dset.results
        if dres.get('image_analysis'):
            _ice_rings = dres['image_analysis']['summary']['ice_rings']
        else:
            _ice_rings = 'N/C'
        
        _mos = '%0.2f' % dres['correction']['summary']['mosaicity']
        _std_pix = '%0.1f' % (dres['correction']['summary']['stdev_spot'],)
        _std_deg = '%0.1f' % (dres['correction']['summary']['stdev_spindle'],)
        if options.get('mode') != 'merge':
            _summary = dres['scaling']
            _score = dres['crystal_score']            
            _compl = _summary['summary']['completeness']
        elif dataset_name == "*combined*":
            _ice_rings = 'N/A'
            _summary = dres['scaling']
            _score = dset.score()
            _std_pix = "N/A"
            _std_deg = "N/A"
            _mos = "N/A"
            _compl = dres['data_quality']['completeness']*100.0
        else: 
            _summary = dres['correction']
            _score = dset.score()
            _compl = _summary['summary']['completeness']

        _sum_values = [ dataset_name,
            '%0.2f' % _score,
            '%7.4f' % (dset.parameters['wavelength'],),
            xtal.SPACE_GROUP_NAMES[ dres['correction']['symmetry']['space_group']['sg_number'] ],
            '%0.4f %0.4f %0.4f' % tuple(dres['correction']['summary']['unit_cell'][:3]),
            '%0.4f %0.4f %0.4f' % tuple(dres['correction']['summary']['unit_cell'][3:]),
            '%0.0f' % (xtal.cell_volume(dres['correction']['summary']['unit_cell']),),
            '%0.2f' % _summary['summary']['resolution'][0],
            _summary['summary']['observed'],
            _summary['summary']['unique'],
            '%0.1f' % (float(_summary['summary']['observed'])/_summary['summary']['unique'],),
            '%0.1f%%' % (_compl,),
            '%0.1f' % (_summary['summary']['i_sigma'],),
            '%0.1f' % (_summary['summary']['cc_half'],),
            '%0.1f%%' % (_summary['summary']['r_meas'],),
            _mos,
            _std_pix,
            _std_deg,
            _ice_rings,
            ]
        _section['table'].append(zip(_sum_keys, _sum_values))
    _section['notes'] = """[a] Data Quality Score. > 0.8 Excellent, > 0.6 Good, > 0.5 Acceptable, > 0.4 Marginal, > 0.3 Barely usable
[b] NOTE: Automatic Space group selection is unreliable for incomplete data. See detailed results below.
[c] Resolution selection method: %s
[d] Average I/sigma(I) for all data.
[e] Redundancy independent R-factor. Diederichs & Karplus (1997), Nature Struct. Biol. 4, 269-275.
[f] Percentage correlation between intensities from random half-datasets. (see Karplus & Diederichs (2012), Science. 336 (6084): 1030-1033)""" % resol_method[_summary['summary']['resolution'][1]]
    info['summary'] = _section
    
    # print data collection parameters
    _section = {}
    _section['title'] = '%s Data Collection Parameters' % adj
    _section['table'] = []
    _keys = ['Description', 'Detector Distance (mm)','Exposure Time (sec)', 'No. Frames', 'Starting Angle (deg)',
             'Delta (deg)', 'Two Theta (deg)', 'Detector Origin (pix)', 'Detector Size (pix)',
             'Pixel Size (um)', 'File Template']
    for dataset_name, dset in data_items:
        if dataset_name == "*combined*": continue
        
        dres = dset.results
        # print out data collection parameters
        
        _rows = [dataset_name, dset.parameters['distance'],
                dset.parameters['exposure_time'],
                dset.parameters['frame_count'],
                dset.parameters['start_angle'],
                dset.parameters['delta_angle'], 
                '%0.1f' % dset.parameters['two_theta'], 
                '%0.0f x %0.0f' %  tuple(dset.parameters['beam_center']),
                '%d x %d' %  tuple(dset.parameters['detector_size']), 
                '%0.5f x %0.5f' %  (dset.parameters['pixel_size'],dset.parameters['pixel_size']),
                 os.path.basename(dset.parameters['file_template']),]
        _section['table'].append(zip(_keys, _rows))
    info['parameters'] =  _section
    
    
    info['details'] = {}
    for dataset_name, dset in data_items:

        info['details'][dataset_name] = {}
        dres = dset.results
        
        # Print out strategy information
        if dres.get('strategy'):
            _strategy = {}
            _strategy['summary'] = {}
            _strategy['summary']['title'] = 'Recommended Strategy for %s Data Collection' % adj
            _strategy['summary']['table'] = []
            _strategy_keys = ['', 'Attenuation (%)', 'Distance (mm)',    'Start Angle',
                  'Delta (deg)', 'No. Frames', 'Total Angle (deg)', 'Exposure Time (s) [a]',
                  'Overlaps?', '-- Expected Quality --', 'Resolution',
                  'Completeness (%)', 'Multiplicity',
                  'I/sigma(I) [b]', 'R-factor (%) [b]' ]
            for run in dres['strategy'].get('runs', []):
                _name = run['name']
                if run['number'] == 1:
                    _res = '%0.2f [c]' % (dres['strategy']['resolution'],)
                    _cmpl = '%0.1f' % (dres['strategy']['completeness'],)
                    _mlt = '%0.1f' % (dres['strategy']['redundancy'],)
                    _i_sigma = '%0.1f (%0.1f)' % (dres['strategy']['prediction_all']['average_i_over_sigma'],
                                                  dres['strategy']['prediction_hi']['average_i_over_sigma'])
                    _r_fac = '%0.1f (%0.1f)' % (dres['strategy']['prediction_all']['R_factor'],
                                                dres['strategy']['prediction_hi']['R_factor'])
                else:
                    _res = _cmpl = _mlt = _i_sigma = _r_fac = '<--'
                    

                _strategy_vals = [_name, '%0.0f' % (dres['strategy']['attenuation'],), 
                  '%0.1f' % (run['distance'],), 
                  '%0.1f' % (run['phi_start'],),
                  '%0.2f' % (run['phi_width'],), 
                  '%0.0f' % (run['number_of_images'],), 
                  '%0.2f' % (run['phi_width'] * run['number_of_images'],), 
                  '%0.1f' % (run['exposure_time'],),
                  '%s' % (run['overlaps'],), '-------------',
                  _res, _cmpl, _mlt, _i_sigma, _r_fac,                      
                  ]
                _strategy['summary']['table'].append(zip(_strategy_keys,_strategy_vals))

            _strategy['summary']['notes'] = """[a] NOTE: Recommended exposure time does not take into account overloads at low resolution!
[b] Values in parenthesis represent the high resolution shell.
[c] %s \n"""  %  dres['strategy'].get('resolution_reasoning','N/A')
                        
            _section = {}
            _section['title'] = 'Maximum Delta Angle to Prevent Angular Overlap'
            _section['table'] = []
            for row in dres['indexing']['oscillation_ranges']:
                n_row = SortedDict()                
                for k,t in [('High Resolution Limit','resolution'),('Max. Angle Delta [a]', 'delta_angle')]:
                    n_row[k] = row[t]
                _section['table'].append(n_row.items())
            _section['notes'] ='[a] NOTE: Only a rough estimate. Assumes a mosaicity of zero!'
            _strategy['overlap'] = _section
            info['details'][dataset_name]['strategy'] = _strategy
        
        if dataset_name != '*combined*':
            _section = {}
            _section['lattices'] = {}
            _section['lattices']['title'] = 'Compatible Lattice Character and Bravais Lattices'
            _section['lattices']['table'] = []
            _sec_keys = ['No.', 'Character', 'Cell Parameters', 'Quality', 'Cell Volume', 'Reindexing Matrix']
            for l in dres['correction']['symmetry']['lattices']:
                if l['star'] != '*': continue  #incompatible lattices
                id, lat_type = l['id']
                row = [id, 
                    lat_type, 
                    '%5.1f %5.1f %5.1f %5.1f %5.1f %5.1f' % xtal.tidy_cell(l['unit_cell'], lat_type),
                    l['quality'], "%0.1f" % xtal.cell_volume( l['unit_cell'] ),
                    '%2d %2d %2d %2d %2d %2d %2d %2d %2d %2d %2d %2d' % tuple(l['reindex_matrix']) ]
                _section['lattices']['table'].append(zip(_sec_keys, row))
            
            _section['space_groups'] = {}
            _section['space_groups']['title'] = 'Likely Space Groups and their probabilities'
            _section['space_groups']['table'] = []
            _sec_keys = ['Space Group','No.', 'Probability']
            sg_num = dres['correction']['symmetry']['space_group']['sg_number']
            sg_name = xtal.SPACE_GROUP_NAMES[ sg_num ]
            if dres['symmetry'].get('candidates'):
                for i, sol in enumerate(dres['symmetry']['candidates']):
                    if sg_num == sol['number'] and i== 0:
                        sg_name = '* %s' % (xtal.SPACE_GROUP_NAMES[ sol['number'] ])
                    else:
                        sg_name = '  %s' % (xtal.SPACE_GROUP_NAMES[ sol['number'] ])
                    row = [ sg_name,   sol['number'],    sol['probability']]
                    _section['space_groups']['table'].append(zip(_sec_keys, row))
                u_cell = xtal.tidy_cell(dres['symmetry']['unit_cell'], dres['symmetry']['character'])
                sg_name = xtal.SPACE_GROUP_NAMES[ dres['symmetry']['sg_number'] ]
                _section['space_groups']['notes'] = "[*] Selected:  %s,  #%s. " % ( 
                    sg_name, dres['symmetry']['sg_number'] )
                _section['space_groups']['notes'] += " Unit Cell: %5.1f %5.1f %5.1f %5.1f %5.1f %5.1f." % u_cell 
                _section['space_groups']['notes'] += " NOTE: Detailed statistics reported below use this selection. "    
                if dres['symmetry']['type'] == 'PointGroup':
                    _section['space_groups']['notes'] += """
        [!] Space Group is ambiguous. The lowest symmetry group of the high probability candidates has been chosen to permit reindexing in the future without loss of data!"""
            
            info['details'][dataset_name]['symmetry'] = _section
            
            # Print out integration results
            _section = {}
            _section['title'] = "Integration Statistics"
            _section['plot'] = []
            _keymap = [('Frame No.','frame'),('Scale Factor', 'scale'),('Overloads','overloads'), 
                       ('Reflections','reflections'), ('Mosaicity', 'mosaicity'),
                       ('Unexpected Spots','unexpected'), ('Divergence','divergence')]
            for row in dres['integration']['scale_factors']:
                n_row = SortedDict()
                for k,t in _keymap:
                    n_row[k] = row[t]
                _section['plot'].append(n_row.items())
            _section['plot_axes'] = [('Frame No.',['Scale Factor']), ('Frame No.', ['Mosaicity']),('Frame No.',['Divergence'])]   
            info['details'][dataset_name]['integration'] = _section
    
            # Print out correction results
            _section = {}
            _section['title'] = "Correction Statistics"
            if dres.get('scaling'):
                _data_key = 'table'
            else:
                _data_key = 'table+plot'
                _section['plot_axes'] = [('Resolution',['R_meas', 'CC(1/2)', 'Completeness']),('Resolution', ['I/Sigma'])]
                if options.get('anomalous') == True:
                    _section['plot_axes'].append(('Resolution', ['SigAno']))
            _section[_data_key] = []
            for row in dres['correction']['statistics']:
                n_row = SortedDict()
                for k,t in [('Resolution','shell'),('Completeness', 'completeness'),('R_meas','r_meas'), ('CC(1/2)','cc_half'), ('I/Sigma','i_sigma'), ('SigAno','sig_ano'), ('AnoCorr','cor_ano')]:
                    n_row[k] = row[t]
                _section[_data_key].append(n_row.items())
            resol = dres['correction']['summary']['resolution']
            _section['notes'] = "Resolution cut-off (%s): %5.2f" % (resol_method[resol[1]], resol[0])    
            info['details'][dataset_name]['correction'] = _section
        
        # Print out scaling results
        if dres.get('scaling'):
            _section = {}
            _section['title'] = "Statistics of scaled output files"
            _section['shells'] = {}
            _section['shells']['title'] = "Statistics presented by resolution shell"
            _data_key = 'table+plot' 
            _section['shells'][_data_key] = []
            for row in dres['scaling']['statistics']:
                n_row = SortedDict()
                for k, t in [('Resolution', 'shell'), ('Completeness', 'completeness'), ('R_meas', 'r_meas'), ('CC(1/2)', 'cc_half'), ('I/Sigma', 'i_sigma'), ('SigAno', 'sig_ano'), ('AnoCorr', 'cor_ano')]:
                    n_row[k] = row[t]
                _section['shells'][_data_key].append(n_row.items())
                
            _section['shells']['plot_axes'] = [('Resolution', ['R_meas', 'CC(1/2)', 'Completeness']), ('Resolution', ['I/Sigma'])]
            if options.get('anomalous', False):
                _section['shells']['plot_axes'].append(('Resolution', ['SigAno']))
                          
            info['details'][dataset_name]['scaling'] = _section   

    return info

def _next_10th(x):
    return ((x//10)+1)*10

def get_reports(datasets, options={}):
    info = []
    
    count = 0
    for _name, dset in datasets.items():
        
        # Only generate report for first dataset when multi-merging
        if options.get('mode') == 'merge' and count > 0:
            continue
        elif options.get('mode') == 'merge':
            _report_directory = options["directory"]
            # data description is different for merged data
            dataset_name = misc.combine_names(datasets.keys())
        else:
            _report_directory = dset.parameters['working_directory']
            dataset_name = _name

        count += 1
                
        _dataset_info = {}
        dres = dset.results
        
        # read dataset file if present and use that to figure out the data_id, crystal_id, experiment_id
        data_id = None
        crystal_id = None
        exp_id = None

        dataset_file = re.sub('_[?]*\.[^.]*$', '.SUMMARY', dset.parameters['file_template'])
        if os.path.exists(dataset_file):
            dataset_info = json.load(file(dataset_file))
            data_id = dataset_info.get('id')
            crystal_id = dataset_info.get('crystal_id')
            exp_id = dataset_info.get('experiment_id')
        
        if dres.get('image_analysis'):
            _ice_rings = dres['image_analysis']['summary']['ice_rings']
        else:
            _ice_rings = -1
        
        if dres.get('scaling') and options.get('mode') != 'merge':
            _summary = dres['scaling']
        else:
            _summary= dres['correction']
        _sum_keys = ['name', 'data_id', 'crystal_id', 'experiment_id', 'score', 'space_group_id', 'cell_a','cell_b', 'cell_c', 'cell_alpha', 'cell_beta','cell_gamma',
                 'resolution','reflections', 'unique','multiplicity', 'completeness','mosaicity', 'i_sigma',
                 'r_meas','cc_half', 'sigma_spot', 'sigma_angle','ice_rings', 'url', 'wavelength']
        _sum_values = [
            dataset_name,
            data_id,
            crystal_id,
            exp_id,
            dres['crystal_score'], 
            dres['correction']['symmetry']['space_group']['sg_number'],
            dres['correction']['summary']['unit_cell'][0],
            dres['correction']['summary']['unit_cell'][1],
            dres['correction']['summary']['unit_cell'][2],
            dres['correction']['summary']['unit_cell'][3],
            dres['correction']['summary']['unit_cell'][4],
            dres['correction']['summary']['unit_cell'][5],
            _summary['summary']['resolution'][0],
            _summary['summary']['observed'],
            _summary['summary']['unique'],
            float(_summary['summary']['observed'])/_summary['summary']['unique'],
            _summary['summary']['completeness'],
            dres['correction']['summary']['mosaicity'],
            _summary['summary']['i_sigma'],
            _summary['summary']['r_meas'],
            _summary['summary']['cc_half'],
            dres['correction']['summary']['stdev_spot'],
            dres['correction']['summary']['stdev_spindle'],
            _ice_rings,
            _report_directory,
            dset.parameters['wavelength'],
            ]
        _dataset_info = dict(zip(_sum_keys, _sum_values))
        _dataset_info['details'] = {}
        
        
        resol_method = {
            0: 'based on detector edge',
            1: 'based on I/sigma(I) > 0.5',
            2: 'based on CC(1/2) significant at 0.1% level',
            3: 'by DISTL (see Zang et al, J. Appl. Cryst. (2006). 39, 112-119',
            4: 'manualy',
        }
        
        # set detailed parameters
        _dataset_info['details']['anomalous'] = options.get('anomalous', False)
        _dataset_info['details']['resolution_method'] = resol_method[_summary['summary']['resolution'][1]]
        
      
        # compatible lattices and space group selection
        _section = {}
        
        #select only compatible lattices
        _comp_lattices = []
        for _lat in dres['correction']['symmetry']['lattices']:
            if _lat['star'] == '*':
                _comp_lattices.append(_lat)


        _t = Table(_comp_lattices)
        _id = SortedDict(_t['id'])
        _section['id'] = _id.keys()
        _section['type'] = _id.values()
        _cell_fmt = '%5.1f %5.1f %5.1f %5.1f %5.1f %5.1f'
        _section['unit_cell'] = [_cell_fmt % tuple(c) for c in _t['unit_cell']]
        _section['quality'] = _t['quality']
        _section['volume'] = [xtal.cell_volume(c) for c in _t['unit_cell']]
        _dataset_info['details']['compatible_lattices'] = _section
        
        _section = {}
        _t = Table(dres['symmetry']['candidates'])
        _section['space_group'] = _t['number']
        _section['name'] = [xtal.SPACE_GROUP_NAMES[n] for n in  _section['space_group']]
        _section['probability'] = _t['probability']            
        _dataset_info['details']['spacegroup_selection'] = _section

        # Harvest screening details
        if options.get('mode', None) == 'screen':
            _dataset_info['kind'] = AUTOXDS_SCREENING

            if dres.get('strategy') and dres['strategy'].get('runs'):
                _strategy = dres['strategy']
                # harvest old strategy
                _strategy_keys = ['name', 'attenuation', 'distance',    'start_angle',
                    'delta_angle', 'total_angle', 'exposure_time',
                    'exp_resolution', 'exp_completeness', 'exp_multiplicity',
                    'exp_i_sigma', 'exp_r_factor', 'energy',
                    ]
                run = dres['strategy']['runs'][0]
                _strategy_vals = [
                  dataset_name,
                  _strategy['attenuation'], 
                  run['distance'], run['phi_start'], run['phi_width'], 
                  run['phi_width'] * run['number_of_images'], run['exposure_time'],
                  _strategy['resolution'], _strategy['completeness'],
                  _strategy['redundancy'], _strategy['prediction_all']['average_i_over_sigma'],
                  _strategy['prediction_all']['R_factor'],
                  ]
                _dataset_info['strategy'] = dict(zip(_strategy_keys,_strategy_vals))
                
                # harvest new strategy
                _section = {
                    'name': dataset_name,
                    'attenuation': _strategy['attenuation'], 
                    'resolution': _strategy['resolution'],
                    'distance': run['distance'],
                    'start_angle': run['phi_start'],
                    'delta_angle': run['phi_width'],
                    'total_angle': run['phi_width'] * run['number_of_images'],
                    'exposure_time': run['exposure_time'],
                    'resolution_reasoning': _strategy.get('resolution_reasoning', 'N/A'),
                    'completeness':    _strategy['completeness'],
                    'r_factor':  _strategy['prediction_all']['R_factor'],
                    'i_sigma': _strategy['prediction_all']['average_i_over_sigma'],
                    'multiplicity': _strategy['redundancy'],
                    'frac_overload': _strategy['prediction_all']['fract_overload'],
                    }
                _dataset_info['details']['strategy'] = _section
                
                # overlap_analysis and wedge analysis
                _st_details =_strategy.get('details', {})
                _dataset_info['details']['overlap_analysis'] = _st_details.get('delta_statistics')
                _dataset_info['details']['wedge_analysis'] = _st_details.get('completeness_statistics')
                _dataset_info['details']['crystal_alignment'] = _st_details.get('crystal_alignment')

                # shell_statistics
                _st_shell = _st_details.get('shell_statistics', {})
                _res_shells = [(x+y)/2.0 for x,y in zip(_st_shell.get('min_resolution',[]), _st_shell.get('max_resolution',[]))]
                if len(_res_shells) > 1:
                    _section = {
                        'shell': _res_shells[:-1],
                        'completeness': [x*100 for x in _st_shell['completeness'][:-1]],
                        'r_factor': _st_shell['R_factor'][:-1],
                        'i_sigma': _st_shell['average_i_over_sigma'][:-1],
                        'multiplicity': _st_shell['redundancy'][:-1],
                        'frac_overload': _st_shell['fract_overload'][:-1],
                        }
                    _dataset_info['details']['predicted_quality'] = _section

                # exposure time statistics
                _st_time = _st_details.get('time_statistics', {})
                _res_shells = _st_time.get('resolution_max',[])
                if len(_res_shells) > 0:
                    _section = {
                        'resolution': _res_shells,
                        'exposure_time': _st_time.get('ex_time'),
                        }
                    _dataset_info['details']['exposure_analysis'] = _section
               
                    
        else:  
            _dataset_info['kind'] = AUTOXDS_PROCESSING
            # Print out integration results
            _section = {}
            # combine integration statistics if merging
            scale_factors = dres['integration']['scale_factors']
            if options.get('mode') == 'merge':
                max_frame = max([v['frame'] for v in scale_factors])
                for dat in datasets.values()[1:] :
                    _dat_sf = []
                    _dat_sf.extend(dat.results['integration']['scale_factors'])
                    next_start = _next_10th(max_frame)
                    for v in _dat_sf:
                        v['frame'] = v['frame'] + next_start
                        max_frame = v['frame']
                    scale_factors.extend(dat.results['integration']['scale_factors'])
            _t = Table(scale_factors)
            for k in ['frame','scale','overloads','reflections','mosaicity','unexpected','divergence']:
                _section[k] = _t[k]
                
            if dres['correction'].get('frame_statistics'):
                frame_stats =  dres['correction']['frame_statistics']
                if options.get('mode') == 'merge':
                    max_frame = max([v['frame'] for v in frame_stats])
                    for dat in datasets.values()[1:] :
                        _dat = []
                        _dat.extend(dat.results['correction']['frame_statistics'])
                        next_start = _next_10th(max_frame)
                        for v in _dat:
                            v['frame'] = v['frame'] + next_start
                            max_frame = v['frame']
                        frame_stats.extend(dat.results['correction']['frame_statistics'])
                                   
                _t = Table(frame_stats)
                _section['frame_no'] = _t['frame']
                for k in ['i_obs', 'n_misfit', 'r_meas', 'i_sigma', 'unique', 'corr']:
                    _section[k] = _t[k]
                    
            if dres['correction'].get('diff_statistics'):
                diff_stats =  dres['correction']['diff_statistics']
                if options.get('mode') == 'merge':
                    max_frame = max([v['frame_diff'] for v in diff_stats])
                    for dat in datasets.values()[1:] :
                        _dat = []
                        _dat.extend(dat.results['correction']['diff_statistics'])
                        next_start = _next_10th(max_frame)
                        for v in _dat:
                            v['frame_diff'] = v['frame_diff'] + next_start
                            max_frame = v['frame_diff']
                        diff_stats.extend(dat.results['correction']['diff_statistics'])
                                   
                _t = Table(diff_stats)
                _dataset_info['details']['diff_statistics'] = {}
                for k in ['frame_diff', 'rd', 'rd_friedel', 'rd_non_friedel', 'n_refl', 'n_friedel', 'n_non_friedel']:
                    _dataset_info['details']['diff_statistics'][k] = _t[k]
            _dataset_info['details']['frame_statistics'] = _section
            
            _section = {}
            _t = Table(dres['integration']['batches'])
            for k in ['range','unit_cell','stdev_spot','stdev_spindle','mosaicity','distance','beam_center']:
                _section[k] = _t[k]
            _dataset_info['details']['integration_batches'] = _section
                
            # Print out correction results
            _section = {}
            if dres.get('scaling') and dres['scaling'].get('statistics'):
                _t = Table(dres['scaling']['statistics'])
            else:
                _t = Table(dres['correction']['statistics'])
            for k in ['completeness','r_meas','cc_half','i_sigma','sig_ano','cor_ano']:
                _section[k] = _t[k][:-1] # don't get 'total' row
            _section['shell'] = [float(v) for v in _t['shell'][:-1]]
            _dataset_info['details']['shell_statistics'] = _section
            
            # Print out standard errors
            if dres['correction'].get('standard_errors'):
                _section = {}
                _t = Table(dres['correction']['standard_errors'])
                _section['shell'] = [sum(v)/2.0 for v in _t['resol_range'][:-1]] # don't get 'total' row
                for k in ['chi_sq', 'i_sigma', 'r_obs', 'r_exp','n_obs', 'n_accept', 'n_reject']:
                    _section[k] = _t[k][:-1]
                _dataset_info['details']['standard_errors'] = _section
                
            # correction factors
            _dataset_info['details']['correction_factors'] = dres['correction'].get('correction_factors')

            # Print out wilson_plot, cum int dist, twinning test
            if dres['scaling'].get('wilson_plot'):
                _section = {}
                _t = Table(dres['scaling']['wilson_plot'])
                for k in ['inv_res_sq', 'mean_i']:
                    _section[k] = _t[k]
                _dataset_info['details']['wilson_plot'] = _section
            if dres['scaling'].get('wilson_line'):
                _dataset_info['details']['wilson_line'] = dres['scaling']['wilson_line']

            if dres.get('data_quality'):
                if dres['data_quality'].get('intensity_plots'):
                    _section = {}
                    _t = Table(dres['data_quality']['intensity_plots'])
                    for k in ['inv_res_sq', 'expected_i', 'mean_i_binned', 'mean_i']:
                        _section[k] = _t[k]
                    _dataset_info['details']['wilson_plot'] = _section
                if dres['data_quality'].get('twinning_l_test'):
                    _section = {}
                    _t = Table(dres['data_quality']['twinning_l_test'])
                    for k in ['abs_l', 'observed', 'twinned', 'untwinned']:
                        _section[k] = _t[k]
                    _dataset_info['details']['twinning_l_test'] = _section
                    
                if dres['data_quality'].get('twin_laws'):
                    _dataset_info['details']['twin_laws'] = dres['data_quality']['twin_laws']
                if dres['data_quality'].get('twinning_l_statistic'):
                    _dataset_info['details']['twinning_l_statistic'] = dres['data_quality']['twinning_l_statistic']
                if dres['data_quality'].get('twinning_l_zscore'):
                    _dataset_info['details']['twinning_l_zscore'] = dres['data_quality']['twinning_l_zscore']

            # Save converted output files
            if dres.get('output_files') and len(dres.get('output_files')) > 0:
                _dataset_info['details']['output_files'] = dres.get('output_files')
      
        info.append(_dataset_info)
    return info
    
def save_json(result_list, filename, options={}):

    names = [v['name'] for v in result_list]
    
    # read previous json_file and obtain id from it if one exists:
    if os.path.exists(filename):
        old_json = misc.load_json(filename)
        for res in old_json:
            dataset_name = res['name']
            if dataset_name in names:
                pos = names.index(dataset_name)
                result_list[pos]['id'] = res.get('id')

    # save process.json
    with open(filename, 'w') as handle:
        json.dump(result_list, handle)

    

def save_html(result_list, options={}):
    #generate html reports

    for report in result_list:
        report_directory = os.path.join(report['url'],'report')
        if not os.path.exists(report_directory):
            os.makedirs(report_directory)
        if report['kind'] == AUTOXDS_SCREENING:
            htmlreport.create_screening_report(report, report_directory)
        else:
            htmlreport.create_full_report(report, report_directory)    
        _logger.info('Report summary: %s/index.html' % (misc.relpath(report_directory, options['command_dir']) ))

def save_log(info, filename):
    fh = open(filename, 'w')

    # print summary
    file_text = format_section(info['summary'], level=1)
    file_text += format_section(info['parameters'], level=1)
    for name, dset in info['details'].items():
        file_text += text_heading("DETAILED RESULTS FOR DATASET: '%s'" % (name), level=1)
        if dset.get('strategy', None) is not None: 
            file_text += text_heading("Data Collection Strategy", level=2)
            for key in ['summary','overlap']:
                if key in ['oscillation', 'overlap']:
                    invert = True
                else:
                    invert = False
                file_text += format_section(dset['strategy'][key], level=3, invert=invert)
        if dset.get('symmetry') is not None:
            file_text += text_heading("Lattice Character and Space Group Determination", level=2)
            file_text += format_section(dset['symmetry']['lattices'], level=3, 
                            invert=True, fields=['No.','Character', 'Cell Parameters', 'Quality'])
            file_text += format_section(dset['symmetry']['lattices'], level=3, 
                            invert=True, fields=['No.', 'Cell Volume','Reindexing Matrix'], show_title=False)
            file_text += format_section(dset['symmetry']['space_groups'], level=3, invert=True)
            file_text += format_section(dset['correction'], level=2, invert=True)
        if dset.get('scaling') is not None:
            file_text += text_heading(dset['scaling']['title'], level=2)
            for key in ['shells']:
                file_text += format_section(dset['scaling'][key], level=3, invert=True)
    
    file_text += '\n\n'
    out_text = add_margin(file_text, 1)
    fh.write(out_text)   
    fh.close()
    
