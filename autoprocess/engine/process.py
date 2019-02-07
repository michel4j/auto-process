import copy
import gzip
import os
import subprocess
import sys
import time
from collections import OrderedDict

import msgpack


import autoprocess.errors
from autoprocess.engine import indexing, spots, integration, scaling, solver, reporting
from autoprocess.engine import symmetry, strategy, conversion
from autoprocess.utils import dataset, misc, log, xtal


logger = log.get_module_logger(__name__)

VERSION = '4.0 RC'

_MAX_RMEAS_FACTOR = 2

_STEP_FUNCTIONS = {
    'initialize': spots.initialize,
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

_HARVEST_FUNCTIONS = {
    'initialize': spots.harvest_initialize,
    'spot_search': spots.harvest_spots,
    'indexing': indexing.harvest_index,
    'integration': integration.harvest_integrate,
    'correction': integration.harvest_correct,
}


class DataSet(object):
    def __init__(self, filename=None, info=None, overwrites=None):
        overwrites = {} if overwrites is None else overwrites
        if filename is not None:
            self.parameters = dataset.get_parameters(filename)
            self.parameters.update(overwrites)  # overwrite parameters
            self.log = []
            self.results = {}
        elif info is not None:
            self.set_info(info)
            self.parameters.update(overwrites)  # overwrite parameters
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
        self.results = info.get('results', {})

    def score(self):

        # can't calculate score if not 'correction' metadata
        if not 'correction' in self.results:
            return 0.0

        mosaicity = self.results['correction']['summary']['mosaicity']
        stdev_spot = self.results['correction']['summary']['stdev_spot']
        stdev_spindle = self.results['correction']['summary']['stdev_spindle']
        resolution = self.results['correction']['summary']['resolution'][0]
        completeness = self.results['correction']['summary']['completeness']

        reflections = self.results['correction']['total_reflections']
        rejected = self.results['correction'].get('rejected', 0)
        rejected_fraction = float(rejected)/reflections

        if 'scaling' in self.results:
            i_sigma = self.results['scaling']['summary']['inner_shell']['i_sigma']
            r_meas = self.results['scaling']['summary']['inner_shell']['r_meas']

        else:
            i_sigma = self.results['correction']['summary']['inner_shell']['i_sigma']
            r_meas = self.results['correction']['summary']['inner_shell']['r_meas']

        # screening
        if 'strategy' in self.results:
            resolution = self.results['strategy']['resolution']
            completeness = self.results['strategy']['completeness']

        score, scores = xtal.score_crystal(
            resolution, completeness, r_meas, i_sigma, mosaicity, stdev_spot, stdev_spindle, rejected_fraction
        )
        self.results['crystal_score'] = score
        logger.debug('Scoring Details:')
        for name, quality, val in scores:
            logger.debug('\t{:>20}:\t[{:g}] {:5.2f}'.format(name, val, quality))
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

            prefix = os.path.commonprefix(self.datasets.keys())


            # prepare directories
            if self.options.get('directory', None) is None:
                if self.options.get('mode') == 'screen':
                    suffix = 'screen'
                elif self.options.get('mode') == 'mad':
                    suffix = 'mad'
                elif self.options.get('mode') == 'merge':
                    suffix = 'merge'
                elif self.options.get('anomalous', False):
                    suffix = 'anom'
                else:
                    suffix = 'native'
                prefix = prefix or 'proc'
                directory = os.path.join(self.options['command_dir'], '{}-{}'.format(prefix, suffix))
                if self.options.get('backup') and os.path.exists(directory):
                    for i in range(99):
                        new_directory = '{}.{}'.format(directory, i + 1)
                        if not os.path.exists(new_directory):
                            directory = new_directory
                            break
                self.options['directory'] = directory
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

        try:
            misc.prepare_dir(self.options['directory'])
        except Exception as e:
            logger.error("Could not prepare working directory '%s'." % self.options['directory'])
            logger.error(e)
            raise autoprocess.errors.FilesystemError('Could not prepare working directory')

        # for multiple data sets, process each in a separate sub-directory
        multiple = (len(self.datasets.keys()) > 1)
        for i, dset in enumerate(self.datasets.values()):
            if multiple:
                directory = os.path.join(self.options['directory'], '{}-{}'.format(i, dset.name))
                dset.parameters['working_directory'] = directory
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
        fname = os.path.join(self.options['directory'], 'process.chkpt')
        with gzip.open(fname, 'wb') as handle:
            msgpack.dump(info, handle)
        return info

    def run_step(self, step, dset, overwrite={}, optional=False, colonize=False):
        """
        Runs the specified step with optional overwritten parameters
        and record the results in the dataset object.
        
        Will exit the program if a non optional step fails.
        
        """
        step_parameters = {}
        step_parameters.update(dset.parameters)
        step_parameters.update(overwrite)

        if colonize and step in _HARVEST_FUNCTIONS:
            _out = _HARVEST_FUNCTIONS[step]
        else:
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
                logger.warning('Failed (%s): %s' % (_out['step'], _out['reason']))
            else:
                logger.error('Failed (%s): %s' % (_out['step'], _out['reason']))
                sys.exit(1)


    def screen(self, resume_from=None, single=False, overwrite={}):
        pass

    def process(self, resume_from=None, single=False, overwrite={}):
        pass

    def run(self, resume_from=None, single=False, colonize=False, overwrite={}):
        """
        resume_from is a tuple of the form
            (dataset_index, 'step')
        """

        # Create a log file also
        log.log_to_file(os.path.join(self.options['directory'], 'auto.log'))
        self._start_time = time.time()
        _header = '------ AutoProcess({}) - {} [{:d} dataset(s)] ------'.format(
            VERSION, self.options['mode'].upper(), len([name for name in self.datasets.keys() if name != 'combined'])
        )
        _separator = len(_header) * '-'
        logger.info(_header)
        _env_hosts = os.environ.get('DPS_NODES', 'localhost')
        _num_nodes = len(_env_hosts.split(' '))

        logger.debug('Computer system: %d nodes' % (_num_nodes))
        logger.debug('Computer nodes: "%s"' % _env_hosts)

        run_steps = ['initialize', 'spot_search',
                     'indexing', 'integration', 'correction', 'symmetry',
                     'strategy',
                     ]


        if resume_from is not None:
            cur_pos, next_step = resume_from
        else:
            cur_pos, next_step = (0, 'initialize')

        # Fist initialize and index all datasets
        _sub_steps = ['initialize', 'spot_search', 'indexing']
        step_ovw = {}
        if next_step in _sub_steps:
            for i, dset in enumerate(self.datasets.values()):
                if dset.name == 'combined' and self.options.get('mode') == 'merge':
                    # 'combined' merged dataset is special
                    continue
                if i < cur_pos: continue  # skip all datasets earlier than specified one
                logger.info(_separator)
                logger.info('Initializing `{}` in directory "{}"'.format(
                    dset.name, os.path.relpath(dset.parameters['working_directory'], self.options['command_dir']))
                )
                for j, step in enumerate(_sub_steps):
                    self.run_position = (i, step)

                    # prepare separate copy of overwrite parameters for this step
                    step_ovw = {}
                    step_ovw.update(overwrite)

                    # skip this step based on the properties
                    if j < _sub_steps.index(next_step): continue
                    self.run_step(step, dset, overwrite=step_ovw, colonize=colonize)

                    # Special post processing after indexing
                    if step == 'indexing':
                        # Update parameters with reduced cell
                        dset.parameters.update({
                            'unit_cell': dset.results['indexing']['parameters']['unit_cell'],
                            'space_group': dset.results['indexing']['parameters']['sg_number']})

                        logger.log(log.IMPORTANT, "Reduced Cell: %0.2f %0.2f %0.2f %0.2f %0.2f %0.2f" % tuple(
                            dset.results['indexing']['parameters']['unit_cell']))
                        _xter_list = [v['character'] for v in dset.results['indexing']['lattices']]
                        _pg_txt = ", ".join(xtal.get_pg_list(_xter_list, chiral=self.options.get('chiral', True)))
                        logger.log(log.IMPORTANT, "Possible Point Groups: %s" % _pg_txt)

            next_step = 'integration'

        # then integrate and correct separately
        _sub_steps = ['integration', 'correction']
        if next_step in _sub_steps:
            for i, dset in enumerate(self.datasets.values()):
                if dset.name == 'combined' and self.options.get('mode') == 'merge':
                    # 'combined' merged dataset is special
                    continue
                if i < cur_pos: continue  # skip all datasets earlier than specified one                    
                logger.info(_separator)
                for j, step in enumerate(_sub_steps):
                    self.run_position = (i, step)

                    # skip this step based on the properties
                    if j < _sub_steps.index(next_step): continue

                    # prepare separate copy of overwrite parameters for this step
                    step_ovw = {}
                    step_ovw.update(overwrite)

                    # special pre-step handling  for correction
                    if step == 'correction' and  i > 0 and self.options.get('mode') in ['merge', 'mad']:
                        # update parameters with reference after correction
                        _ref_file = os.path.join('..',
                                                 self.datasets.values()[i - 1].results['correction']['output_file'])
                        _ref_sg = self.datasets.values()[0].results['correction']['summary']['spacegroup']
                        step_ovw.update({'reference_data': _ref_file, 'reference_spacegroup': _ref_sg})

                    self.run_step(step, dset, overwrite=step_ovw, colonize=colonize)
                    if step == 'correction':
                        ISa = dset.results['correction']['correction_factors']['parameters'][0].get('ISa', -1)
                        logger.info('(%s) I/Sigma(I) Asymptote [ISa]: %0.1f' % (dset.name, ISa))
                        dset.results['integration']['statistics'] = copy.deepcopy(dset.results['correction'])

            next_step = 'symmetry'

        # Check Spacegroup and scale the datasets
        if next_step == 'symmetry':
            self.run_position = (0, 'symmetry')
            ref_info = None
            _sg_number = 0
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
                if dset.name == 'combined' and self.options.get('mode') == 'merge':
                    # 'combined' merged dataset is special
                    continue
                if self.options.get('mode') in ['simple', 'screen'] and overwrite.get('sg_overwrite') is None:
                    # automatic spacegroup determination
                    self.run_step('symmetry', dset, colonize=colonize)
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
                    # 'reference_data': ref_sginfo.get('reference_data'), # will be none for single data sets
                    'message': 'Reindexing & refining',
                })
                self.run_step('correction', dset, overwrite=step_ovw, colonize=colonize)
                cell_str = "%0.6g %0.6g %0.6g %0.6g %0.6g %0.6g" % tuple(
                    dset.results['correction']['summary']['unit_cell'])
                logger.info('Refined cell: %s' % cell_str)

                if self.options.get('mode') in ['merge']:
                    _score = dset.score()

                    logger.info('(%s) Initial Score: %0.2f' % (dset.name, _score))

            self.save_checkpoint()
            next_step = 'strategy' if self.options.get('mode') == 'screen' else 'scaling'

        if next_step == 'scaling':

            self.run_position = (0, 'scaling')
            step_ovw = {}
            step_ovw.update(self.options)
            step_ovw.update(overwrite)
            if self.options.get('mode') == 'merge' and 'combined' in self.datasets:
                # 'combined' merged dataset is special remove it before scaling
                self.datasets.pop('combined', None)
            _out = scaling.scale_datasets(self.datasets, step_ovw)
            self.save_checkpoint()

            if not _out['success']:
                logger.error('Failed (%s): %s' % (_out['step'], _out['reason']))
                sys.exit()
            next_step = 'strategy'

        # Strategy
        if self.options.get('mode') == 'screen' and next_step == 'strategy':
            self.run_position = (0, 'strategy')
            for dset in self.datasets.values():
                if not 'resolution' in overwrite:
                    overwrite['resolution'] = dset.results['integration']['statistics']['summary']['stderr_resolution']
                self.run_step('strategy', dset, overwrite=overwrite, colonize=colonize)

                strategy = reporting.get_strategy(dset.results)
                strategy_table = misc.sTable([
                        ['Recommended Strategy', ''],
                        ['Resolution', '{:0.2f}'.format(strategy['resolution'])],
                        ['Attenuation', '{:0.1f}'.format(strategy['attenuation'])],
                        ['Start Angle', '{:0.0f}'.format(strategy['start_angle'])],
                        ['Maximum Delta Angle', '{:0.2f}'.format(strategy['max_delta'])],
                        ['Minimum Angle Range', '{:0.1f}'.format(strategy['total_angle'])],
                        ['Exposure Rate (deg/sec)', '{:0.2f}'.format(strategy['exposure_rate'])],
                        ['Overlaps?', strategy['overlaps']],
                ])
                for line in str(strategy_table).splitlines():
                    logger.info(line)

            self.save_checkpoint()

        # check quality and covert formats     
        for i, dset in enumerate(self.datasets.values()):
            # Only calculate for 'combined' dataset when merging.
            if self.options['mode'] == 'merge' and dset.name != 'combined': continue

            # Run Data Quality Step:
            if self.options.get('mode') != 'screen':
                self.run_position = (i, 'data_quality')
                logger.info('Checking quality of dataset `%s` ...' % dset.name)
                _out = scaling.data_quality(dset.results['scaling']['output_file'], self.options)
                dset.log.append((time.time(), _out['step'], _out['success'], _out.get('reason', None)))
                if not _out['success']:
                    logger.error('Failed (%s): %s' % ("data quality", _out['reason']))
                    sys.exit()
                else:
                    dset.results['data_quality'] = _out.get('data')
                self.save_checkpoint()

            # Scoring
            logger.info('(%s) Final Score: %0.2f' % (dset.name, dset.score()))

            # file format conversions
            self.run_position = (i, 'conversion')
            if self.options.get('mode') != 'screen':
                if self.options.get('mode') == 'merge' and dset.name != 'combined': continue
                _step_options = {}
                _step_options.update(self.options)
                _step_options['file_root'] = dset.name

                _out = conversion.convert_formats(dset, _step_options)
                dset.log.append((time.time(), _out['step'], _out['success'], _out.get('reason', None)))
                if not _out['success']:
                    dset.log.append((time.time(), _out['step'], _out['success'], _out.get('reason', None)))
                    logger.error('Failed (%s): %s' % ("conversion", _out['reason']))
                else:
                    dset.results['output_files'] = _out.get('data')
                    logger.info('%s' % (', '.join(_out['data'])))
                self.save_checkpoint()

            if self.options.get('solve-small'):
                self.run_position = (i, 'solve-small')
                if self.options.get('mode') == 'merge' and i > 0:
                    pass  # do not solve
                else:
                    _step_info = {
                        'unit_cell': dset.results['correction']['summary']['unit_cell'],
                        'name': dset.name,
                        'formula': self.options.get('solve-small'),
                    }
                    _out = solver.solve_small_molecule(_step_info, self.options)
                self.save_checkpoint()

        # reporting
        self.run_position = (0, 'reporting')
        os.chdir(self.options['directory'])
        checkpoint = self.save_checkpoint()

        # Save summaries
        logger.info('Generating Reports ...')
        reporting.save_report(checkpoint['datasets'], self.options)
        logger.info('    HTML: report.html ')
        logger.info('    TEXT: report.txt ')

        used_time = time.strftime('%H:%M:%S', time.gmtime(time.time() - self._start_time))
        out = subprocess.check_output(['sync'])
        logger.info("Done in: %s" % (used_time))
        time.sleep(2.0)
