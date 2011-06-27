
import os
import sys
import time
import dpm.errors
from dpm.utils.misc import json
from dpm.utils import odict, dataset, misc, log, xtal
from dpm.engine import indexing, spots, integration, scaling, symmetry, strategy, conversion


_logger = log.get_module_logger(__name__)

VERSION = 3.0

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

    def score(self, strategy=False):
        
        mosaicity = self.results['correction']['summary']['mosaicity']
        std_spot = self.results['correction']['summary']['stdev_spot']
        std_spindle= self.results['correction']['summary']['stdev_spindle']
        if self.results.get('scaling') is not None:
            resolution = self.results['scaling']['summary']['resolution'][0]
            i_sigma = self.results['scaling']['summary']['i_sigma']
            r_meas = self.results['scaling']['summary']['r_meas']
            completeness = self.results['scaling']['summary']['completeness']
        else:
            resolution = self.results['correction']['summary']['resolution'][0]
            i_sigma = self.results['correction']['summary']['i_sigma']
            r_meas = self.results['correction']['summary']['r_meas']          
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
        self.command_dir = os.getcwd()
        
        if checkpoint is not None:
            self.run_position = checkpoint['run_position']
            self.options = checkpoint['options']
            for dset_info in checkpoint['datasets']:
                dset = DataSet(info=dset_info, overwrites=overwrites)
                self.datasets[dset.name] = dset
        elif options is not None:   
            self.run_position = 0
            self.options = options      
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
                    
                self.options['directory'] = os.path.join(self.command_dir, '%s-%s' % (_prefix, _suffix))
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
        
        run_steps = ['initialize', 'image_analysis', 'spot_search', 
                     'indexing', 'integration','correction', 'symmetry',
                     'strategy',
                     ]
        
        _logger.info('AutoProcess(v%0.1f) - %s [%d dataset(s)]' % (VERSION, 
                              self.options['mode'].upper(), len(self.datasets)))
        if resume_from is not None:
            cur_pos, next_step = resume_from
        else:
            cur_pos, next_step = (0, 'initialize')
        
        if next_step not in ['scaling', 'conversion']:
            for i, dset in enumerate(self.datasets.values()):
                if i < cur_pos: continue  # skip all datasets earlier than specified one
                self.run_position = i 
                    
                _logger.info('Processing `%s` in %s' % (dset.name, 
                             misc.relpath(dset.parameters['working_directory'], self.command_dir)))                
                for j, step in enumerate(run_steps):
                    if j < run_steps.index(next_step): continue
                    if self.options.get('mode') != 'screen' and step == 'strategy':
                        continue
    
                    self.run_step(step, dset, overwrite=overwrite, optional=(step=='image_analysis'))
                    # special post-step handling 
                    if step == 'correction':
                        # update parameters with reference after correction
                        if self.run_position > 0 and self.options.get('mode', 'simple') in ['merge', 'mad']:
                            _ref_file = os.path.join('..', 
                                        self.datasets.values()[i-1].results['correction']['output_file'])
                            dset.parameters.update({'reference_data': _ref_file,
                                                    'reference_sginfo': self.datasets.values()[i-1].results['symmetry'],
                                                    })
                    elif step == 'symmetry':
                        self.run_step('correction', dset, overwrite=overwrite) #final correction after symmetry
            next_step = 'scaling'
        
        if next_step == 'scaling':
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
            self.run_position = i 
            
            # Scoring and experiment setup check
            ISa =   dset.results['correction']['correction_factors']['parameters'][0].get('ISa', -1)
            _logger.info('(%s) Asymptotic I/Sigma(I): %0.1f' % (dset.name, ISa))
            _score = dset.score(self.options.get('mode')=='screening')
            _logger.info('(%s) Dataset Score: %0.1f' % (dset.name, _score))

            # Run Data Quality Step:
            _out = scaling.data_quality(dset.parameters, self.options)
            self.save_checkpoint()
            if not _out['success']:
                _logger.error('Failed (%s): %s' % ("data quality", _out['reason']))
                sys.exit()
            else:
                dset.results['data_quality'] = _out.get('data')
            
            # file format conversions
            if self.options.get('mode') != 'screen':
                _out = conversion.convert_formats(dset, self.options)
                if not _out['success']:
                    _logger.error('Failed (%s): %s' % ("conversion", _out['reason']))
                else:
                    dset.results['output_files'] = _out.get('data')
                    _logger.info('(%s) Output Files: %s' % (dset.name, ', '.join(_out['data'])))

            # reporting

        
        
            
                
            