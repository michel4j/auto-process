""" 
Data Processing Class

"""

import os, sys, time

from dpm.parser.pointless import parse_pointless
from dpm.parser.distl import parse_distl
from dpm.parser import xds
from dpm.parser.best import parse_best
from dpm.utils.log import get_module_logger, log_to_console
from dpm.utils.prettytable import PrettyTable
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
        if is_screening:
            workdir_prefix = 'screen'
        else: 
            workdir_prefix = 'process'
        self.top_directory = utils.prepare_work_dir(
                self.options.get('directory', './'),
                workdir_prefix
                )
        # for multiple data sets process each in a separate subdirectory
        if len(self.options['images']) == 1:
            img = self.options.get('images')[0]
            run_info = utils.get_dataset_params(img, is_screening)
            run_info['cpu_count'] = self.cpu_count
            if self.options.get('prefix'):
                run_info['dataset_name'] = self.options['prefix'][0]
            run_info['working_directory'] = self.top_directory
            self.dataset_info[run_info['dataset_name']] =  run_info
        else:   
            for i, img in enumerate(self.options['images']):
                run_info = utils.get_dataset_params(img, is_screening)
                run_info['cpu_count'] = self.cpu_count
                if self.options.get('prefix'):
                    run_info['dataset_name'] = self.options['prefix'][i]
                run_info['working_directory'] = os.path.join(self.top_directory,
                                                             run_info['dataset_name'])
                self.dataset_info[run_info['dataset_name']] =  run_info
        os.chdir(self.top_directory)
        
    def save_log(self, filename='autoxds.log'):
        os.chdir(self.top_directory)
        fh = open(filename, 'w')
        file_text = ""
        for dataset_name, dset in self.results.items():
            file_text += "\n###--- Results for data in %s\n" % dataset_name
            img_anal_res = dset.get('image_analysis', None)
            file_text += '\n CRYSTAL SCORE %8.3f \n' % dset['crystal_score']
            if img_anal_res is not None:
                file_text += '\n--- IMAGE ANALYSIS ---\n\n'
                good_percent = 100.0 * (img_anal_res['summary']['bragg_spots'])/img_anal_res['summary']['resolution_spots']
                file_text += "%20s:  %s\n" % ('File', img_anal_res['summary']['file'] )
                file_text += "%20s:  %8d\n" % ('Total Spots', img_anal_res['summary']['total_spots'] )
                file_text += "%20s:  %7.0f%%\n" % ('% Good Spots', good_percent )
                file_text += "%20s:  %8d\n" % ('Ice Rings', img_anal_res['summary']['ice_rings'] )
                file_text += "%20s:  %8.2f\n" % ('Estimated Resolution', img_anal_res['summary']['resolution'] )
                file_text += "%20s:  %7.0f%%\n\n" % ('Saturation(top %d)' % img_anal_res['summary']['peaks'], img_anal_res['summary']['saturation'] )


            file_text += "\n--- INDEXING ---\n\n"
            file_text += "Standard deviation of spot position:    %5.3f (pix)\n" % dset['indexing']['summary']['stdev_spot']
            file_text += "Standard deviation of spindle position: %5.3f (deg)\n" % dset['indexing']['summary']['stdev_spindle']
            file_text += "Mosaicity:  %5.3f\n" % dset['indexing']['summary']['mosaicity']
            file_text += "\n--- Likely Lattice Types ---\n"
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
            
            file_text += "\n--- SPACEGROUP SELECTION ---\n\n"
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
            file_text += "\n--- INTEGRATION and CORRECTION ---\n"
            file_text  += '\n--- Summary ---\n'
            file_text += 'Observed Reflections: %11d\n' %  dset['correction']['summary']['observed']
            file_text += 'Unique Reflections:   %11d\n' %  dset['correction']['summary']['unique']
            file_text += 'Redundancy: %7.1f\n' %  ( float(dset['correction']['summary']['observed'])/dset['correction']['summary']['unique'] )
            file_text += 'Unit Cell:  %7.2f %7.2f %7.2f %7.2f %7.2f %7.2f\n' % dset['correction']['summary']['unit_cell']
            file_text += 'Cell E.S.D: %7.2g %7.2g %7.2g %7.2g %7.2g %7.2g\n' % dset['correction']['summary']['unit_cell_esd']
            file_text += 'Mosaicity:  %7.2f\n' % dset['correction']['summary']['mosaicity']
            file_text += "Standard deviation of spot position:    %5.3f (pix)\n" % dset['correction']['summary']['stdev_spot']
            file_text += "Standard deviation of spindle position: %5.3f (deg)\n" % dset['correction']['summary']['stdev_spindle']
            file_text += '\n--- Statistics ---\n'
            
            pt = PrettyTable()
            tbl = Table(dset['correction']['statistics'])
            pt.add_column('Resolution', tbl['shell'], 'r')
            pt.add_column('Completeness', tbl['completeness'], 'r')
            pt.add_column('R_meas', tbl['r_meas'], 'r')
            pt.add_column('R_mrg-F', tbl['r_mrgdf'], 'r')
            pt.add_column('I/Sigma', tbl['i_sigma'], 'r')
            pt.add_column('SigAno', tbl['sig_ano'], 'r')
            pt.add_column('AnoCorr', tbl['cor_ano'], 'r')
                        
            file_text += str(pt)
            resol = dset['correction']['resolution']
            file_text += "\nResolution cut-off from preliminary analysis (I/SigI>1.5):  %5.2f\n\n" % (resol)
            

            # Print out scaling results
            if dset.get('scaling', None):
                file_text += "\n--- SCALING ---\n"
                file_text += '\n--- Statistics of scaled output data set ---\n'
                pt = PrettyTable()
                tbl = Table(dset['scaling']['statistics'])
                pt.add_column('Resolution', tbl['shell'], 'r')
                pt.add_column('Completeness', tbl['completeness'], 'r')
                pt.add_column('R_meas', tbl['r_meas'], 'r')
                pt.add_column('R_mrg-F', tbl['r_mrgdf'], 'r')
                pt.add_column('I/Sigma', tbl['i_sigma'], 'r')
                pt.add_column('SigAno', tbl['sig_ano'], 'r')
                pt.add_column('AnoCorr', tbl['cor_ano'], 'r')
                        
                file_text += str(pt)
            
            # Print out strategy information  
            if dset.get('strategy', None):
                file_text  += "\n--- STRATEGY ---\n\n"
                file_text  += '--- Recommended Strategy for Data Collection ---\n\n'
                all_runs = []
                data_labels = []
                data_labels.append('%20s:' % 'Run Number')
                data_labels.append('%20s:' % 'Attenuation')
                data_labels.append('%20s:' % 'Distance')
                data_labels.append('%20s:' % 'Start Angle')
                data_labels.append('%20s:' % 'Delta')
                data_labels.append('%20s:' % 'Frames')
                data_labels.append('%20s:' % 'Total Angle')
                data_labels.append('%20s:' % 'Exposure Time')
                data_labels.append('%20s' % 'Overlaps?')
        
                file_text  += 'NOTE: Recommended exposure time does not take into account overloads at low resolution!\n\n'
                for run in dset['strategy']['runs']:
                    run_data = []
                    run_data.append('%8d' % run['number'])
                    run_data.append('%7.0f%%' % dset['strategy']['attenuation'])
                    run_data.append('%8.1f' % run['distance'])
                    run_data.append('%8.1f' % run['phi_start'])
                    run_data.append('%8.2f' % run['phi_width'])
                    run_data.append('%8.0f' % run['number_of_images'])
                    run_data.append('%8.2f' % (run['phi_width'] * run['number_of_images']) )
                    run_data.append('%8.1f' % run['exposure_time'])
                    run_data.append('%8s' % run['overlaps'])
                    all_runs.append(run_data)
                
                for i in range(len(data_labels)):
                    line = data_labels[i]
                    for run_data in all_runs:
                        line += run_data[i]
                    file_text += "%s\n" % line
                    
                file_text += '\n--- Expected data quality ---\n\n'
                file_text += ' %20s: %8.2f\n' % ('Resolution', dset['strategy']['resolution'] )
                file_text += ' %20s: %7.1f%%\n' % ('Completeness', dset['strategy']['completeness'])
                file_text += ' %20s: %8.1f\n' % ('Redundancy', dset['strategy']['redundancy'])
                file_text += ' %20s: %8.1f (%0.1f)\n' % (
                    'I/Sigma (hires)', 
                    dset['strategy']['prediction_all']['average_i_over_sigma'],
                    dset['strategy']['prediction_hi']['average_i_over_sigma'])
                file_text += ' %20s: %7.1f%% (%0.1f%%)\n' % (
                    'R-factor (hires)', 
                    dset['strategy']['prediction_all']['R_factor'],
                    dset['strategy']['prediction_hi']['R_factor'])
        file_text += '\n\n'   
        fh.write(file_text)    
        fh.close()

    def save_xml(self, filename='autoxds.xml'):
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
        sigma = 6
        sepmin, clustrad = 6, 3
        spot_size = 6
        while info.get('failure') and _retries < 5:
            utils.print_table(data)
            _retries += 1
            utils.backup_file('IDXREF.LP')
            utils.backup_file('SPOT.XDS')
            # first correct detector origin
            if data['index_error_max'] > 0.051:
                _logger.info(':-( Indices deviate significantly from integral values!')
                if data['distinct_subtrees'] > 0:
                    #FIXME: in the future we should remove ice ring here
                    sigma *= 1.5
                    _logger.info('Retrying after removing spots with Sigma < %2.0f ...' % sigma)
                    spot_list = utils.load_spots()
                    spot_list = utils.filter_spots(spot_list, sigma=sigma)
                    utils.save_spots(spot_list)
                    utils.execute_xds_par()
                    info = xds.parse_idxref()
                    data = utils.diagnose_index(info)
                else:
                    spot_size *= 1.5
                    sepmin *= 1.5
                    clustrad *= 1.5
                    new_params = {'min_spot_size':spot_size, 'min_spot_separation':sepmin, 'cluster_radius': clustrad}
                    run_info.update(new_params)
                    _logger.info('Adjusting spot size and separation parameters ...')
                    io.write_xds_input('COLSPOT IDXREF', run_info)
                    utils.execute_xds_par()
                    info = xds.parse_idxref()
                    data = utils.diagnose_index(info)                  
            elif data['index_origin_delta'] > 6:
                _logger.info(':-( Index origin is not optimal!')
                run_info['detector_origin'] = data['new_origin']
                io.write_xds_input(jobs, run_info)
                _logger.info('Retrying with adjusted detector origin %0.1f %0.1f ...' % run_info['detector_origin'])
                utils.execute_xds_par()
                info = xds.parse_idxref()
                data = utils.diagnose_index(info)
            elif data['percent_indexed'] < 70.0 or data['spot_deviation'] >= 3.0:
                if data['percent_indexed'] < 70.0:
                    _logger.info(':-( Not enough percentage of indexed spots!')
                else:
                    _logger.info(':-( Solution is not accurate!')
                if data['primary_subtree'] < 90:
                    _logger.info('Retrying after removing unindexed alien spots ...')
                    spot_list = utils.load_spots()
                    spot_list = utils.filter_spots(spot_list, unindexed=True)
                    utils.save_spots(spot_list)
                    utils.execute_xds_par()
                    info = xds.parse_idxref()
                    data = utils.diagnose_index(info)
                else:
                    _logger.info('Retrying with Sigma=%2.0f ...' % sigma)
                    spot_list = utils.load_spots()
                    sigma *= 1.5
                    spot_list = utils.filter_spots(spot_list, sigma=sigma)
                    utils.save_spots(spot_list)
                    utils.execute_xds_par()
                    info = xds.parse_idxref()
                    data = utils.diagnose_index(info)
            else:
                _logger.info(':-( Unrecognized problem with auto-indexing')
                utils.print_table(data)
                break
        if info.get('failure') is None:
            _logger.info(':-) Auto-indexing succeeded.')
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
            #_logger.info(':-) Correction succeeded.')
            return {'success':True, 'data': info}
        else:
            return {'success':False, 'reason': info['failure']}

    def determine_spacegroup(self, run_info):
        os.chdir(run_info['working_directory'])
        _logger.info("Determining SpaceGroup...")
        success = utils.execute_pointless()
        if not success:
            _logger.warning(':-( SpaceGroup Determination failed!')
            return {'success':False, 'reason': 'POINTLESS FAILED!'}
        else:
            sg_info = parse_pointless('pointless.xml')
            return {'success':True, 'data': sg_info}        
    
    def scale_datasets(self, run_info):
        os.chdir(self.top_directory)
        _logger.info("Scaling ...")
        command = self.options.get('command', None)
        output_file_list = []
        if command == 'mad':
            sections = []
            _crystal_name = os.path.commonprefix(self.results.keys())
            for name, rres in self.results.items():
                resol = rres['correction']['resolution']
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
                    resol = rres['correction']['resolution']
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
            self.results.values()[-1]['scaling'] =  raw_info.values()[0]     
        else:
            for name, info in raw_info.items():
                self.results[name]['scaling'] = info
        if not success:
            _logger.error(':-( Scaling failed!')
            return {'success': False, 'reason': None}
    
    def convert_files(self, run_info):
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
                    'resolution': rres['correction']['resolution'],
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
                    'resolution': rres['correction']['resolution'],
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
                    'resolution': rres['correction']['resolution'],
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
        _reso = 1.0 #self.results[run_info['dataset_name']]['correction']['resolution']
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
    
    def score_dataset(self, rres):
        resolution = rres['correction']['resolution']
        mosaicity = rres['correction']['summary']['mosaicity']
        std_spot = rres['correction']['summary']['stdev_spot']
        std_spindle= rres['correction']['summary']['stdev_spindle']
        i_sigma = rres['correction']['summary']['i_sigma']
        r_meas = rres['correction']['summary']['r_meas']
        st_table = rres['indexing']['subtrees']            
        st_array = [i['population'] for i in st_table]
        subtree_skew = sum(st_array[1:]) / float(sum(st_array))
        if rres.has_key('image_analysis'):
            ice_rings = rres['image_analysis']['ice_rings']
        else:
            ice_rings = 0
        score = utils.score_crystal(resolution, mosaicity, r_meas, i_sigma,
                            std_spot, std_spindle,
                            subtree_skew, ice_rings)
        _logger.info("Dataset Score: %0.2f" % score)
        rres['crystal_score'] = score
                  
    def run(self):
        
        t1 = time.time()
        description = 'PROCESSING'
        adj = 'NATIVE'
        if self.options.get('command',None) == 'screen':
            description = 'CHARACTERIZING'
        elif self.options.get('command',None) == 'mad':
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
                _logger.error('Initialization FAILED! Reason: %s' % _out.get('reason'))
                sys.exit(1)
            
            # Auto Indexing
            _out = self.auto_index(run_info)
            if not _out['success']:
                _logger.error('Auto-indexing FAILED! Reason: %s' % _out.get('reason'))
                sys.exit(1)
            run_result['indexing'] = _out.get('data')
            
            #Integration
            _out = self.integrate(run_info)
            if not _out['success']:
                _logger.error('Integration FAILED! Reason: %s' % _out.get('reason'))
                sys.exit(1)
            run_result['integration'] = _out.get('data')

            #initial correction
            if _ref_run is not None:
                run_info['reference_data'] = os.path.join('..', self.results[_ref_run]['files']['correct'])
            _out = self.correct(run_info)
            if not _out['success']:
                _logger.error('Correction FAILED! Reason: %s' % _out.get('reason'))
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
                _logger.info('Proceeding with PointGroup: %s (#%d)' % (utils.SPACE_GROUP_NAMES[_sel_pgn], _sel_pgn))
                
            # Final correction
            _out = self.correct(run_info)
            if not _out['success']:
                _logger.error('Correction FAILED! Reason: %s' % _out.get('reason'))
            else:
                run_result['correction'] = _out.get('data')

            # Select Cut-off resolution
            resol = utils.select_resolution( run_result['correction']['statistics'])
            run_result['correction']['resolution'] = resol
            
            if self.options.get('command', None) == 'screen':
                _out = self.calc_strategy(run_info)
                if not _out['success']:
                    _logger.error('Strategy FAILED! Reason: %s' % _out.get('reason'))
                else:
                    run_result['strategy'] = _out.get('data')
#                success = utils.execute_distl(run_info['reference_image'])
#                if success:
#                    info = parse_distl('distl.log')
#                    run_result['image_analysis'] = info
#                else:
#                    print 'ERROR: Image analysis failed!'
#                    run_result['image_analysis'] = {}
                                            
            run_result['files'] = self.get_fileinfo(run_info)
            if _ref_run is None:
                _ref_run = run_name
            self.results[run_name] = run_result 
                           
            # Score dataset
            self.score_dataset(run_result)
        
        # Score dataset
        self.scale_datasets(run_info)
        
        self.convert_files(run_info)            
        self.save_xml('process.xml')
        self.save_log('process.log')

        elapsed = time.time() - t1
        _logger.info("Done. Total time used:  %d min %d sec"  % (int(elapsed/60), int(elapsed % 60)))          
       
