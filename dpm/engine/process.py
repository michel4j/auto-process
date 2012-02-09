
import os
import sys
import time

import dpm.errors
from dpm.utils.misc import json
from dpm.utils import odict, dataset, misc, log, xtal
from dpm.engine import indexing, spots, integration, scaling
from dpm.engine import reporting, symmetry, strategy, conversion


_logger = log.get_module_logger(__name__)

_version_file = os.path.join(os.path.dirname(__file__), '..', 'VERSION')
if os.path.exists(_version_file):
    VERSION = (file(_version_file).readline()).strip()
else:
    VERSION = '3.0 Dev'

_MAX_RMEAS_FACTOR = 2

_STEP_FUNCTIONS = {
    'initialize': spots.initialize,
    'image_analysis': spots.analyse_image,
    'spot_search': spots.find_spots,
    'indexing': indexing.auto_index,
    'integration': integration.integrate,
    'symmetry': symmetry.determine_sg,
    'data_quality': scaling.data_quality,
    'correction': integration.correct,
    'scaling': scaling.scale_datasets,
    'strategy': strategy.calc_strategy,
}

class DataSet(object):
    def __init__(self, filename=None, info=None, overwrites={}):
        if filename is not None:
            self.parameters = dataset.get_parameters(filename)
            self.parameters.update(overwrites) # overwrite parameters
            self.log = []
            self.results = {}
        elif info is not None:
            self.set_info(info)
            self.parameters.update(overwrites) # overwrite parameters
        else:
            raise dpm.errors.DatasetError('Filename/parameters not specified')
        self.name = self.parameters['name']
    
    def __str__(self):
        return "<DataSet: %s, %s, first=%d, n=%d>" % (self.name, self.parameters['file_template'],
                                             self.parameters['first_frame'], 
                                             self.parameters['frame_count'])
    
    def get_info(self):
        """
        Return a dictionary representing all the information content of the 
        dataset object. The dictionary can be used in the future to recreate
        an identical dataset object
        
        """
        
        info = {'parameters': self.parameters,
                'log': self.log,
                'results': self.results,
                
                }
        return info
    
    def set_info(self, info):
        """
        Restore the state of the dataset object to the content of the
        info dictionary. 
        
        """
        
        self.parameters = info.get('parameters')
        self.log = info.get('log', [])
        self.results = info.get('results',{})            

    def score(self, strategy=False, scaled=False):
        
        if scaled:
            _summary = self.results['scaling']['summary']
        else:
            _summary = self.results['correction']['summary']
            
        mosaicity = self.results['correction']['summary']['mosaicity']
        std_spot = self.results['correction']['summary']['stdev_spot']
        std_spindle= self.results['correction']['summary']['stdev_spindle']
        resolution = _summary['resolution'][0]
        i_sigma = _summary['i_sigma']
        r_meas = _summary['r_meas']
        
        if scaled:
            completeness = self.results['data_quality']['sf_check']['data_compl']
        else:         
            completeness = self.results['correction']['summary']['completeness']

        if self.results.get('image_analysis') is not None:
            ice_rings = self.results['image_analysis'].get('summary', {}).get('ice_rings', 0)
        else:
            ice_rings = 0
            
        #use predicted values for resolution, r_meas, i_sigma if we are screening
        if strategy:
            resolution = self.results['strategy']['resolution']
            if self.results['strategy'].get('prediction_all') is not None:
                r_meas = self.results['strategy']['prediction_all']['R_factor']
                i_sigma = self.results['strategy']['prediction_all']['average_i_over_sigma']
                completeness = self.results['strategy']['prediction_all']['completeness']*100.0
            
        score = xtal.score_crystal(resolution, 
                                   completeness,
                                   r_meas, i_sigma,
                                   mosaicity, 
                                   std_spot, std_spindle,
                                   ice_rings)
        self.results['crystal_score'] = score
        return score

    
class Manager(object):
    def __init__(self, options=None, checkpoint=None, overwrites={}):
        
        self.datasets = odict.SortedDict()  
        
        if checkpoint is not None:
            self.run_position = checkpoint['run_position']
            self.options = checkpoint['options']
            self.options['command_dir'] = os.getcwd()

            for dset_info in checkpoint['datasets']:
                dset = DataSet(info=dset_info, overwrites=overwrites)
                self.datasets[dset.name] = dset
        elif options is not None:   
            self.run_position = (0, 'initialize')
            self.options = options
            self.options['command_dir'] = os.getcwd()
    
            for img in options.get('images', []):
                dset = DataSet(filename=img, overwrites=overwrites)
                self.datasets[dset.name] = dset
            # prepare directories
            if self.options.get('directory', None) is None:
                if self.options.get('mode', 'simple') == 'screen':
                    _suffix = 'scrn'
                else: 
                    _suffix = 'proc'
                _prefix = os.path.commonprefix(self.datasets.keys())
                if _prefix == '':
                    _prefix = '_'.join(self.datasets.keys())
                elif _prefix[-1] == '_':
                    _prefix = _prefix[:-1]
                    
                self.options['directory'] = os.path.join(self.options['command_dir'], '%s-%s' % (_prefix, _suffix))
            self.setup_directories()
        else:
            raise dpm.errors.DatasetError('Options/Checkpoint file not specified')
        
            

        
    def setup_directories(self):
        """
        Creates the top-level working directory if it doesn't exist. Renames 
        existing directories for backup if the backup option is specified.
        
        Also creates per-dataset working directories underneath the top-level
        one if multiple datasets are being processed.
        
        """
        
        # prepare top level working directory
        if not os.path.isdir(self.options['directory']) or self.options.get('backup', False):
            try:
                misc.prepare_dir(self.options['directory'], self.options.get('backup', False))
            except:
                _logger.error("Could not prepare working directory '%s'." % self.options['directory'])                  
                raise dpm.errors.FilesystemError('Could not prepare working directory')
        
        # for multiple data sets, process each in a separate sub-directory
        _multi = (len(self.datasets.keys()) > 1)
        for dset in self.datasets.values():
            if _multi:
                dset.parameters['working_directory'] = os.path.join(self.options['directory'], dset.name)
                misc.prepare_dir(dset.parameters['working_directory'])
            else:   
                dset.parameters['working_directory'] = self.options['directory']
        
    def save_checkpoint(self):
        """
        Save a checkpoint file to use for resuming or repeating auto-processing
        steps.
        
        """
        
        info = {'options': self.options,
                'run_position': self.run_position,
                'datasets': [d.get_info() for d in self.datasets.values()]}
        
        # Checkpoint file is saved in top-level processing directory
        fname = os.path.join(self.options['directory'], 'checkpoint.json')
        fh = open(fname, 'w')
        json.dump(info, fh)
        fh.close()

    def run_step(self, step, dset, overwrite={}, optional=False):
        """
        Runs the specified step with optional overwritten parameters
        and record the results in the dataset object.
        
        Will exit the program if a non optional step fails.
        
        """
        step_parameters = {}
        step_parameters.update(dset.parameters)
        step_parameters.update(overwrite)
        
        # symmetry needs an extra parameter
        if step == 'symmetry':
            _out = _STEP_FUNCTIONS[step](step_parameters, dset, self.options)
        else:
            _out = _STEP_FUNCTIONS[step](step_parameters, self.options)

        dset.log.append((time.time(), _out['step'], _out['success'], _out.get('reason', None)))
        if _out.get('data') is not None:
            dset.results[step] = _out.get('data')
        self.save_checkpoint()

        if not _out['success']:
            if optional:
                _logger.warning('Failed (%s): %s' % (_out['step'], _out['reason']))
            else:
                _logger.error('Failed (%s): %s' % (_out['step'], _out['reason']))
                sys.exit(1)
                        
    
    def run(self, resume_from=None, single=False, overwrite={}):
        """
        resume_from is a tuple of the form
            (dataset_index, 'step')
        """
        
        self._start_time = time.time()
        run_steps = ['initialize', 'image_analysis', 'spot_search', 
                     'indexing', 'integration','correction', 'symmetry',
                     'strategy',
                     ]
        
        _logger.info('---- AutoProcess(%s) - %s [%d dataset(s)] ----' % (VERSION, 
                              self.options['mode'].upper(), len(self.datasets)))
        _num_cores = int(os.environ.get('DPM_CORES', misc.get_cpu_count))
        _env_hosts = os.environ.get('DPM_HOSTS', 'localhost')
        _num_nodes = len(_env_hosts.split(' '))

        _logger.debug('Computer system: %d cores in %d nodes' % (_num_cores, _num_nodes))
        _logger.debug('Computer nodes: "%s"' % _env_hosts )
        if resume_from is not None:
            cur_pos, next_step = resume_from
        else:
            cur_pos, next_step = (0, 'initialize')
        
        if next_step not in ['scaling', 'conversion', 'data_quality', 'reporting']:
            for i, dset in enumerate(self.datasets.values()):
                if i < cur_pos: continue  # skip all datasets earlier than specified one
                    
                _logger.info('Processing `%s` in directory "%s"' % (dset.name, 
                             misc.relpath(dset.parameters['working_directory'], self.options['command_dir'])))                
                for j, step in enumerate(run_steps):
                    self.run_position = (i, step)
                    
                    # skip this step based on the properties
                    if j < run_steps.index(next_step): continue
                    if self.options.get('mode') != 'screen' and step == 'strategy': continue
    
                    self.run_step(step, dset, overwrite=overwrite, optional=(step=='image_analysis'))
                    
                    # special post-step handling  for specific steps
                    if step == 'correction':
                        # update parameters with reference after correction
                        if i > 0 and self.options.get('mode', 'simple') in ['merge', 'mad']:
                            _ref_file = os.path.join('..', 
                                        self.datasets.values()[i-1].results['correction']['output_file'])
                            dset.parameters.update({'reference_data': _ref_file,
                                                    'reference_sginfo': self.datasets.values()[0].results['symmetry'],
                                                    })                            
                    elif step == 'symmetry':
                        # perform addition correction and check effect on 
                        # data quality
                        self.run_step('correction', dset, overwrite=overwrite)
                        min_rmeas = dset.results['correction']['summary']['min_rmeas']
                        low_rmeas = dset.results['correction']['statistics'][0]['r_meas']
                        #FIXME: min_rmeas is calculated to 5 A but low_r_meas is variable low resolution shell
                                                
                        if _MAX_RMEAS_FACTOR * min_rmeas < low_rmeas and min_rmeas > 0.0:
                            _logger.warning('Data quality degraded (%0.1f%%) due to merging!' % (100.0*low_rmeas/min_rmeas))
                            _logger.warning('Selected SpaceGroup is likely inaccurate!')
                            
                        if self.options.get('mode') == 'screen':
                            # calculate and report the angles of the spindle from
                            # the three axes
                            _logger.info('Optimizing offset of longest-cell axes from spindle')   
                            _dat = dset.results['correction']['parameters']
                            _output = misc.optimize_xtal_offset(_dat)
                            
                            _logger.info('... %s-AXIS [%5.1f A]  %5.1f deg offset' % (
                                            ['A','B','C'][_output['longest_axis']],
                                            _dat['unit_cell'][_output['longest_axis']], 
                                            _output['offset']))
                            _logger.info('... Best Offset = %5.1f deg' %(_output['best_offset']))
                            _logger.info('......   Kappa  = %5.1f deg' %(_output['kappa'])) 
                            _logger.info('......   Phi    = %5.1f deg' %(_output['phi']))
                        
                    
                        
            next_step = 'scaling'
        
        if next_step == 'scaling':
            self.run_position = (0, 'scaling')
            scaling_options = {}
            scaling_options.update(self.options)
            scaling_options.update(overwrite)
            _out= scaling.scale_datasets(self.datasets, scaling_options)
            self.save_checkpoint()

            if not _out['success']:
                _logger.error('Failed (%s): %s' % (_out['step'], _out['reason']))
                sys.exit()
        
        # Final steps run for all datasets       
        for i, dset in enumerate(self.datasets.values()):
            if i < cur_pos: continue  # skip all datasets earlier than specified one
            
            # Run Data Quality Step:
            self.run_position = (i, 'data_quality')
            if self.options['mode'] == 'merge' and i > 0:
                _out = scaling.data_quality(dset.results['correction']['output_file'], self.options)
            else:
                _out = scaling.data_quality(dset.results['scaling']['output_file'], self.options)
            dset.log.append((time.time(), _out['step'], _out['success'], _out.get('reason', None)))
            if not _out['success']:
                _logger.error('Failed (%s): %s' % ("data quality", _out['reason']))
                sys.exit()
            else:
                dset.results['data_quality'] = _out.get('data')
            self.save_checkpoint()
                       
            # Scoring and experiment setup check
            ISa =   dset.results['correction']['correction_factors']['parameters'][0].get('ISa', -1)
            _logger.info('(%s) Asymptotic I/Sigma(I): %0.1f' % (dset.name, ISa))
            _score = dset.score(strategy=(self.options.get('mode')=='screening'),
                                scaled=(self.options.get('mode')!='merge'))
            _logger.info('(%s) Dataset Score: %0.2f' % (dset.name, _score))

            # file format conversions
            self.run_position = (i, 'conversion')
            if self.options.get('mode') != 'screen':
                
                if self.options.get('mode') == 'merge' and i > 0: 
                    pass # do not convert 
                else:
                    _step_options = {}
                    _step_options.update(self.options)
                    if self.options['mode'] == 'merge':
                        _prefix = os.path.commonprefix(self.datasets.keys())
                        if _prefix == '':
                            _prefix = '_'.join(self.datasets.keys())                       
                        elif _prefix[-1] == '_':
                            _prefix = _prefix[:-1]
                        _step_options['file_root'] = _prefix
                    else:
                        _step_options['file_root'] = dset.name
                    
                    _out = conversion.convert_formats(dset, _step_options)
                    dset.log.append((time.time(), _out['step'], _out['success'], _out.get('reason', None)))
                    if not _out['success']:
                        dset.log.append((time.time(), _out['step'], _out['success'], _out.get('reason', None)))
                        _logger.error('Failed (%s): %s' % ("conversion", _out['reason']))
                    else:
                        dset.results['output_files'] = _out.get('data')
                        _logger.info('(%s): %s' % (dset.name, ', '.join(_out['data'])))
                self.save_checkpoint()

        # reporting
        self.run_position = (0, 'reporting')
        os.chdir(self.options['directory'])
        self.save_checkpoint()

        _logger.info('Saving summaries ... "process.log", "process.json"')
        log_data = reporting.get_log_data(self.datasets, self.options)
        reporting.save_log(log_data, 'process.log')     
        reports = reporting.get_reports(self.datasets, self.options)
        reporting.save_json(reports, 'process.json', self.options)
        _logger.info('Generating HTML reports ...')
        reporting.save_html(reports, self.options)      

        used_time = time.strftime('%H:%M:%S', time.gmtime(time.time() - self._start_time))
        _logger.info("Done in: %s"  % (used_time))
  
        
            
                
            
