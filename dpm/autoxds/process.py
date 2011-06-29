# -*- coding: utf-8 -*-
""" 
Data Processing Class

"""

import os
import sys
import time

from dpm.parser.pointless import parse_pointless
from dpm.parser.distl import parse_distl
from dpm.parser import xds
from dpm.parser.best import parse_best
from dpm.parser.ccp4 import parse_ctruncate
from dpm.utils.log import get_module_logger
from dpm.utils.progress import ProgDisplay, ProgChecker
from dpm.parser.utils import Table
from dpm.utils.odict import SortedDict
from dpm.utils import json
import utils, io



_logger = get_module_logger('AutoXDS')

AUTOXDS_SCREENING, AUTOXDS_PROCESSING = range(2)

class AutoXDS:

    def __init__(self, options):
        self.options = options
        self.results = {}
        is_screening = (self.options.get('mode', None) == 'screen')
        self.dataset_info = {}
        self.cpu_count = utils.get_cpu_count()
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
        if self.options.get('directory', None) is not None:
            self.top_directory = os.path.abspath(self.options.get('directory'))
            # Check that working directory exists
            if not ( os.path.isdir(self.top_directory ) and os.access( self.top_directory, os.W_OK) ):
                try:
                    os.mkdir(self.top_directory)
                except:
                    err_msg = "Directory '%s' does not exist, or is not writable." % self.top_directory
                    _logger.error(err_msg)                   
                    sys.exit()
        else:
            self.top_directory = utils.prepare_work_dir(os.getcwd(),
                            work_dir, backup=self.options.get('backup', False))
        
        # for multiple data sets, process each in a separate subdirectory
        if len(self.dataset_info.keys()) ==1:
            for run_info in self.dataset_info.values():
                run_info['working_directory'] = self.top_directory
        else:   
            for run_info in self.dataset_info.values():
                run_info['working_directory'] = os.path.join(self.top_directory,
                                                             run_info['dataset_name'])
        os.chdir(self.top_directory)
        

    
                
    def create_inputs(self, run_info):
        os.chdir(run_info['working_directory'])
        jobs = 'ALL ! XYCORR INIT COLSPOT IDXREF DEFPIX XPLAN INTEGRATE CORRECT'
        io.write_xds_input(jobs, run_info)
        
    
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
    

    def run(self):
        
        t1 = time.time()
        adj = 'NATIVE'
        if self.options.get('mode',None) == 'screen':
            description = 'CHARACTERIZING'
        else:
            description = 'PROCESSING'
        if self.options.get('mode',None) == 'mad':
            adj = 'MAD'
        elif self.options.get('anomalous', False):
            adj = 'ANOMALOUS'
        _ref_run = None

        for run_name in self.dataset_names:
            run_info = self.dataset_info[run_name]
            if not os.path.isdir(run_info['working_directory']):
                os.mkdir(os.path.abspath(run_info['working_directory']))
            #_logger.info("==> Output: '%s'." % run_info['working_directory'])
            run_result = {}
            run_result['parameters'] = run_info
            
            # Generate input files
            if self.options.get('inputs_only') is not None:
                _logger.info("Generating input files in: '%s'" % run_info['working_directory'])
                self.create_inputs(run_info)
                continue
            
            _logger.info("%s %s DATASET: '%s'" % (description, adj, run_name))
            _logger.info('Using %d CPUs.' % self.cpu_count)
            _logger.info("Directory: '%s'" % run_info['working_directory'])
            # Initializing
            _out = self.initialize(run_info)
            if not _out['success']:
                err_msg = 'Initialization failed! %s' % _out.get('reason')
                _logger.error(err_msg)
                sys.exit()
            
            # Image Analysis
            _logger.info('Analysing Reference Image ...')
            success = utils.execute_distl(run_info['reference_image'])
            if success:
                info = parse_distl('distl.log')
                run_result['image_analysis'] = info
            else:
                _logger.error(':-( Image analysis failed!')                                                           

            # Auto Indexing
            _out = self.auto_index(run_info)
            if not _out['success']:
                err_msg = 'Auto-indexing failed! %s' % _out.get('reason')
                _logger.error(err_msg)
                sys.exit()
            run_result['indexing'] = _out.get('data')
            
#            #Integration
#            if self.options.get('mode', None) == 'screen':
#                run_info['data_range'] = run_info['spot_range'][0]

            _out = self.integrate(run_info)
            if not _out['success']:
                err_msg = 'Integration failed! %s' % _out.get('reason')
                _logger.error(err_msg)
                sys.exit()
            run_result['integration'] = _out.get('data')

            #initial correction
            if _ref_run is not None:
                run_info['reference_data'] = os.path.join('..', self.results[_ref_run]['files']['correct'])
            _out = self.correct(run_info)
            if not _out['success']:
                err_msg = 'Correction failed! %s' % _out.get('reason')
                _logger.error(err_msg)
                sys.exit()
            run_result['correction'] = _out.get('data')
            _sel_pgn = _out['data']['symmetry']['space_group']['sg_number']
            _logger.info('Suggested PointGroup: %s (#%d)' % (utils.SPACE_GROUP_NAMES[_sel_pgn], _sel_pgn))
            
            #space group determination
            _out = self.determine_spacegroup(run_info)
            _sel_sgn = _sel_pgn
            if _out['success']:
                sg_info = _out.get('data')
                _sel_sgn = sg_info['sg_number']

                # Overwrite sg_info parameters with XDS friendly ones if present:
                # fetches xds reindex matrix and cell constants based on lattice,
                # character
                # FIXME: Check what happens when multiple entries of same character exists
                # currently picks one with best quality but is this necessarily the best one?
                for _lat in run_result['correction']['symmetry']['lattices']:
                    id, lat_type = _lat['id']
                    if sg_info['character'] == lat_type:
                        sg_info['reindex_matrix'] = _lat['reindex_matrix']
                        sg_info['unit_cell'] = _lat['unit_cell']
                        break
                
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
            # if only detector edge resolution is available, try using distl value
            if run_result.get('image_analysis') and resol[1] == 0:
                resol = (run_result['image_analysis']['summary']['resolution'], 3)
            run_result['correction']['resolution'] = resol
                           
            run_result['files'] = self.get_fileinfo(run_info)
            run_result['files']['output'] = None
            if _ref_run is None:
                _ref_run = run_name
            self.results[run_name] = run_result             
        
        # Do not proceed if only generating inputs
        if self.options.get('inputs_only') is not None:
            return 
        
        # Scale datasets
        self.scale_datasets()
        self.calc_statistics()
        
        # Calculate Strategy if screening
        for name, run_info in self.dataset_info.items():
            if self.options.get('mode', None) == 'screen':
                _out = self.calc_strategy(run_info, self.results[name]['scaling']['resolution'][0])
                if not _out['success']:
                    _logger.error('Strategy failed! %s' % _out.get('reason'))
                else:
                    self.results[name]['strategy'] = _out.get('data')
        
        # Score dataset
        self.score_datasets()
        
        if self.options.get('mode', None) != 'screen':       
            self.convert_files()
                      
        #self.save_xml(self.results, 'debug.xml')
        #self.save_xml(self.get_log_dict(), 'process.xml')
        self.save_log('process.log')
        self.export_json('process.json')

        elapsed = time.time() - t1
        total_frames = 0
        for info in self.dataset_info.values():
            total_frames += info['data_range'][1]-info['data_range'][0]
        frame_rate = total_frames/(time.time() - self._start_time)
        used_time = time.strftime('%H:%M:%S', time.gmtime(elapsed))
        _logger.info("Done in: %s [ %0.1f frames/sec ]"  % (used_time, frame_rate))
        
        return         
