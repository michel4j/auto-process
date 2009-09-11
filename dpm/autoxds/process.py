""" 
Data Processing Class

"""

import os, sys, time

from dpm.parser.pointless import parse_pointless
from dpm.parser.distl import parse_distl
from dpm.parser.xds import parse_idxref, parse_correct, parse_xscale, parse_integrate
from dpm.parser.best import parse_best
from dpm.utils.log import get_module_logger, log_to_console
import pprint
from gnosis.xml import pickle

import utils, io

_logger = get_module_logger('AutoXDS')

class AutoXDS:
    results = []
    
    def __init__(self, options):
        self.options = options
        is_screening = (self.options.get('command', None) == 'screen')
        self.dataset_info = []
        for img, prefix in zip(self.options['images'], self.options['prefix']):
            run_info = utils.get_dataset_params(img, is_screening)
            run_info['prefix'] = prefix
            self.dataset_info.append( run_info )
        if is_screening:
            workdir_prefix = 'screen'
        else: 
            workdir_prefix = 'process'
        self.work_directory = utils.prepare_work_dir(
                self.options.get('directory', './'),
                workdir_prefix
                )
        os.chdir(self.work_directory)
        
    def save_xml(self, filename='autoxds.xml'):
        fh = open(filename, 'w')
        pickle.dump(self.results, fh)
        fh.close()

    def find_spots(self, run_info):
        _logger.info('Finding strong spots...')
        jobs = 'COLSPOT'
        io.write_xds_input(jobs, run_info)
        utils.execute_xds_par()
        if utils.check_spots():
            return {'success':True}
        else:
            return {'success':False, 'reason': 'Could not find spots.'}
        
    def initialize(self, run_info):
        _logger.info('Initializing...')
        jobs = 'XYCORR INIT'
        io.write_xds_input(jobs, run_info)
        utils.execute_xds_par()
        if utils.check_init():
            _out = self.find_spots(run_info)
            return _out   
        else:
            return {'success':False, 'reason': 'Could not create correction tables'}
        
    def auto_index(self, run_info):
        _logger.info('Auto-indexing...')
        jobs = 'IDXREF'
        io.write_xds_input(jobs, run_info)
        utils.execute_xds_par()
        info = parse_idxref()
        if info.get('failure'):
            data = utils.diagnose_index(info)            
            # filter out weaker spots and retry spots
            spot_list = utils.load_spots()
            sigma = 4
            _retries = 0
            while data['percent_indexed'] < 70.0 and sigma < 50 and _retries < 4:
                sigma *= 2
                _retries +=1
                _logger.info('Failed! Retrying with SIGMA=%2d ...' % sigma)
                spot_list = utils.filter_spots(spot_list, sigma=sigma)
                utils.save_spots(spot_list)
                utils.execute_xds_par()
                info = parse_idxref()
                _data = utils.diagnose_index(info)
                data = _data
            
            #utils.print_table(data)
                           
        if info.get('failure') is None:
            _logger.info('Auto-indexing SUCCESS')
            return {'success':True, 'data': info}
        else:
            return {'success':False, 'reason': info['failure']}
        
    def save_log(self, filename='autoxds.log'):
        fh = open(filename, 'w')
        file_text = ""
        for dset in self.results:
            file_text += "###--- Results for data in %s\n" % dset['parameters']['file_template']
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
            file_text += '\n%8s %8s %8s %8s %8s %8s %8s\n' % (
                'Shell',
                'Complete',
                'R_meas',
                'R_mrgd-F',
                'I/Sigma',
                'SigAno',
                'AnoCorr'
                )
            
            for l in dset['correction']['statistics']:
                file_text += '%8s %7.2f%% %7.2f%% %7.2f%% %8.2f %8.2f %8.1f\n' % (
                    l['shell'],
                    l['completeness'],
                    l['r_meas'],
                    l['r_mrgdf'],
                    l['i_sigma'],
                    l['sig_ano'],
                    l['cor_ano']
                    )
            resol = dset['correction']['resolution']
            file_text += "\nResolution cut-off from preliminary analysis (I/SigI>1.5):  %5.2f\n\n" % (resol)
            

            # Print out scaling results
            if dset.get('scaling',None):
                file_text += "\n--- SCALING ---\n"
                file_text += '\n--- Statistics ---\n'
                file_text += '\n%8s %8s %8s %8s %8s %8s %8s\n' % (
                    'Shell',
                    'Complete',
                    'R_meas',
                    'R_mrgd-F',
                    'I/Sigma',
                    'SigAno',
                    'AnoCorr'
                    )
                for l in dset['scaling']['statistics']:
                    file_text += '%8s %7.2f%% %7.2f%% %7.2f%% %8.2f %8.2f %8.1f\n' % (
                        l['shell'],
                        l['completeness'],
                        l['r_meas'],
                        l['r_mrgdf'],
                        l['i_sigma'],
                        l['sig_ano'],
                        l['cor_ano']
                        )
            
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
        
            
    def run(self):
        
        t1 = time.time()
        _logger.info('Using %d CPUs.' % self.dataset_info[0]['cpu_count'])
        _logger.info("Output in '%s'." % self.work_directory)
        description = 'Processing'
        adj = 'native'
        if self.options.get('command',None) == 'screen':
            description = 'Characterizing'
        elif self.options.get('command',None) == 'mad':
            adj = 'MAD'
        elif self.options.get('anomalous', False):
            adj = 'anomalous'
        _logger.info("%s %d %s dataset(s)... " % (
            description, len(self.dataset_info), adj))
        
        for run_info in self.dataset_info:
            run_result = {}
            run_result['parameters'] = run_info
            
            # Initializing
            _out = self.initialize(run_info)
            if not _out['success']:
                _logger.error('FAILED! Reason: %s' % _out.get('reason'))
                sys.exit(1)
            
            # Auto Indexing
            _out = self.auto_index(run_info)
            while not _out['success']:
                _logger.error('Auto-indexing FAILED! Reason: %s' % _out.get('reason'))
                sys.exit(1)
            run_result['indexing'] = _out.get('data')
            
            #Integration
            print "AutoXDS: Integrating '%s'" % run_info['prefix']
            jobs = "DEFPIX INTEGRATE CORRECT"
            io.write_xds_input(jobs, run_info)
            utils.execute_xds_par()
            print "AutoXDS: Selecting spacegroup for '%s' ..." % run_info['prefix'],
            success = utils.execute_pointless()
            if not success:
                print 'WARNING: Could not run POINTLESS! SpaceGroup Selection may fail!'
            else:
                sg_info = parse_pointless('pointless.xml')
                run_result['space_group'] = sg_info                        
                run_info['unit_cell'] = utils.tidy_cell(sg_info['unit_cell'], sg_info['character'])
                run_info['space_group'] = sg_info['sg_number']
                run_info['reindex_matrix'] = sg_info['reindex_matrix']
                print sg_info['sg_number'], utils.SPACE_GROUP_NAMES[sg_info['sg_number']], sg_info['character']
            
            # Rerun CORRECT in the right space group and scale
            print "AutoXDS: Merging reflections in '%s'" % run_info['prefix']
            jobs = "CORRECT"
            io.write_xds_input(jobs, run_info)
            success = utils.execute_xds_par()
            if not success:
                print 'ERROR: Could not run CORRECT! Automatic data processing can not proceed!'
                return
            info = parse_correct()
            if info.get('statistics') is not None:
                if len(info['statistics']) > 1 and info.get('summary') is not None:
                    info['summary'].update( info['statistics'][-1] )
            run_result['correction'] = info
            run_result['integration'] = parse_integrate()

            
            if self.options.get('command', None) == 'screen':
                success = utils.execute_best(run_info['exposure_time'], self.options.get('anomalous', False))
                if not success:
                    print 'ERROR: Could not calculate Strategy!'
                else:
                    info = parse_best('best.xml')
                    run_result['strategy'] = info
                success = utils.execute_distl(run_info['reference_image'])
                if success:
                    info = parse_distl('distl.log')
                    run_result['image_analysis'] = info
                else:
                    print 'ERROR: Image analysis failed!'
                    run_result['image_analysis'] = {}
                
            
            run_result['files'] = utils.save_files(run_info['prefix'])
            self.results.append( run_result )
               
            # Select Cut-off resolution
            resol = utils.select_resolution( run_result['correction']['statistics'])
            run_result['correction']['resolution'] = resol

        # SCALE data set(s) if we are not screening
        command = self.options.get('command', None)
        output_file_list = []
        if command == 'mad':
            sections = []
            for rres in self.results:
                resol = rres['correction']['resolution']
                in_file = rres['files']['correct']
                sections.append(
                    {'anomalous': self.options.get('anomalous', False),
                     'output_file': "%s/XSCALE.HKL" % rres['files']['prefix'],
                     'inputs': [{'input_file': in_file, 'resolution': resol}],
                    }
                    )
                scale_out_file = "%s/XSCALE.HKL" % rres['files']['prefix']
                output_file_list.append(scale_out_file)
                rres['files']['xscale'] = [scale_out_file]
        else:
            inputs = []
            for rres in self.results:
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
    
        print 'AutoXDS: Scaling data set(s) ...'
        xscale_options = {
            'cpu_count': self.dataset_info[0]['cpu_count'],
            'unit_cell': self.results[0]['correction']['symmetry']['space_group']['unit_cell'],
            'space_group': self.results[0]['correction']['symmetry']['space_group']['sg_number'],
            'sections': sections
            }
        
        io.write_xscale_input(xscale_options)
        success = utils.execute_xscale()
        if not success:
            print 'ERROR: SCALING Failed!'
            return

        if len(output_file_list) == 1:
            info = parse_xscale('XSCALE.LP', output_file_list[0])
            if info.get('statistics') is not None:
                if len(info['statistics']) > 1:
                    info['summary'] = info.get('statistics')[-1]               
            self.results[-1]['scaling'] = info
        else:
            for ofile, rres in zip(output_file_list, self.results):
                info = parse_xscale('XSCALE.LP', ofile)
                if info.get('statistics') is not None:
                    if len(info['statistics']) > 1:
                        info['summary'] = info.get('statistics')[-1]               
                rres['scaling'] = info
        
        # Calculate SCORE
        for rres in self.results:
            print "AutoXDS: Scoring data set '%s'..." % rres['files']['prefix'],
            resolution = rres['correction']['resolution']
            mosaicity = rres['correction']['summary']['mosaicity']
            std_spot = rres['correction']['summary']['stdev_spot']
            std_spindle= rres['correction']['summary']['stdev_spindle']
            i_sigma = rres['scaling']['summary']['i_sigma']
            if i_sigma < -99: 
                i_sigma = rres['correction']['summary']['i_sigma']
            r_meas= rres['scaling']['summary']['r_meas']
            if r_meas < -99:
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
            print '%8.3f' % score
            rres['crystal_score'] = score
        
        # GENERATE MTZ and CNS output files    
        for rres in self.results:
            print 'AutoXDS: Converting data set(s) to MTZ, SHELX and CNS ...'
            out_files = []
            for infile in rres['files']['xscale']:
                out_file_root = ''.join(infile.split('.')[:-1])

                # CNS File
                out_files.append(out_file_root + ".CNS")
                xdsconv_options = {
                    'resolution': rres['correction']['resolution'],
                    'unit_cell': rres['correction']['symmetry']['space_group']['unit_cell'],
                    'space_group': rres['correction']['symmetry']['space_group']['sg_number'],
                    'format': 'CNS',
                    'anomalous': self.options.get('anomalous', False),
                    'input_file': infile,
                    'output_file': out_file_root + ".CNS",
                    'freeR_fraction': 0.05,
                }
                io.write_xdsconv_input(xdsconv_options)
                utils.execute_xdsconv()

                #SHELX File
                out_files.append(out_file_root + ".SHELX")
                xdsconv_options = {
                    'resolution': rres['correction']['resolution'],
                    'unit_cell': rres['correction']['symmetry']['space_group']['unit_cell'],
                    'space_group': rres['correction']['symmetry']['space_group']['sg_number'],
                    'format': 'SHELX',
                    'anomalous': self.options.get('anomalous', False),
                    'input_file': infile,
                    'output_file': out_file_root + ".SHELX",
                    'freeR_fraction': 0.05,
                }
                io.write_xdsconv_input(xdsconv_options)
                utils.execute_xdsconv()

                #MTZ File
                out_files.append(out_file_root + ".MTZ")
                xdsconv_options = {
                    'resolution': rres['correction']['resolution'],
                    'unit_cell': rres['correction']['symmetry']['space_group']['unit_cell'],
                    'space_group': rres['correction']['symmetry']['space_group']['sg_number'],
                    'format': 'CCP4_F',
                    'anomalous': self.options.get('anomalous', False),
                    'input_file': infile,
                    'output_file': out_file_root + ".CCP4F",
                    'freeR_fraction': 0.05,
                }
                io.write_xdsconv_input(xdsconv_options)
                utils.execute_xdsconv()
                
                f2mtz_options = {
                    'output_file': out_file_root + ".MTZ"
                }
                io.write_f2mtz_input(f2mtz_options)
                utils.execute_f2mtz()
            
            print 'AutoXDS: Output Files ... \n\t', ',\n\t'.join(out_files)
            rres['files']['xdsconv'] = out_files               
            

        elapsed = time.time() - t1
        print "AutoXDS: Done. Total time used:  %d min %d sec"  % (int(elapsed/60), int(elapsed % 60))          
       
