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

        # prepare dataset info
        for i, img in enumerate(self.options['images']):
            run_info = utils.get_dataset_params(img, is_screening)
            run_info['cpu_count'] = self.cpu_count
            if self.options.get('prefix'):
                run_info['dataset_name'] = self.options['prefix'][i]
            self.dataset_info[run_info['dataset_name']] =  run_info
        
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
        os.chdir(self.top_directory)
        fh = open(filename, 'w')
        file_text = utils.text_heading('Data Processing Summary', level=1)
        
        pt = PrettyTable()
        pt.add_column('Statistic', [
                      'Score [a]', 'Wavelength (A)',    'Space Group [b]',
                      'Cell parameters (A)', '              (deg)', 
                      'Cell Volume (A^3)', 'Resolution (A)[c]', 'Total Reflections',
                      'Unique Reflections', 'Multiplicity', 'Completeness',
                      'Mosaicity', 'I/sigma(I) [d]', 'R-mrgd-F [e]',
                      'R-meas [f]', 'sigma(spot) (pix)', 'sigma(angle) (deg)','No. Ice rings',
                      ], 'l')
        
        for dataset_name, dset in self.results.items():
            if dset.get('image_analysis', None) is not None:
                _ice_rings = dset['image_analysis']['summary']['ice_rings']
            else:
                _ice_rings = 'N/C'
            pt.add_column(dataset_name, [
                '%0.2f' % (dset['crystal_score'],),
                '%7.4f' % (self.dataset_info[dataset_name]['wavelength'],),
                utils.SPACE_GROUP_NAMES[ dset['correction']['symmetry']['space_group']['sg_number'] ],
                '%5.1f %5.1f %5.1f' % dset['correction']['symmetry']['space_group']['unit_cell'][:3],
                '%5.1f %5.1f %5.1f' % dset['correction']['symmetry']['space_group']['unit_cell'][3:],
                '%0.0f' % (utils.cell_volume(dset['correction']['symmetry']['space_group']['unit_cell']),),
                '%0.2f (%0.2f)' % dset['scaling']['resolution'],
                dset['scaling']['summary']['observed'],
                dset['scaling']['summary']['unique'],
                '%0.1f' % (float(dset['scaling']['summary']['observed'])/dset['scaling']['summary']['unique'],),
                '%0.1f%%' % (dset['scaling']['summary']['completeness'],),
                '%0.2f' % (dset['correction']['summary']['mosaicity'],),
                '%0.1f' % (dset['scaling']['summary']['i_sigma'],),
                '%0.1f%%' % (dset['scaling']['summary']['r_mrgdf'],),
                '%0.1f%%' % (dset['scaling']['summary']['r_meas'],),
                '%0.1f' % (dset['correction']['summary']['stdev_spot'],),
                '%0.1f' % (dset['correction']['summary']['stdev_spindle'],),
                _ice_rings,
                        ],'r')
        file_text += pt.get_string()
        file_text += '\n[a] Data Quality Score for comparing similar data sets. > 0.8 Excellent, \n'
        file_text += '    > 0.6 Good, > 0.5 Acceptable, > 0.4 Marginal, > 0.3 Barely usable\n'
        file_text += '[b] NOTE: Automatic Space group selection is unreliable for incomplete\n'
        file_text += '    data. See detailed results below.\n'
        file_text += '[c] Resolution selected based on I/sigma(I) > 1 cut-off. Value in parenthesis,\n'
        file_text += '    based on R-mergd-F < 40% cut-off.\n'
        file_text += '[d] Average I/sigma(I) for all data in scaled output file\n'
        file_text += '[e] Redundancy independent R-factor.\n    Diederichs & Karplus (1997), Nature Struct. Biol. 4, 269-275.\n'
        file_text += '[f] Quality of amplitudes.\n    see Diederichs & Karplus (1997), Nature Struct. Biol. 4, 269-275.\n\n' 
        
        for dataset_name, dset in self.results.items():
            file_text += utils.text_heading("DETAILED RESULTS FOR DATASET: '%s'" % (dataset_name), level=2)
            # Print out strategy information  
            if dset.get('strategy', None) and dset['strategy'].get('runs', None) is not None:
                file_text  += utils.text_heading('Recommended Strategy for Data Collection', level=3)
                pt = PrettyTable()
                pt.add_column('Parameter', [
                      'Attenuation', 'Distance (mm)',    'Start Angle',
                      'Delta (deg)', 'No. Frames', 'Total Angle (deg)', 'Exposure Time (s) [b]',
                      'Overlaps?' ], 'l')
                
        
                for run in dset['strategy']['runs']:
                    pt.add_column('Run %d [a]' % (run['number'],), [
                      '%7.0f%%' % (dset['strategy']['attenuation'],), 
                      '%8.1f' % (run['distance'],), 
                      '%8.1f' % (run['phi_start'],),
                      '%8.2f' % (run['phi_width'],), 
                      '%8.0f' % (run['number_of_images'],), 
                      '%8.2f' % (run['phi_width'] * run['number_of_images'],), 
                      '%8.1f' % (run['exposure_time'],),
                      '%8s' % (run['overlaps'],)], 'r')
                
                file_text += pt.get_string()
                
                file_text += '\n[a] For this strategy, the expected data quality is as follows\n'
                file_text += '    %s: %8.2f\n' % ('Resolution', dset['strategy']['resolution'] )
                file_text += '    %s: %7.1f%%\n' % ('Completeness', dset['strategy']['completeness'])
                file_text += '    %s: %8.1f\n' % ('Redundancy', dset['strategy']['redundancy'])
                file_text += '    %s: %8.1f (%0.1f)\n' % (
                    'I/Sigma (hires)', 
                    dset['strategy']['prediction_all']['average_i_over_sigma'],
                    dset['strategy']['prediction_hi']['average_i_over_sigma'])
                file_text += '    %s: %7.1f%% (%0.1f%%)\n' % (
                    'R-factor (hires)', 
                    dset['strategy']['prediction_all']['R_factor'],
                    dset['strategy']['prediction_hi']['R_factor'])
                file_text += '[b] NOTE: Recommended exposure time does not take into \n'
                file_text += '    account overloads at low resolution!\n'
                
            file_text += utils.text_heading('Automatic Space Group Assignment', level=3)
            file_text += "\n%16s %10s %7s %35s %8s %s\n" % (
                'Lattice Type',
                'PointGroup',
                'Quality',
                '_______ Unit Cell Parameters ______',
                'Cell Vol',
                'Reindex',
                )
            for l in dset['correction']['symmetry']['lattices']:
                vol = utils.cell_volume( l['unit_cell'] )
                lat_type = l['id'][1]
                descr = "%s(%s)" % (utils.CRYSTAL_SYSTEMS[ lat_type[0] ], lat_type)
                sg = utils.POINT_GROUPS[ lat_type ][0]
                sg_name = utils.SPACE_GROUP_NAMES[ sg ]
                txt_subst = (descr, sg, sg_name, l['quality'])
                reindex = '%2d %2d %2d %2d %2d %2d %2d %2d %2d %2d %2d %2d' % l['reindex_matrix']
                txt_subst += utils.tidy_cell(l['unit_cell'], lat_type) + (vol, reindex)
                file_text += "%16s %3d %6s %7.1f %5.1f %5.1f %5.1f %5.1f %5.1f %5.1f %8d %s\n" % txt_subst
            
            file_text  += '--- Likely Space Groups ---\n'
            file_text += '%15s %4s %9s\n' % (
                'SpaceGroup',
                '(#)',
                'Probability',
                )
            for sol in dset['space_group']['candidates']:
                file_text += '%13s (%4d) %9.3f\n' % (
                    sol['name'],
                    sol['number'],
                    sol['probability']
                    )
            sg_name = utils.SPACE_GROUP_NAMES[ dset['space_group']['sg_number'] ]
            file_text += "\nSelected Group is:    %s,  #%s\n" % ( 
                sg_name, dset['space_group']['sg_number'] )
            u_cell = utils.tidy_cell(dset['space_group']['unit_cell'], dset['space_group']['character'])
            file_text += "\nUnit Cell:    %7.2f %7.2f %7.2f %7.2f %7.2f %7.2f\n" % u_cell
            
            if dset['space_group']['type'] == 'pointgroup':
                file_text += "Space Group selection ambiguous. Current selection is not final!\n"  
            
            # Print out integration results
            file_text += utils.text_heading("Integration and Correction Statistics", level=3)
            pt = PrettyTable()
            tbl = Table(dset['correction']['statistics'])
            pt.add_column('Resolution', tbl['shell'], 'r')
            pt.add_column('Completeness', tbl['completeness'], 'r')
            pt.add_column('R_meas', tbl['r_meas'], 'r')
            pt.add_column('R_mrg-F', tbl['r_mrgdf'], 'r')
            pt.add_column('I/Sigma', tbl['i_sigma'], 'r')
            pt.add_column('SigAno', tbl['sig_ano'], 'r')
            pt.add_column('AnoCorr', tbl['cor_ano'], 'r')
                        
            file_text += pt.get_string()
            resol = dset['correction']['resolution']
            file_text += "\nResolution cut-off from preliminary analysis (I/SigI>1.0):  %5.2f\n\n" % (resol[0])
            

            # Print out scaling results
            if dset.get('scaling', None):
                file_text += utils.text_heading("Scaling Statistics", level=3)
                pt = PrettyTable()
                tbl = Table(dset['scaling']['statistics'])
                pt.add_column('Resolution', tbl['shell'], 'r')
                pt.add_column('Completeness', tbl['completeness'], 'r')
                pt.add_column('R_meas', tbl['r_meas'], 'r')
                pt.add_column('R_mrg-F', tbl['r_mrgdf'], 'r')
                pt.add_column('I/Sigma', tbl['i_sigma'], 'r')
                pt.add_column('SigAno', tbl['sig_ano'], 'r')
                pt.add_column('AnoCorr', tbl['cor_ano'], 'r')
                        
                file_text += pt.get_string()
                    
        file_text += '\n\n'
        out_text = utils.add_margin(file_text, 1)
        fh.write(out_text)    
        fh.close()

    def save_xml(self, filename='process.xml'):
        os.chdir(self.top_directory)
        fh = open(filename, 'w')
        pickle.dump(self.results, fh)
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
            rres['files']['xdsconv'] = out_files               

    def calc_strategy(self,run_info):
        os.chdir(run_info['working_directory'])
        utils.update_xparm()
        _logger.info('Calculating Strategy ...')
        jobs = "XPLAN"
        _reso = 1.0 
        run_info['shells'] = utils.resolution_shells(_reso, 10)
        io.write_xds_input(jobs, run_info)
        success = utils.execute_xds_par()
        info_x = xds.parse_xplan()
        _logger.info('Calculating Strategy ...')
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
        for run_name, run_info in self.dataset_info.items():
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
                        run_info['unit_cell'] = self.results[_ref_run]['unit_cell']
                        run_info['space_group'] = _ref_sgn
            else:
                run_result['space_group'] = run_result['correction']['space_group']
                _logger.info('Proceeding with PointGroup: %s (#%d)' % (utils.SPACE_GROUP_NAMES[_sel_pgn], _sel_pgn))
                
            # Final correction
            _out = self.correct(run_info)
            if not _out['success']:
                _logger.error('Correction failed! %s' % _out.get('reason'))
            else:
                run_result['correction'] = _out.get('data')

            # Select Cut-off resolution
            resol = utils.select_resolution( run_result['correction']['statistics'])
            run_result['correction']['resolution'] = resol
            
            if self.options.get('command', None) == 'screen':
                _out = self.calc_strategy(run_info)
                if not _out['success']:
                    _logger.error('Strategy failed! %s' % _out.get('reason'))
                else:
                    run_result['strategy'] = _out.get('data')
                success = utils.execute_distl(run_info['reference_image'])
                if success:
                    info = parse_distl('distl.log')
                    run_result['image_analysis'] = info
                else:
                    _logger.error(':-) Image analysis failed!')
                                                            
            run_result['files'] = self.get_fileinfo(run_info)
            if _ref_run is None:
                _ref_run = run_name
            self.results[run_name] = run_result 
                           
        
        # Scale datasets
        self.scale_datasets()
        
        # Score dataset
        self.score_datasets()
        
        if self.options.get('command', None) != 'screen':       
            self.convert_files()
                      
        self.save_xml('process.xml')
        self.save_log('process.log')

        elapsed = time.time() - t1
        total_frames = 0
        for info in self.dataset_info.values():
            total_frames += info['data_range'][1]-info['data_range'][0]
        frame_rate = total_frames/elapsed
        used_time = time.strftime('%H:%M:%S', time.gmtime(elapsed))
        _logger.info("Done. Time used:  %s [ %0.1f frames/sec ]"  % (used_time, frame_rate))             
