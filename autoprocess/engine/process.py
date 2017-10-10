
import os
import sys
import time
import numpy
import json

import autoprocess.errors
from collections import OrderedDict
from autoprocess.utils import dataset, misc, log, xtal
from autoprocess.utils import kappa
from autoprocess.engine import indexing, spots, integration, scaling, solver
from autoprocess.engine import symmetry, strategy, conversion



_logger = log.get_module_logger(__name__)

VERSION = '4.0 RC'

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
    'solve-small': solver.solve_small_molecule
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
            raise autoprocess.errors.DatasetError('Filename/parameters not specified')
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

    def score(self):
        
        _overall = {}
        _overall.update(self.results['correction']['summary'])
        # full data processing
        if 'scaling' in self.results:
            _overall.update(self.results['scaling']['summary'])
            t = misc.Table(self.results['scaling']['statistics'])
        else:
            t = misc.Table(self.results['correction']['statistics'])

                    
        # screening
        if 'strategy' in self.results and 'shell_statistics' in self.results['strategy'].get('details', {}):
            _overall.update(self.results['strategy']['prediction_all'])
            _overall['resolution'] = [self.results['strategy']['resolution'], 0]

            # Average out the low resolution to approx the same level ~ 4.0 A
            t = misc.rTable(self.results['strategy']['details']['shell_statistics'])
            _shells = numpy.array(map(float, t['max_resolution'][:-1]))
            _isigma = numpy.array(t['average_i_over_sigma'][:-1])
            _rmeas = numpy.array(t['R_factor'][:-1])
            _compl = numpy.array(t['completeness'][:-1])*100.0
            
            sel = (_shells > 4.0)
            
            if sel.sum() == len(_shells):
                low_res = dict(zip(t.keys(), t.row(-1)))
            elif sel.sum() == 0:
                low_res = dict(zip(t.keys(), t.row(0)))
            else:
                # simple average
                low_res = {
                    'i_sigma': _isigma[sel].mean(),
                    'r_meas': _rmeas[sel].mean(),
                    'completeness': _compl.mean(),
                    'shell': _shells[sel][-1],
                }        
        else:         
            _shells = numpy.array(map(float, t['shell'][:-1]))
            _isigma = numpy.array(t['i_sigma'][:-1])
            _rmeas = numpy.array(t['r_meas'][:-1])
            _compl = numpy.array(t['completeness'][:-1])
            _nrefl = numpy.array(t['compared'][:-1])
            _unique = numpy.array(t['unique'][:-1])
            _possible = numpy.array(t['possible'][:-1])
            sel = (_shells > 4.0)
            
            if sel.sum() == len(_shells) or _nrefl[sel].any() == 0:
                low_res = dict(zip(t.keys(), t.row(-1)))
            elif sel.sum() == 0:
                low_res = dict(zip(t.keys(), t.row(0)))
            else:
                # weighted by number of reflections
                low_res = {
                    'i_sigma': (_isigma[sel]*_nrefl[sel]).mean() / _nrefl[sel].mean(),
                    'r_meas': (_rmeas[sel]*_nrefl[sel]).mean() / _nrefl[sel].mean(),
                    'completeness': 100.0 * _unique[sel].sum() / _possible[sel].sum(),
                    'shell': _shells[sel][-1],
                }

        if self.results.get('image_analysis') is not None:
            ice_rings = self.results['image_analysis'].get('summary', {}).get('ice_rings', -1)
        else:
            ice_rings = -1
                        
        score = xtal.score_crystal(_overall['resolution'][0], 
                                   low_res['completeness'],
                                   low_res['r_meas'],
                                   low_res['i_sigma'],
                                   _overall['mosaicity'], 
                                   _overall['stdev_spot'],
                                   _overall['stdev_spindle'],
                                   ice_rings)
        self.results['crystal_score'] = score
        return score
    
class Manager(object):
    def __init__(self, options=None, checkpoint=None, overwrites={}):
        
        self.datasets = OrderedDict()
        
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
                    _suffix = 'screen'
                else: 
                    _suffix = 'proc'
                _prefix = misc.combine_names(self.datasets.keys())
                    
                self.options['directory'] = os.path.join(self.options['command_dir'], '%s-%s' % (_prefix, _suffix))
            self.setup_directories()
        else:
            raise autoprocess.errors.DatasetError('Options/Checkpoint file not specified')
        
            

        
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
            except Exception as e:
                _logger.error("Could not prepare working directory '%s'." % self.options['directory'])
                _logger.error(e)
                raise autoprocess.errors.FilesystemError('Could not prepare working directory')
        
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
        
        # Create a log file also
        log.log_to_file(os.path.join(self.options['directory'], 'auto.log'))
        
        self._start_time = time.time()
        run_steps = ['initialize', 'image_analysis', 'spot_search', 
                     'indexing', 'integration','correction', 'symmetry',
                     'strategy',
                     ]
        
        _header = '------ AutoProcess(%s) - %s [%d dataset(s)] ------' % (VERSION, 
                              self.options['mode'].upper(), len(self.datasets))
        _separator = len(_header)*'-'
        _logger.info(_header)
        _env_hosts = os.environ.get('DPS_NODES', 'localhost')
        _num_nodes = len(_env_hosts.split(' '))

        _logger.debug('Computer system: %d nodes' % (_num_nodes))
        _logger.debug('Computer nodes: "%s"' % _env_hosts )
        if resume_from is not None:
            cur_pos, next_step = resume_from
        else:
            cur_pos, next_step = (0, 'initialize')

        # Fist initialize and index all datasets
        _sub_steps = ['initialize', 'image_analysis', 'spot_search', 'indexing']
        step_ovw = {}
        if next_step in _sub_steps:
            for i, dset in enumerate(self.datasets.values()):
                if i < cur_pos: continue  # skip all datasets earlier than specified one
                _logger.info(_separator)
                _logger.info('Initializing `%s` in directory "%s"' % (dset.name, 
                             misc.relpath(dset.parameters['working_directory'], self.options['command_dir'])))                
                for j, step in enumerate(_sub_steps):
                    self.run_position = (i, step)
                    
                    # prepare separate copy of overwrite parameters for this step
                    step_ovw = {}
                    step_ovw.update(overwrite)

                    # skip this step based on the properties
                    if j < _sub_steps.index(next_step): continue
                    if self.options.get('mode') != 'screen' and step == 'image_analysis': continue
    
                    self.run_step(step, dset, overwrite=step_ovw)
                    
                    # Special post processing after indexing
                    if step == 'indexing':
                        # Update parameters with reduced cell
                        dset.parameters.update({
                            'unit_cell': dset.results['indexing']['parameters']['unit_cell'],
                            'space_group': dset.results['indexing']['parameters']['sg_number']})
                        
                        _logger.log(log.IMPORTANT, "Reduced Cell: %0.2f %0.2f %0.2f %0.2f %0.2f %0.2f" % tuple(
                                            dset.results['indexing']['parameters']['unit_cell']))
                        _xter_list = [ v['character'] for v in dset.results['indexing']['lattices'] ]
                        _pg_txt = ", ".join(xtal.get_pg_list(_xter_list, chiral=self.options.get('chiral', True)))
                        _logger.log(log.IMPORTANT, "Possible Point Groups: %s" % _pg_txt)
                            
            next_step = 'integration'
        
        # then integrate and correct separately
        _sub_steps = ['integration', 'correction']
        if next_step in _sub_steps:
            for i, dset in enumerate(self.datasets.values()):
                if i < cur_pos: continue  # skip all datasets earlier than specified one                    
                _logger.info(_separator)
                for j, step in enumerate(_sub_steps):
                    self.run_position = (i, step)
                    
                    # skip this step based on the properties
                    if j < _sub_steps.index(next_step): continue
                    
                    # prepare separate copy of overwrite parameters for this step
                    step_ovw = {}
                    step_ovw.update(overwrite)
    
                    # special pre-step handling  for correction
                    if step == 'correction' and i > 0 and self.options.get('mode') in ['merge', 'mad']:                  
                        # update parameters with reference after correction
                        _ref_file = os.path.join('..', self.datasets.values()[i-1].results['correction']['output_file'])
                        _ref_sg = self.datasets.values()[0].results['correction']['summary']['spacegroup']
                        step_ovw.update({'reference_data': _ref_file, 'reference_spacegroup': _ref_sg })
                                                             
                    self.run_step(step, dset, overwrite=step_ovw)
            next_step = 'symmetry'
        
        
        # Check Spacegroup and scale the datasets
        if next_step == 'symmetry':
            self.run_position = (0, 'symmetry')
            if overwrite.get('sg_overwrite') is not None:
                _sg_number = overwrite['sg_overwrite']
                ref_info = None              
            elif self.options.get('mode') in ['merge', 'mad']:
                ref_opts = {}
                ref_opts.update(self.options)
                ref_opts.update(overwrite)
                ref_info = scaling.prepare_reference(self.datasets, ref_opts)
                _sg_number = ref_info['sg_number']
                
            for dset in self.datasets.values():
                if self.options.get('mode') in ['simple', 'screen'] and overwrite.get('sg_overwrite') is None:
                    # automatic spacegroup determination
                    self.run_step('symmetry', dset)
                    ref_sginfo = dset.results['symmetry']
                else:
                    # tranfer symmetry info from reference to this dataset and update with specific reindex matrix
                    if ref_info is not None: 
                        dset.results['symmetry'] = ref_info
                    ref_sginfo = symmetry.get_symmetry_params(_sg_number, dset)
                    dset.results['symmetry'].update(ref_sginfo)

                step_ovw = {}
                step_ovw.update(overwrite)
                step_ovw.update({
                    'space_group': ref_sginfo['sg_number'],
                    'unit_cell': ref_sginfo['unit_cell'],
                    'reindex_matrix': ref_sginfo['reindex_matrix'],
                    #'reference_data': ref_sginfo.get('reference_data'), # will be none for single data sets
                    'message': 'Reindexing & refining',
                    })
                self.run_step('correction', dset, overwrite=step_ovw)
                cell_str = "%0.6g %0.6g %0.6g %0.6g %0.6g %0.6g" % tuple(dset.results['correction']['summary']['unit_cell'])
                _logger.info('Refined cell: %s' % cell_str)         
            
            self.save_checkpoint()
            next_step = 'scaling'

        if next_step == 'scaling':
                            
            self.run_position = (0, 'scaling')
            step_ovw = {}
            step_ovw.update(self.options)
            step_ovw.update(overwrite)
            _out= scaling.scale_datasets(self.datasets, step_ovw)
            self.save_checkpoint()

            if not _out['success']:
                _logger.error('Failed (%s): %s' % (_out['step'], _out['reason']))
                sys.exit()
            next_step = 'strategy'

 
        # Strategy
        if self.options.get('mode') == 'screen' and next_step == 'strategy':
            self.run_position = (0, 'strategy')
            for dset in self.datasets.values():
                self.run_step('strategy', dset, overwrite=overwrite)
                # calculate and report the angles of the spindle from
                # the three axes
                xoptions = {}
                xoptions.update(self.options)
                xoptions.update(overwrite)
                xalign_options = xoptions.get('xalign', {'vectors': ("",""), 'method': 0})
                self.options['xalign'] = xalign_options
                
                _logger.info('Goniometer parameters for re-orienting crystal:')
                info = dset.results['correction']['parameters']
                _mode = {0:'MAIN', 1:'CUSP'}[xalign_options['method']]
                isols, pars = kappa.get_solutions(info, orientations=xalign_options['vectors'], mode=_mode)
                if pars['mode'] == 'MAIN':
                    descr = u'v1\u2225omega, v2\u2225omega-beam plane'
                    html_descr = 'v1 parallel to omega, v2 perpendicular to the omega-beam plane'
                else:
                    descr = u'v1\u27C2omega & beam, v2\u2225v1-omega plane'
                    html_descr = 'v1 parallel to both omega & beam, v2 perpendicular to the v1-omega plane'
                _logger.info("%6s %6s  %s: %s" % ("Kappa", "Phi", "(v1,v2)", descr))
                _logger.info("-"*58)
                sols = []
                for isol in isols:
                    txt = ", ".join(["(%s)" % v for v in  [",".join(p) for p in isol[1:]]])
                    _logger.info("%6.1f %6.1f  %s" % (isol[0][0], isol[0][1], txt))
                    sols.append((isol[0][0], isol[0][1], txt))
                _logger.info("-"*58)
                dset.results['strategy']['details']['crystal_alignment'] = {
                    'method': html_descr,
                    'solutions': sols,
                    'goniometer': pars['goniometer']
                }
            self.save_checkpoint()
        
        # check quality and covert formats     
        for i, dset in enumerate(self.datasets.values()):
            # Only calculate for first dataset when merging.
            if self.options['mode'] == 'merge' and i > 0: break
            
            # data description is different for merged data
            if self.options['mode'] == 'merge':
                _data_dscr = misc.combine_names(self.datasets.keys())
            else:
                _data_dscr = dset.name

            # Run Data Quality Step:
            if self.options.get('mode') != 'screen':
                self.run_position = (i, 'data_quality')
                _logger.info('Checking quality of dataset `%s` ...' % _data_dscr)
                _out = scaling.data_quality(dset.results['scaling']['output_file'], self.options)
                dset.log.append((time.time(), _out['step'], _out['success'], _out.get('reason', None)))
                if not _out['success']:
                    _logger.error('Failed (%s): %s' % ("data quality", _out['reason']))
                    sys.exit()
                else:
                    dset.results['data_quality'] = _out.get('data')
                self.save_checkpoint()
                       
            # Scoring and experiment setup check
            _score = dset.score()
            _logger.info('(%s) Dataset Score: %0.2f' % (dset.name, _score))
            ISa =   dset.results['correction']['correction_factors']['parameters'][0].get('ISa', -1)
            _logger.info('(%s) I/Sigma(I) Asymptote [ISa]: %0.1f' % (dset.name, ISa))
            
            # file format conversions
            self.run_position = (i, 'conversion')
            if self.options.get('mode') != 'screen':
                
                if self.options.get('mode') == 'merge' and i > 0: 
                    pass # do not convert 
                else:
                    _step_options = {}
                    _step_options.update(self.options)
                    _step_options['file_root'] = _data_dscr
                    
                    _out = conversion.convert_formats(dset, _step_options)
                    dset.log.append((time.time(), _out['step'], _out['success'], _out.get('reason', None)))
                    if not _out['success']:
                        dset.log.append((time.time(), _out['step'], _out['success'], _out.get('reason', None)))
                        _logger.error('Failed (%s): %s' % ("conversion", _out['reason']))
                    else:
                        dset.results['output_files'] = _out.get('data')
                        _logger.info('%s' % (', '.join(_out['data'])))
                self.save_checkpoint()


            if self.options.get('solve-small'):
                self.run_position = (i, 'solve-small')
                if self.options.get('mode') == 'merge' and i > 0: 
                    pass # do not solve 
                else:
                    _step_info = {
                        'unit_cell': dset.results['correction']['summary']['unit_cell'],
                        'name': _data_dscr,
                        'formula': self.options.get('solve-small'),
                    }
                    _out = solver.solve_small_molecule(_step_info, self.options)
                self.save_checkpoint()

        # reporting
        self.run_position = (0, 'reporting')
        os.chdir(self.options['directory'])
        self.save_checkpoint()

        # Save summaries
        import reporting
        log_data = reporting.get_log_data(self.datasets, self.options)
        reporting.save_log(log_data, 'process.log')   
        reports = reporting.get_reports(self.datasets, self.options)
        reporting.save_json(reports, 'process.json', self.options)
        _logger.info('Generating HTML reports ...')
        reporting.save_html(reports, self.options)      
            
        used_time = time.strftime('%H:%M:%S', time.gmtime(time.time() - self._start_time))
        _logger.info("Done in: %s"  % (used_time))
  
        
            
                
            
