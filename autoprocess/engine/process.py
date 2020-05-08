import copy
import gzip
import os
import subprocess
import sys
import time
from collections import OrderedDict
from datetime import datetime
import msgpack


import autoprocess.errors
from autoprocess import version
from autoprocess.engine import indexing, spots, integration, scaling, solver, reporting
from autoprocess.engine import symmetry, strategy, conversion
from autoprocess.utils import dataset, misc, log, xtal

logger = log.get_module_logger(__name__)


MAX_RMEAS_FACTOR = 2

STEP_FUNCTIONS = {
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

HARVEST_FUNCTIONS = {
    'initialize': spots.harvest_initialize,
    'spot_search': spots.harvest_spots,
    'indexing': indexing.harvest_index,
    'integration': integration.harvest_integrate,
    'correction': integration.harvest_correct,
}

THICK_LINE = '*' * 79
THIN_LINE = '-' * 79

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
        rejected_fraction = float(rejected) / reflections

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
    def __init__(self, options=None, checkpoint=None, overwrites=None):
        overwrites = overwrites or {}

        self.datasets = OrderedDict()

        if checkpoint is not None:
            self.run_position = checkpoint['run_position']
            self.options = checkpoint['options']
            self.options['command_dir'] = os.path.abspath(os.getcwd())

            for dset_info in checkpoint['datasets']:
                dset = DataSet(info=dset_info, overwrites=overwrites)
                self.datasets[dset.name] = dset

        elif options is not None:
            self.run_position = (0, 'initialize')
            self.options = options
            self.options['command_dir'] = os.path.abspath(os.getcwd())

            for img in options.get('images', []):
                dset = DataSet(filename=img, overwrites=overwrites)
                self.datasets[dset.name] = dset

            prefix = os.path.commonprefix(list(self.datasets.keys()))
            # prepare directories
            if not self.options.get('directory'):
                if self.options.get('mode') in ['screen', 'mad', 'merge']:
                    suffix = self.options.get('mode')
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
        multiple = (len(list(self.datasets.keys())) > 1)
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

        info = {
            'options': self.options,
            'run_position': self.run_position,
            'datasets': [d.get_info() for d in list(self.datasets.values())]
        }

        # Checkpoint file is saved in top-level processing directory
        fname = os.path.join(self.options['directory'], 'process.chkpt')
        with gzip.open(fname, 'wb') as handle:
            msgpack.dump(info, handle, default=str) #msgpack_numpy.encode

        return info

    def run_step(self, step, dset, overwrite=None, optional=False, colonize=False):
        """
        Runs the specified step with optional overwritten parameters
        and record the results in the dataset object.
        
        Will exit the program if a non optional step fails.
        
        """
        overwrite = overwrite or {}

        step_parameters = {}
        step_parameters.update(dset.parameters)
        step_parameters.update(overwrite)

        if colonize and step in HARVEST_FUNCTIONS:
            out = HARVEST_FUNCTIONS[step]
        else:
            # symmetry needs an extra parameter
            if step == 'symmetry':
                out = STEP_FUNCTIONS[step](step_parameters, dset, self.options)
            else:
                out = STEP_FUNCTIONS[step](step_parameters, self.options)

        dset.log.append((time.time(), out['step'], out['success'], out.get('reason', None)))
        if out.get('data') is not None:
            dset.results[step] = out.get('data')
        self.save_checkpoint()

        if not out['success']:
            if optional:
                logger.warning('Failed ({}): {}'.format(out['step'], out['reason']))
            else:
                logger.error('Failed ({}): {}'.format(out['step'], out['reason']))
                sys.exit(1)

    def screen(self, resume_from=None, single=False, overwrite=None):
        overwrite = overwrite or {}

    def process(self, resume_from=None, single=False, overwrite=None):
        overwrite = overwrite or {}

    def run(self, resume_from=None, single=False, colonize=False, overwrite=None):
        """
        resume_from is a tuple of the form
            (dataset_index, 'step')
        """
        overwrite = overwrite or {}

        # Create a log file also
        log.log_to_file(os.path.join(self.options['directory'], 'auto.log'))
        self.start_time = time.time()
        date_time = datetime.now().isoformat()
        header = f'AutoProcess (VERSION {version.get_version()})'
        sub_header = "{} on {} - {} [{:d} dataset(s)]".format(
            misc.get_project_name(),
            date_time, self.options['mode'].upper(),
            len([name for name in list(self.datasets.keys()) if name != 'combined'])
        )
        logger.info(f'{THICK_LINE}')
        logger.info(f'{header:^79}')
        logger.info(f'{THICK_LINE}')
        logger.info(f'{sub_header:^79}')

        env_hosts = os.environ.get('DPS_NODES', 'localhost')
        logger.debug('{:^79}'.format(f'Computer systems: {env_hosts}'))

        if resume_from is not None:
            cur_pos, next_step = resume_from
        else:
            cur_pos, next_step = (0, 'initialize')

        # Fist initialize and index all datasets
        sub_steps = ['initialize', 'spot_search', 'indexing']

        if next_step in sub_steps:
            for i, dset in enumerate(self.datasets.values()):
                if dset.name == 'combined' and self.options.get('mode') == 'merge':
                    # 'combined' merged dataset is special
                    continue
                if i < cur_pos: continue  # skip all datasets earlier than specified one
                logger.info(THIN_LINE)
                logger.info(
                    log.log_value('Processing dataset', dset.name, style=log.TermColor.normal)
                )
                logger.info(
                    log.log_value('Working directory:', dset.parameters["working_directory"])
                )

                for j, step in enumerate(sub_steps):
                    self.run_position = (i, step)

                    # prepare separate copy of overwrite parameters for this step
                    step_ovw = {}
                    step_ovw.update(overwrite)

                    # skip this step based on the properties
                    if j < sub_steps.index(next_step): continue
                    self.run_step(step, dset, overwrite=step_ovw, colonize=colonize)

                    # Special post processing after indexing
                    if step == 'indexing':
                        # Update parameters with reduced cell
                        dset.parameters.update({
                            'unit_cell': dset.results['indexing']['parameters']['unit_cell'],
                            'space_group': dset.results['indexing']['parameters']['sg_number']})
                        r_cell = "{:0.2f} {:0.2f} {:0.2f} {:0.2f} {:0.2f} {:0.2f}".format(
                            *dset.results['indexing']['parameters']['unit_cell']
                        )
                        xter_list = [v['character'] for v in dset.results['indexing']['lattices']]
                        p_groups = ", ".join(xtal.get_pg_list(xter_list, chiral=self.options.get('chiral', True)))
                        logger.info(log.log_value('Reduced Cell:',r_cell))
                        logger.info(log.log_value('Point Groups:', p_groups))

            next_step = 'integration'

        # then integrate and correct separately
        sub_steps = ['integration', 'correction']
        if next_step in sub_steps:
            for i, dset in enumerate(self.datasets.values()):
                if dset.name == 'combined' and self.options.get('mode') == 'merge':
                    # 'combined' merged dataset is special
                    continue
                if i < cur_pos: continue  # skip all datasets earlier than specified one                    
                logger.info(THIN_LINE)
                for j, step in enumerate(sub_steps):
                    self.run_position = (i, step)

                    # skip this step based on the properties
                    if j < sub_steps.index(next_step): continue

                    # prepare separate copy of overwrite parameters for this step
                    step_ovw = {}
                    step_ovw.update(overwrite)

                    # special pre-step handling  for correction
                    if step == 'correction' and i > 0 and self.options.get('mode') in ['merge', 'mad']:
                        # update parameters with reference after correction
                        ref_file = os.path.join(
                            '..', list(self.datasets.values())[i - 1].results['correction']['output_file']
                        )
                        ref_sg = list(self.datasets.values())[0].results['correction']['summary']['spacegroup']
                        step_ovw.update({'reference_data': ref_file, 'reference_spacegroup': ref_sg})

                    self.run_step(step, dset, overwrite=step_ovw, colonize=colonize)
                    if step == 'correction':
                        ISa = dset.results['correction']['correction_factors']['parameters'].get('ISa', -1)
                        r_meas = dset.results['correction']['summary']['inner_shell']['r_meas']
                        i_sigma = dset.results['correction']['summary']['inner_shell']['i_sigma']
                        logger.info(log.log_value(
                            'Low-res R-meas for "{}"'.format(dset.name),
                            f'{r_meas:0.1f} %'
                        ))
                        logger.info(log.log_value(
                            'Low-res I/Sigma for "{}"'.format(dset.name),
                            f'{i_sigma:0.1f}'
                        ))
                        if ISa >= 0:
                            logger.info(log.log_value(
                                'I/Sigma(I) Asymptote [ISa] for dataset "{}":'.format(dset.name),
                                f'{ISa:0.1f}'
                            ))
                        dset.results['integration']['statistics'] = copy.deepcopy(dset.results['correction'])

            next_step = 'symmetry'

        # Check Spacegroup and scale the datasets
        if next_step == 'symmetry':
            logger.info(THIN_LINE)
            self.run_position = (0, 'symmetry')
            ref_info = None
            sg_number = 0
            if overwrite.get('sg_overwrite') is not None:
                sg_number = overwrite['sg_overwrite']
                ref_info = None
            elif self.options.get('mode') in ['merge', 'mad']:
                ref_opts = {}
                ref_opts.update(self.options)
                ref_opts.update(overwrite)
                ref_info = scaling.prepare_reference(self.datasets, ref_opts)
                sg_number = ref_info['sg_number']

            for dset in list(self.datasets.values()):
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
                    ref_sginfo = symmetry.get_symmetry_params(sg_number, dset)
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
                cell_str = "{:0.6g} {:0.6g} {:0.6g} {:0.6g} {:0.6g} {:0.6g}".format(
                    *dset.results['correction']['summary']['unit_cell']
                )
                logger.info(log.log_value(
                    f'Refined unit cell for for "{dset.name}":', cell_str
                ))

                if self.options.get('mode') in ['merge']:
                    logger.info(log.log_value(f'Initial Score for dataset "{dset.name}"', f"{dset.score():0.2f}"))

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
            out = scaling.scale_datasets(self.datasets, step_ovw)
            self.save_checkpoint()

            if not out['success']:
                logger.error(f'Failed ({out["step"]}): {out["reason"]}')
                sys.exit()
            next_step = 'strategy'

        # Strategy
        if self.options.get('mode') == 'screen' and next_step == 'strategy':
            self.run_position = (0, 'strategy')
            for dset in list(self.datasets.values()):
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
                strategy_table.table.align[''] = 'r'
                for line in str(strategy_table).splitlines():
                    logger.info(line)

            self.save_checkpoint()

        # check quality and covert formats
        for i, dset in enumerate(self.datasets.values()):
            # Only calculate for 'combined' dataset when merging.
            if self.options['mode'] == 'merge' and dset.name != 'combined': continue

            # Run Data Quality Step:
            if self.options['mode'] != 'screen':
                logger.info(THIN_LINE)
                logger.info(f'Data processing of dataset "{dset.name}" complete.')
                self.run_position = (i, 'data_quality')

                out = scaling.data_quality(dset, self.options)
                dset.log.append((time.time(), out['step'], out['success'], out.get('reason', None)))
                if not out['success']:
                    logger.error(f'Failed ({"data quality"}): {out["reason"]}')
                    sys.exit()
                else:
                    dset.results['data_quality'] = out.get('data')
                self.save_checkpoint()

            # Scoring
            logger.info(log.log_value(f'Final Score for dataset "{dset.name}"', f"{dset.score():0.2f}"))

            # file format conversions
            self.run_position = (i, 'conversion')
            if self.options.get('mode') != 'screen':
                if self.options.get('mode') == 'merge' and dset.name != 'combined': continue
                step_options = {}
                step_options.update(self.options)
                step_options['file_root'] = dset.name

                out = conversion.convert_formats(dset, step_options)
                dset.log.append((time.time(), out['step'], out['success'], out.get('reason', None)))
                if not out['success']:
                    dset.log.append((time.time(), out['step'], out['success'], out.get('reason', None)))
                    logger.error(f'Failed ({"conversion"}): {out["reason"]}')
                else:
                    dset.results['output_files'] = out.get('data')
                self.save_checkpoint()

            if self.options.get('solve-small'):
                self.run_position = (i, 'solve-small')
                if self.options.get('mode') == 'merge' and i > 0:
                    pass  # do not solve
                else:
                    step_info = {
                        'unit_cell': dset.results['correction']['summary']['unit_cell'],
                        'name': dset.name,
                        'formula': self.options.get('solve-small'),
                    }
                    out = solver.solve_small_molecule(step_info, self.options)
                self.save_checkpoint()

        # reporting
        self.run_position = (0, 'reporting')
        os.chdir(self.options['directory'])
        checkpoint = self.save_checkpoint()

        # Save summaries
        logger.info('Generating reports ... report.html, report.txt')
        reporting.save_report(checkpoint['datasets'], self.options)


        used_time = time.strftime('%H:%M:%S', time.gmtime(time.time() - self.start_time))
        out = subprocess.check_output(['sync'])
        footer = f"AutoProcess done. Total time: {used_time}"
        logger.info(THICK_LINE)
        logger.info(f"{footer:^79}")
        logger.info(THICK_LINE)
        time.sleep(2.0)
