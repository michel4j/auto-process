# -*- coding: utf-8 -*-
""" 
Data Processing Class

"""

import os, sys, time

from dpm.parser.pointless import parse_pointless
from dpm.parser.distl import parse_distl
from dpm.parser import xds
from dpm.parser.best import parse_best
from dpm.utils.log import get_module_logger, log_to_console
from dpm.utils.prettytable import PrettyTable, MSWORD_FRIENDLY
from dpm.utils.progress import ProgDisplay, ProgChecker
from dpm.parser.utils import Table
from gnosis.xml import pickle
from dpm.utils.odict import SortedDict
import pprint
import utils, io

_logger = get_module_logger('AutoXDS')

class AutoXDS:

    def __init__(self, options):
        self.options = options
        self.results = {}
        is_screening = (self.options.get('command', None) == 'screen')
        self.dataset_info = {}
        self.cpu_count = utils.get_cpu_count()
        _logger.info('Using %d CPUs.' % self.cpu_count)
        self.dataset_names = []
        # prepare dataset info
        for i, img in enumerate(self.options['images']):
            run_info = utils.get_dataset_params(img, is_screening)
            run_info['cpu_count'] = self.cpu_count
            run_info['anomalous'] = self.options.get('anomalous', False)
            if self.options.get('prefix'):
                run_info['dataset_name'] = self.options['prefix'][i]
            self.dataset_info[run_info['dataset_name']] =  run_info
            self.dataset_names.append(run_info['dataset_name'])
            
        
        # prepare top level working directory
        if is_screening:
            _suffix = 'scrn'
        else: 
            _suffix = 'proc'
        _prefix = os.path.commonprefix(self.dataset_info.keys())
        if _prefix == '':
            _prefix = '_'.join(self.dataset_info.keys())
        elif _prefix[-1] == '_':
            _prefix = _prefix[:-1]
        work_dir = '%s-%s' % (_prefix, _suffix)
        self.top_directory = utils.prepare_work_dir(
                self.options.get('directory', './'),  work_dir, backup=self.options.get('backup', False))
        
        # for multiple data sets, process each in a separate subdirectory
        if len(self.dataset_info.keys()) ==1:
            for name, run_info in self.dataset_info.items():
                run_info['working_directory'] = self.top_directory
        else:   
            for name, run_info in self.dataset_info.items():
                run_info['working_directory'] = os.path.join(self.top_directory,
                                                             run_info['dataset_name'])
        os.chdir(self.top_directory)
        
    def save_log(self, filename='process.log'):
        if self.options.get('anomalous', False):
            adj = 'ANOMALOUS'
        else:
            adj = 'NATIVE'
        info = self.get_log_dict()
        os.chdir(self.top_directory)
        fh = open(filename, 'w')

        # print summary
        file_text = utils.format_section(info['summary'], level=1)
        for name, dset in info['details'].items():
            file_text += utils.text_heading("DETAILED RESULTS FOR %s DATASET: '%s'" % (adj, name), level=1)
            file_text += utils.format_section(dset['parameters'], level=2)
            if dset.get('strategy', None) is not None: 
                file_text += utils.text_heading("Data Collection Strategy", level=2)
                for key in ['summary','oscillation', 'overlap']:
                    if key in ['oscillation', 'overlap']:
                        invert = True
                    else:
                        invert = False
                    file_text += utils.format_section(dset['strategy'][key], level=3, invert=invert)
            file_text += utils.text_heading("Lattice Character and Space Group Determination", level=2)
            file_text += utils.format_section(dset['symmetry']['lattices'], level=3, 
                            invert=True, fields=['No.','Character', 'Cell Parameters', 'Quality'])
            file_text += utils.format_section(dset['symmetry']['lattices'], level=3, 
                            invert=True, fields=['No.', 'Cell Volume','Reindexing Matrix'], show_title=False)
            file_text += utils.format_section(dset['symmetry']['space_groups'], level=3, invert=True)
            file_text += utils.format_section(dset['correction'], level=2, invert=True)
            file_text += utils.format_section(dset['scaling'], level=2, invert=True)
        
        file_text += '\n\n'
        out_text = utils.add_margin(file_text, 1)
        fh.write(out_text)    
        fh.close()
        
    def get_log_dict(self):
        if self.options.get('anomalous', False):
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
                      'Mosaicity', 'I/sigma(I) [d]', 'R-mrgd-F [e]',
                      'R-meas [f]', 'sigma(spot) (pix)', 'sigma(angle) (deg)','No. Ice rings',
                      ]
        _section['table'] = []
        for dataset_name in self.dataset_names:
            dset = self.results[dataset_name]
            if dset.get('image_analysis', None) is not None:
                _ice_rings = dset['image_analysis']['summary']['ice_rings']
            else:
                _ice_rings = 'N/C'
            if dset.get('scaling', None) is not None:
                _summary = dset['scaling']
            else:
                _summary= dset['correction']
            _sum_values = [ dataset_name,
                '%0.2f' % (dset['crystal_score'],),
                '%7.4f' % (self.dataset_info[dataset_name]['wavelength'],),
                utils.SPACE_GROUP_NAMES[ dset['correction']['symmetry']['space_group']['sg_number'] ],
                '%0.1f %0.1f %0.1f' % dset['correction']['symmetry']['space_group']['unit_cell'][:3],
                '%0.1f %0.1f %0.1f' % dset['correction']['symmetry']['space_group']['unit_cell'][3:],
                '%0.0f' % (utils.cell_volume(dset['correction']['symmetry']['space_group']['unit_cell']),),
                '%0.2f (%0.2f)' % _summary['resolution'],
                _summary['summary']['observed'],
                _summary['summary']['unique'],
                '%0.1f' % (float(_summary['summary']['observed'])/_summary['summary']['unique'],),
                '%0.1f%%' % (_summary['summary']['completeness'],),
                '%0.2f' % (dset['correction']['summary']['mosaicity'],),
                '%0.1f' % (_summary['summary']['i_sigma'],),
                '%0.1f%%' % (_summary['summary']['r_mrgdf'],),
                '%0.1f%%' % (_summary['summary']['r_meas'],),
                '%0.1f' % (dset['correction']['summary']['stdev_spot'],),
                '%0.1f' % (dset['correction']['summary']['stdev_spindle'],),
                _ice_rings,
                ]
            _section['table'].append(zip(_sum_keys, _sum_values))
        _section['notes'] = """[a] Data Quality Score for comparing similar data sets. > 0.8 Excellent, > 0.6 Good, > 0.5 Acceptable, > 0.4 Marginal, > 0.3 Barely usable
[b] NOTE: Automatic Space group selection is unreliable for incomplete data. See detailed results below.
[c] Resolution selected based on I/sigma(I) > 1 cut-off. Value in parenthesis based on R-mergd-F < 40% cut-off.
[d] Average I/sigma(I) for all data.
[e] Redundancy independent R-factor. Diederichs & Karplus (1997), Nature Struct. Biol. 4, 269-275.
[f] Quality of amplitudes. see Diederichs & Karplus (1997), Nature Struct. Biol. 4, 269-275."""
        info['summary'] = _section
        
        info['details'] = {}
        for dataset_name in self.dataset_names:
            info['details'][dataset_name] = {}
            dset = self.results[dataset_name]
            # print out data collection parameters
            if dset.get('parameters', None) is not None:
                _section = {}
                _section['title'] = 'Data Collection and Processing Parameters'
                _section['table'] = []
                _keys = ['Description', 'Detector Distance (mm)','Exposure Time (sec)', 'No. Frames', 'Starting Angle (deg)',
                         'Delta (deg)', 'Two Theta (deg)', 'Detector Origin (pix)', 'Detector Size (pix)',
                         'Pixel Size (um)', 'File Template','Data Directory', 'Output Directory', 'Output Files']
                _rows = ['Parameters', dset['parameters']['distance'],
                        dset['parameters']['exposure_time'],
                        dset['parameters']['frame_count'],
                        dset['parameters']['starting_angle'],
                        dset['parameters']['oscillation_range'], 
                        dset['parameters']['two_theta'], 
                        '%0.0f x %0.0f' %  dset['parameters']['detector_origin'],
                        '%d x %d' %  dset['parameters']['detector_size'], 
                        '%0.5f x %0.5f' %  dset['parameters']['pixel_size'],
                         os.path.basename(dset['parameters']['file_template']),
                         os.path.dirname(dset['parameters']['file_template']),
                         dset['parameters']['working_directory'],
                         dset['files']['output']]
                _section['table'].append(zip(_keys, _rows))
                _section['notes'] = ''
                info['details'][dataset_name]['parameters'] = _section
            
            # Print out strategy information
            if dset.get('strategy', None) and dset['strategy'].get('runs', None) is not None:
                _strategy = {}
                _strategy['summary'] = {}
                _strategy['summary']['title'] = 'Recommended Strategy for %s Data Collection' % adj
                _strategy['summary']['table'] = []
                _strategy_keys = ['Attenuation', 'Distance (mm)',    'Start Angle',
                      'Delta (deg)', 'No. Frames', 'Total Angle (deg)', 'Exposure Time (s) [a]',
                      'Overlaps?', '-- Expected Quality --', 'Resolution',
                      'Completeness', 'Multiplicity',
                      'I/sigma(I) [b]', 'R-factor [b]' ]
                for run in dset['strategy']['runs']:
                    _name = run['name']
                    if run['number'] == 1:
                        _res = '%0.2f [c]' % (dset['strategy']['resolution'],)
                        _cmpl = '%0.1f%%' % (dset['strategy']['completeness'],)
                        _mlt = '%0.1f' % (dset['strategy']['redundancy'],)
                        _i_sigma = '%0.1f (%0.1f)' % (dset['strategy']['prediction_all']['average_i_over_sigma'],
                                                      dset['strategy']['prediction_hi']['average_i_over_sigma'])
                        _r_fac = '%0.1f%% (%0.1f%%)' % (dset['strategy']['prediction_all']['R_factor'],
                                                    dset['strategy']['prediction_hi']['R_factor'])
                    else:
                        _res = _cmpl = _mlt = _i_sigma = _r_fac = '<--'
                        

                    _strategy_vals = [_name, '%0.0f%%' % (dset['strategy']['attenuation'],), 
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
                
                run = utils.get_xplan_strategy(dset)
                if run:
                    _strategy_vals = ['Alternate [d]', 'N/C', 
                      '', 
                      '%0.1f' % (run['start_angle'],),
                      '%0.2f' % (run['delta_angle'],), 
                      '%0.0f' % (run['number_of_images'],), 
                      '%0.2f' % (run['total_angle'],), 
                      '',
                      '', '-------------',
                      run['resolution'], run['completeness'], 
                      run['multiplicity'], 'N/C', 'N/C',                      
                      ]
                        
                    _strategy['summary']['table'].append(zip(_strategy_keys, _strategy_vals))
                _strategy['summary']['notes'] = """[a] NOTE: Recommended exposure time does not take into account overloads at low resolution!
[b] Values in parenthesis represent the high resolution shell.
[c] %s
[d] Strategy Calculated according to XDS and XPLAN.  Determined from the following tables."""  %  dset['strategy']['resolution_reasoning']
                
                _section = {}
                _section['title'] = 'Alternate Optimal Selection of Collection Range'
                _section['table'] = []
                for row in dset['strategy']['xplan']['summary']:
                    n_row = SortedDict()
                    for k,t in [('Start Angle','start_angle'),('Total Angle', 'total_angle'),('Completeness','completeness'), ('Multiplicity','multiplicity') ]:
                        n_row[k] = row[t]
                    _section['table'].append(n_row.items())
                _section['notes'] = ''
                _strategy['oscillation'] = _section
                
                _section = {}
                _section['title'] = 'Maximum Delta Angle to Prevent Angular Overlap'
                _section['table'] = []
                for row in dset['indexing']['oscillation_ranges']:
                    n_row = SortedDict()                
                    for k,t in [('High Resolution Limit','resolution'),('Max. Angle Delta [a]', 'angle')]:
                        n_row[k] = row[t]
                    _section['table'].append(n_row.items())
                _section['notes'] ='[a] NOTE: Assumes a mosaicity of zero!'
                _strategy['overlap'] = _section
                info['details'][dataset_name]['strategy'] = _strategy
             
            _section = {}
            _section['lattices'] = {}
            _section['lattices']['title'] = 'Compatible Lattice Character and Bravais Lattices'
            _section['lattices']['table'] = []
            _sec_keys = ['No.', 'Character', 'Cell Parameters', 'Quality', 'Cell Volume', 'Reindexing Matrix']
            for l in dset['correction']['symmetry']['lattices']:
                id, lat_type = l['id']
                sg = utils.POINT_GROUPS[ lat_type ][0]
                sg_name = utils.SPACE_GROUP_NAMES[ sg ]
                row = [id, 
                    '%6s %3d %2s' % (sg_name, sg, lat_type), 
                    '%5.1f %5.1f %5.1f %5.1f %5.1f %5.1f' % utils.tidy_cell(l['unit_cell'], lat_type),
                    l['quality'], utils.cell_volume( l['unit_cell'] ),
                    '%2d %2d %2d %2d %2d %2d %2d %2d %2d %2d %2d %2d' % l['reindex_matrix'] ]
                _section['lattices']['table'].append(zip(_sec_keys, row))
            
            _section['space_groups'] = {}
            _section['space_groups']['title'] = 'Likely Space Groups and their probabilities'
            _section['space_groups']['table'] = []
            _sec_keys = ['Space Group','No.', 'Probability']
            sg_num = dset['correction']['symmetry']['space_group']['sg_number']
            sg_name = utils.SPACE_GROUP_NAMES[ sg_num ]
            for i, sol in enumerate(dset['space_group']['candidates']):
                if sg_num == sol['number'] and i== 0:
                    sg_name = '* %s' % (utils.SPACE_GROUP_NAMES[ sol['number'] ])
                else:
                    sg_name = '  %s' % (utils.SPACE_GROUP_NAMES[ sol['number'] ])
                row = [ sg_name,   sol['number'],    sol['probability']]
                _section['space_groups']['table'].append(zip(_sec_keys, row)) 
            u_cell = utils.tidy_cell(dset['space_group']['unit_cell'], dset['space_group']['character'])
            _section['space_groups']['notes'] = "[*] Selected:  %s,  #%s. " % ( 
                sg_name, dset['space_group']['sg_number'] )
            _section['space_groups']['notes'] += " Unit Cell: %5.1f %5.1f %5.1f %5.1f %5.1f %5.1f." % u_cell 
            _section['space_groups']['notes'] += " NOTE: Detailed statistics reported below use this selection. "    
            if dset['space_group']['type'] == 'PointGroup':
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
            for row in dset['integration']['scale_factors']:
                n_row = SortedDict()
                for k,t in _keymap:
                    n_row[k] = row[t]
                _section['plot'].append(n_row.items())
            _section['plot_axes'] = [('Frame No.',['Scale Factor']), ('Frame No.', ['Mosaicity']),('Frame No.',['Divergence'])]   
            info['details'][dataset_name]['integration'] = _section

            # Print out correction results
            _section = {}
            _section['title'] = "Correction Statistics"
            if dset.get('scaling', None) is not None:
                _data_key = 'table'
            else:
                _data_key = 'table+plot'
                _section['plot_axes'] = [('Resolution',['R_meas', 'R_mrgd-F', 'Completeness']),('Resolution', ['I/Sigma'])]
                if dset['parameters']['anomalous'] == True:
                      _section['plot_axes'].append(('Resolution', ['SigAno']))
            _section[_data_key] = []
            for row in dset['correction']['statistics']:
                n_row = SortedDict()
                for k,t in [('Resolution','shell'),('Completeness', 'completeness'),('R_meas','r_meas'), ('R_mrgd-F','r_mrgdf'), ('I/Sigma','i_sigma'), ('SigAno','sig_ano'), ('AnoCorr','cor_ano')]:
                    n_row[k] = row[t]
                _section[_data_key].append(n_row.items())
            resol = dset['correction']['resolution']
            _section['notes'] = "Preliminary resolution cut-off (I/SigI>1.0):  %5.2f" % (resol[0])        
            info['details'][dataset_name]['correction'] = _section
            
            # Print out scaling results
            if dset.get('scaling', None) is not None:
                _section = {}
                _section['title'] = "Scaling Statistics"
                pt = PrettyTable()
                _data_key = 'table+plot' 
                _section[_data_key] = []
                for row in dset['scaling']['statistics']:
                    n_row = SortedDict()
                    for k,t in [('Resolution','shell'),('Completeness', 'completeness'),('R_meas','r_meas'), ('R_mrgd-F','r_mrgdf'), ('I/Sigma','i_sigma'), ('SigAno','sig_ano'), ('AnoCorr','cor_ano')]:
                        n_row[k] = row[t]
                    _section[_data_key].append(n_row.items())
                    
                _section['plot_axes'] = [('Resolution',['R_meas', 'R_mrgd-F', 'Completeness']),('Resolution', ['I/Sigma'])]
                if self.options.get('anomalous', False):
                      _section['plot_axes'].append(('Resolution', ['SigAno']))
                info['details'][dataset_name]['scaling'] = _section   

        return info

    def save_xml(self, info=None, filename='debug.xml'):
        os.chdir(self.top_directory)
        fh = open(filename, 'w')
        if info is None:
            info = self.results
        pickle.dump(info, fh)
        fh.close()

    def find_spots(self, run_info):
        os.chdir(run_info['working_directory'])
        _logger.info('Finding strong spots ...')
        jobs = 'COLSPOT'
        io.write_xds_input(jobs, run_info)
        utils.execute_xds_par()
        if utils.check_spots():
            return {'success':True}
        else:
            return {'success':False, 'reason': 'Could not find spots.'}
        
    def initialize(self, run_info):
        os.chdir(run_info['working_directory'])
        _logger.info('Initializing ...')
        jobs = 'XYCORR INIT'
        io.write_xds_input(jobs, run_info)
        utils.execute_xds_par()
        if utils.check_init():
            _out = self.find_spots(run_info)
            return _out   
        else:
            return {'success':False, 'reason': 'Could not create correction tables'}
        
    def auto_index(self, run_info):
        os.chdir(run_info['working_directory'])
        _logger.info('Auto-indexing ...')
        jobs = 'IDXREF'
        io.write_xds_input(jobs, run_info)
        utils.execute_xds_par()
        info = xds.parse_idxref()
        data = utils.diagnose_index(info)
        _retries = 0
        sigma = 3
        sepmin, clustrad = 6, 3
        spot_size = 6
        _all_images = False
        _aliens_tried = False
        _sigma_tried = False
          
        while info.get('failure_code') > 0 and _retries < 8:
            _logger.warning(':-( %s' % info.get('failure'))
            _logger.debug('Indexing Quality [%04d]' % (data['quality_code']))
            #_logger.debug(utils.print_table(data))
            if run_info['spot_range'][0] == run_info['data_range']:
                _all_images = True
            else:
                _all_images = False
            _retries += 1
            utils.backup_file('IDXREF.LP')
            utils.backup_file('SPOT.XDS')

            if info.get('failure_code') == xds.POOR_SOLUTION:
                if not _aliens_tried:
                    _logger.info('Removing alien spots ...')
                    spot_list = utils.load_spots()
                    spot_list = utils.filter_spots(spot_list, unindexed=True)
                    utils.save_spots(spot_list)
                    io.write_xds_input(jobs, run_info)
                    utils.execute_xds_par()
                    info = xds.parse_idxref()
                    data = utils.diagnose_index(info)
                    _aliens_tried = True
                elif sigma < 48:
                    sigma *= 2
                    _logger.info('Removing weak spots (Sigma < %2.0f) ...' % sigma)
                    spot_list = utils.load_spots()
                    spot_list = utils.filter_spots(spot_list, sigma=sigma)
                    utils.save_spots(spot_list)
                    io.write_xds_input(jobs, run_info)
                    utils.execute_xds_par()
                    info = xds.parse_idxref()
                    data = utils.diagnose_index(info)
                else:
                    _logger.critical(':-( Unable to proceed!')
                    _retries = 999
            elif info.get('failure_code') == xds.INSUFFICIENT_INDEXED_SPOTS:
                if data['distinct_subtrees'] >= 1:
                    _logger.info('Removing alien spots ...')
                    spot_list = utils.load_spots()
                    spot_list = utils.filter_spots(spot_list, unindexed=True)
                    utils.save_spots(spot_list)
                    io.write_xds_input(jobs, run_info)
                    utils.execute_xds_par()
                    info = xds.parse_idxref()
                    data = utils.diagnose_index(info)
                elif sigma < 48 and data['index_origin_delta'] <= 6:
                    sigma *= 2
                    _logger.info('Removing weak spots (Sigma < %2.0f) ...' % sigma)
                    spot_list = utils.load_spots()
                    spot_list = utils.filter_spots(spot_list, sigma=sigma)
                    utils.save_spots(spot_list)
                    io.write_xds_input(jobs, run_info)
                    utils.execute_xds_par()
                    info = xds.parse_idxref()
                    data = utils.diagnose_index(info)
                elif data['index_origin_delta'] > 6:
                    run_info['detector_origin'] = data['new_origin']
                    _logger.info('Adjusting beam origin to (%0.0f %0.0f)...'% run_info['detector_origin'])
                    io.write_xds_input(jobs, run_info)
                    utils.execute_xds_par()
                    info = xds.parse_idxref()
                    data = utils.diagnose_index(info)
                elif not _aliens_tried:
                    spot_list = utils.load_spots()
                    spot_list = utils.filter_spots(spot_list, unindexed=True)
                    utils.save_spots(spot_list)
                    io.write_xds_input(jobs, run_info)
                    utils.execute_xds_par()
                    info = xds.parse_idxref()
                    data = utils.diagnose_index(info)
                    _aliens_tried = True                    
                else:
                    _logger.critical(':-( Unable to proceed!')
                    _retries = 999
            elif info.get('failure_code') == xds.INSUFFICIENT_SPOTS or info.get('failure_code') == xds.SPOT_LIST_NOT_3D:
                if not _all_images:
                    run_info['spot_range'] = [run_info['data_range']]
                    _logger.info('Increasing spot search range to [%d..%d] ...' % tuple(run_info['spot_range'][0]))
                    io.write_xds_input('COLSPOT IDXREF', run_info)
                    utils.execute_xds_par()
                    info = xds.parse_idxref()
                    data = utils.diagnose_index(info)
                elif sigma > 3:
                    sigma /= 2
                    _logger.info('Including weaker spots (Sigma > %2.0f) ...' % sigma)
                    io.write_xds_input('COLSPOT IDXREF', run_info)
                    utils.execute_xds_par()
                    info = xds.parse_idxref()
                    data = utils.diagnose_index(info)
                else:
                    _logger.critical(':-( Unable to proceed!')
                    _retries = 999   
            elif utils.match_code(data['quality_code'], 512) :
                _logger.info('Adjusting spot parameters ...')
                spot_size *= 1.5
                #sepmin *= 1.5
                #clustrad *= 1.5
                new_params = {'min_spot_size':spot_size}
                run_info.update(new_params)
                io.write_xds_input('COLSPOT IDXREF', run_info)
                utils.execute_xds_par()
                info = xds.parse_idxref()
                data = utils.diagnose_index(info)                    
            else:
                _logger.critical(':-( Unable to proceed!')
                _retries = 999

        if info.get('failure_code') == 0:
            _logger.info(':-) Auto-indexing succeeded.')
            #_logger.debug(utils.print_table(data))
            _logger.debug('Indexing Quality [%04d]' % (data['quality_code']))
            return {'success':True, 'data': info}
        else:
            return {'success':False, 'reason': info['failure']}
    
    def integrate(self, run_info):
        os.chdir(run_info['working_directory'])
        _logger.info('Integrating ...')
        jobs = "DEFPIX INTEGRATE"
        io.write_xds_input(jobs, run_info)
        _pc = ProgChecker(self.cpu_count)
        _pd = ProgDisplay(run_info['data_range'], _pc.queue)
        _pd.start()
        _pc.start()
        utils.execute_xds_par()
        _pd.stop()
        _pc.stop()
        
        info = xds.parse_integrate()
        
        if info.get('failure') is None:
            #_logger.info(':-) Integration succeeded.')
            return {'success':True, 'data': info}
        else:
            return {'success':False, 'reason': info['failure']}
    
    def correct(self, run_info):
        os.chdir(run_info['working_directory'])
        _logger.info('Correcting ...')
        jobs = "CORRECT"
        io.write_xds_input(jobs, run_info)
        utils.execute_xds_par()
        info = xds.parse_correct()
        if info.get('statistics') is not None:
            if len(info['statistics']) > 1 and info.get('summary') is not None:
                info['summary'].update( info['statistics'][-1] )
                del info['summary']['shell']
        
        if info.get('failure') is None:
            return {'success':True, 'data': info}
        else:
            return {'success':False, 'reason': info['failure']}

    def determine_spacegroup(self, run_info):
        os.chdir(run_info['working_directory'])
        _logger.info("Determining SpaceGroup...")
        success = utils.execute_pointless()
        if not success:
            success = utils.execute_pointless_retry()
        if not success:
            _logger.warning(':-( SpaceGroup determination failed!')
            return {'success':False, 'reason': 'POINTLESS FAILED!'}
        else:
            sg_info = parse_pointless('pointless.xml')
            return {'success':True, 'data': sg_info}        
    
    def scale_datasets(self):
        os.chdir(self.top_directory)
        _logger.info("Scaling ...")
        command = self.options.get('command', None)
        output_file_list = []
        if command == 'mad':
            sections = []
            _crystal_name = os.path.commonprefix(self.results.keys())
            for name, rres in self.results.items():
                resol = rres['correction']['resolution'][0]
                in_file = rres['files']['correct']
                out_file = os.path.join(name, "XSCALE.HKL")
                sections.append(
                    {'anomalous': self.options.get('anomalous', True),
                     'output_file': out_file,
                     'crystal': _crystal_name,
                     'inputs': [{'input_file': in_file, 'resolution': resol}],
                    }
                    )
                output_file_list.append(out_file)
                rres['files']['xscale'] = [out_file]
        else:
            inputs = []
            for name, rres in self.results.items():
                if command == "screen":
                    resol = 0.0
                else:
                    resol = rres['correction']['resolution'][0]
                in_file = rres['files']['correct']
                inputs.append( {'input_file': in_file, 'resolution': resol} )
            sections = [
                    {'anomalous': self.options.get('anomalous', False),
                     'output_file': "XSCALE.HKL",
                     'inputs': inputs,
                    }
                    ]
            output_file_list.append("XSCALE.HKL")
            rres['files']['xscale'] = output_file_list
    
        xscale_options = {
            'cpu_count': self.cpu_count,
            'sections': sections
            }
        
        io.write_xscale_input(xscale_options)
        success = utils.execute_xscale()
        raw_info = xds.parse_xscale('XSCALE.LP')
        
        if len(raw_info.keys()) == 1:
            info = raw_info.values()[0]
            # Select resolution
            resol = utils.select_resolution(info['statistics'])
            info['resolution'] = resol
            self.results.values()[-1]['scaling'] =  info  
        else:
            for name, info in raw_info.items():
                # Select resolution
                resol = utils.select_resolution(info['statistics'])
                info['resolution'] = resol
                self.results[name]['scaling'] = info
        if not success:
            _logger.error(':-( Scaling failed!')
            return {'success': False, 'reason': None}
    
    def convert_files(self):
        os.chdir(self.top_directory)
        # GENERATE MTZ and CNS output files    
        _logger.info('Generating MTZ, SHELX and CNS files ...')
        for name, rres in self.results.items():
            out_files = []
            if rres['files'].get('xscale') is None: 
                continue
            for infile in rres['files']['xscale']:
                out_file_root = name

                # CNS File
                out_files.append(out_file_root + ".cns")
                xdsconv_options = {
                    'resolution': 0,
                    'unit_cell': rres['correction']['symmetry']['space_group']['unit_cell'],
                    'space_group': rres['correction']['symmetry']['space_group']['sg_number'],
                    'format': 'CNS',
                    'anomalous': self.options.get('anomalous', False),
                    'input_file': infile,
                    'output_file': out_file_root + ".cns",
                    'freeR_fraction': 0.05,
                }
                io.write_xdsconv_input(xdsconv_options)
                utils.execute_xdsconv()

                #SHELX File
                out_files.append(out_file_root + ".shelx")
                xdsconv_options = {
                    'resolution': 0,
                    'unit_cell': rres['correction']['symmetry']['space_group']['unit_cell'],
                    'space_group': rres['correction']['symmetry']['space_group']['sg_number'],
                    'format': 'SHELX',
                    'anomalous': self.options.get('anomalous', False),
                    'input_file': infile,
                    'output_file': out_file_root + ".shelx",
                    'freeR_fraction': 0.05,
                }
                io.write_xdsconv_input(xdsconv_options)
                utils.execute_xdsconv()

                #MTZ File
                out_files.append(out_file_root + ".mtz")
                xdsconv_options = {
                    'resolution': 0,
                    'unit_cell': rres['correction']['symmetry']['space_group']['unit_cell'],
                    'space_group': rres['correction']['symmetry']['space_group']['sg_number'],
                    'format': 'CCP4_F',
                    'anomalous': True,
                    'input_file': infile,
                    'output_file': out_file_root + ".ccp4f",
                    'freeR_fraction': 0.05,
                }
                io.write_xdsconv_input(xdsconv_options)
                utils.execute_xdsconv()
                
                f2mtz_options = {
                    'output_file': out_file_root + ".mtz"
                }
                io.write_f2mtz_input(f2mtz_options)
                utils.execute_f2mtz()
            
            _logger.info('Output Files: %s' % ( ', '.join(out_files)))
            rres['files']['output'] = out_files               

    def calc_strategy(self, run_info, resolution=1.0):
        os.chdir(run_info['working_directory'])
        utils.update_xparm()
        _logger.info('Calculating Strategy ...')
        jobs = "XPLAN"
        # use resolution from correction step since we haven't scaled yet
        _reso = resolution
        run_info['shells'] = utils.resolution_shells(_reso, 5)
        io.write_xds_input(jobs, run_info)
        success = utils.execute_xds_par()
        info_x = xds.parse_xplan()
        _logger.info('Calculating Alternate Strategy ...')
        success = utils.execute_best(run_info['exposure_time'], self.options.get('anomalous', False))
        info_b = parse_best('best.xml')
        info_b['xplan'] = info_x
        if not success:
            _logger.error(':-( Strategy failed!')
            return {'success': False, 'reason': None}
        else:
            return {'success': True, 'data': info_b}

    def get_fileinfo(self, run_info):
        if run_info['working_directory'] == self.top_directory:
            files = {
                'correct': 'XDS_ASCII.HKL',
                'integrate': 'INTEGRATE.HKL',
                }      
        else:
            try:
                # only available in python >= 2.6
                prefix = os.path.relpath(run_info['working_directory'], self.top_directory)
            except:
                prefix = run_info['dataset_name']
            files = {
                'correct': os.path.join(prefix, 'XDS_ASCII.HKL'),
                'integrate': os.path.join(prefix, 'INTEGRATE.HKL')
                }
        return files
    
    def score_datasets(self):
        for dataset_name, rres in self.results.items():
            mosaicity = rres['correction']['summary']['mosaicity']
            std_spot = rres['correction']['summary']['stdev_spot']
            std_spindle= rres['correction']['summary']['stdev_spindle']
            if rres.get('scaling') is not None:
                resolution = rres['scaling']['resolution'][1]
                i_sigma = rres['scaling']['summary']['i_sigma']
                r_meas = rres['scaling']['summary']['r_meas']
            else:
                resolution = rres['correction']['resolution'][1]
                i_sigma = rres['correction']['summary']['i_sigma']
                r_meas = rres['correction']['summary']['r_meas']          
            st_table = rres['indexing']['subtrees']            
            st_array = [i['population'] for i in st_table]
            subtree_skew = sum(st_array[1:]) / float(sum(st_array))
            if rres.get('image_analysis') is not None:
                ice_rings = rres['image_analysis']['summary']['ice_rings']
            else:
                ice_rings = 0
            score = utils.score_crystal(resolution, mosaicity, r_meas, i_sigma,
                                std_spot, std_spindle,
                                subtree_skew, ice_rings)
            _logger.info("Dataset '%s' Score: %0.2f" % (dataset_name, score))
            rres['crystal_score'] = score
                  
    def run(self):
        
        t1 = time.time()
        adj = 'NATIVE'
        if self.options.get('command',None) == 'screen':
            description = 'CHARACTERIZING'
        else:
            description = 'PROCESSING'
        if self.options.get('command',None) == 'mad':
            adj = 'MAD'
        elif self.options.get('anomalous', False):
            adj = 'ANOMALOUS'
        _ref_run = None
        _logger.info("Directory: '%s'" % self.top_directory)
        for run_name in self.dataset_names:
            run_info = self.dataset_info[run_name]
            if not os.path.isdir(run_info['working_directory']):
                os.mkdir(os.path.abspath(run_info['working_directory']))
            _logger.info("%s %s DATASET: '%s'" % (description, adj, run_name))
            #_logger.info("==> Output: '%s'." % run_info['working_directory'])
            run_result = {}
            run_result['parameters'] = run_info
            
            # Initializing
            _out = self.initialize(run_info)
            if not _out['success']:
                _logger.error('Initialization failed! %s' % _out.get('reason'))
                sys.exit(1)
            
            # Auto Indexing
            _out = self.auto_index(run_info)
            if not _out['success']:
                _logger.error('Auto-indexing failed! %s' % _out.get('reason'))
                sys.exit(1)
            run_result['indexing'] = _out.get('data')
            
            #Integration
            _out = self.integrate(run_info)
            if not _out['success']:
                _logger.error('Integration failed! %s' % _out.get('reason'))
                sys.exit(1)
            run_result['integration'] = _out.get('data')

            #initial correction
            if _ref_run is not None:
                run_info['reference_data'] = os.path.join('..', self.results[_ref_run]['files']['correct'])
            _out = self.correct(run_info)
            if not _out['success']:
                _logger.error('Correction failed! %s' % _out.get('reason'))
                sys.exit(1)
            run_result['correction'] = _out.get('data')
            _sel_pgn = _out['data']['symmetry']['space_group']['sg_number']
            _logger.info('Suggested PointGroup: %s (#%d)' % (utils.SPACE_GROUP_NAMES[_sel_pgn], _sel_pgn))
            
            #space group determination
            _out = self.determine_spacegroup(run_info)
            _sel_sgn = _sel_pgn
            if _out['success']:
                sg_info = _out.get('data')
                _sel_sgn = sg_info['sg_number']
                run_result['space_group'] = sg_info                   
                run_info['unit_cell'] = utils.tidy_cell(sg_info['unit_cell'], sg_info['character'])
                run_info['space_group'] = _sel_sgn
                if _ref_run is None:
                    run_info['reindex_matrix'] = sg_info['reindex_matrix']
                _logger.info('Selected %s: %s (#%d)' % (sg_info['type'], utils.SPACE_GROUP_NAMES[_sel_sgn], _sel_sgn))
                if _ref_run is not None:
                    _ref_sgn = self.results[_ref_run]['space_group']['sg_number']
                    _ref_type = self.results[_ref_run]['space_group']['type']
                    if _sel_sgn != _ref_sgn:
                        _logger.warning('WARNING: SpaceGroup differs from reference data set!')                           
                        _logger.info('Proceeding with %s: %s (#%d) instead.' % (_ref_type, utils.SPACE_GROUP_NAMES[_ref_sgn], _ref_sgn))
                        _ref_sginfo = self.results[_ref_run]['space_group']
                        run_info['unit_cell'] = utils.tidy_cell(_ref_sginfo['unit_cell'], _ref_sginfo['character'])
                        run_info['space_group'] = _ref_sgn
            else:
                run_result['space_group'] = run_result['correction']['symmetry']['space_group']
                _logger.info('Proceeding with PointGroup: %s (#%d)' % (utils.SPACE_GROUP_NAMES[_sel_pgn], _sel_pgn))
                
            # Final correction
            utils.backup_file('CORRECT.LP')
            utils.backup_file('XDS_ASCII.HKL')
            _out = self.correct(run_info)
            if not _out['success']:
                _logger.error('Correction failed! %s' % _out.get('reason'))
            else:
                run_result['correction'] = _out.get('data')

            # Select Cut-off resolution
            resol = utils.select_resolution( run_result['correction']['statistics'])
            run_result['correction']['resolution'] = resol
                           
            run_result['files'] = self.get_fileinfo(run_info)
            run_result['files']['output'] = None
            if _ref_run is None:
                _ref_run = run_name
            self.results[run_name] = run_result             
        
        # Scale datasets
        self.scale_datasets()

        # Calculate Strategy if screening
        for name, run_info in self.dataset_info.items():
            if self.options.get('command', None) == 'screen':
                _out = self.calc_strategy(run_info, self.results[name]['scaling']['resolution'][0])
                if not _out['success']:
                    _logger.error('Strategy failed! %s' % _out.get('reason'))
                else:
                    self.results[name]['strategy'] = _out.get('data')
                success = utils.execute_distl(run_info['reference_image'])
                if success:
                    info = parse_distl('distl.log')
                    self.results[name]['image_analysis'] = info
                else:
                    _logger.error(':-( Image analysis failed!')                                                           
        
        # Score dataset
        self.score_datasets()
        
        if self.options.get('command', None) != 'screen':       
            self.convert_files()
                      
        self.save_xml(self.results, 'debug.xml')
        self.save_xml(self.get_log_dict(), 'process.xml')
        self.save_log('process.log')

        elapsed = time.time() - t1
        total_frames = 0
        for info in self.dataset_info.values():
            total_frames += info['data_range'][1]-info['data_range'][0]
        frame_rate = total_frames/elapsed
        used_time = time.strftime('%H:%M:%S', time.gmtime(elapsed))
        _logger.info("Done in: %s [ %0.1f frames/sec ]"  % (used_time, frame_rate))             
