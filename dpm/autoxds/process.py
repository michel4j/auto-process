""" 
Data Processing Class

"""

import os, sys, time

from dpm import parser
from gnosis.xml import pickle

import utils, io

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
        self.work_directory = utils.prepare_work_dir(
                self.options.get('directory', './')
                )
        os.chdir(self.work_directory)
        
    def save_xml(self, filename='autoxds.xml'):
        fh = open(filename, 'w')
        pickle.dump(self.results, fh)
        fh.close()
    
    def save_log(self, filename='autoxds.log'):
        fh = open(filename, 'w')
        file_text = ""
        for dset in self.results:
            file_text += "###--- Results for data in %s\n" % dset['parameters']['file_template']
            img_anal_res = dset.get('image_analysis', None)
            file_text += '\n CRYSTAL SCORE %8.3f \n' % dset['crystal_score']
            if img_anal_res is not None:
                file_text += '\n--- IMAGE ANALYSIS ---\n\n'
                good_percent = 100.0 * (img_anal_res['bragg_spots'])/img_anal_res['resolution_spots']
                file_text += "%20s:  %s\n" % ('File', img_anal_res['file'] )
                file_text += "%20s:  %8d\n" % ('Total Spots', img_anal_res['total_spots'] )
                file_text += "%20s:  %7.0f%%\n" % ('% Good Spots', good_percent )
                file_text += "%20s:  %8d\n" % ('Ice Rings', img_anal_res['ice_rings'] )
                file_text += "%20s:  %8.2f\n" % ('Estimated Resolution', img_anal_res['resolution'] )
                file_text += "%20s:  %7.0f%%\n\n" % ('Saturation(top %d)' % img_anal_res['peaks'], img_anal_res['saturation'] )


            file_text += "\n--- AUTOINDEXING ---\n\n"
            file_text += "Standard deviation of spot position:    %5.3f (pix)\n" % dset['autoindex']['stdev_spot']
            file_text += "Standard deviation of spindle position: %5.3f (deg)\n" % dset['autoindex']['stdev_spindle']
            file_text += "Mosaicity:  %5.3f\n" % dset['autoindex']['mosaicity']
            file_text += "\n--- Likely Lattice Types ---\n"
            file_text += "\n%16s %10s %7s %35s %8s %s\n" % (
                'Lattice Type',
                'PointGroup',
                'Quality',
                '_______ Unit Cell Parameters ______',
                'Cell Vol',
                'Reindex',
                )
            for l in utils.select_lattices(dset['autoindex']['lattice_table']):
                vol = utils.cell_volume( l['unit_cell'] )
                descr = "%s(%s)" % (utils.CRYSTAL_SYSTEMS[ l['character'][0] ], l['character'])
                sg = utils.POINT_GROUPS[ l['character'] ][0]
                sg_name = utils.SPACE_GROUP_NAMES[ sg ]
                txt_subst = (descr, sg, sg_name, l['quality'])
                reindex = '%2d %2d %2d %2d %2d %2d %2d %2d %2d %2d %2d %2d' % l['reindex_matrix']
                txt_subst += utils.tidy_cell(l['unit_cell'], l['character']) + (vol, reindex)
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
            sg_name = utils.SPACE_GROUP_NAMES[ dset['space_group']['group_number'] ]
            file_text += "\nSelected Group is:    %s,  #%s\n" % ( 
                sg_name, dset['space_group']['group_number'] )
            u_cell = utils.tidy_cell(dset['space_group']['unit_cell'], dset['space_group']['character'])
            file_text += "\nUnit Cell:    %7.2f %7.2f %7.2f %7.2f %7.2f %7.2f\n" % u_cell
            
            if dset['space_group']['type'] == 'pointgroup':
                file_text += "Space Group selection ambiguous. Current selection is not final!\n"  
            
            # Print out integration results
            file_text += "\n--- INTEGRATION ---\n"
            file_text  += '\n--- Summary ---\n'
            file_text += 'Observed Reflections: %11d\n' %  dset['integration']['observed']
            file_text += 'Unique Reflections:   %11d\n' %  dset['integration']['unique']
            file_text += 'Redundancy: %7.1f\n' %  ( float(dset['integration']['observed'])/dset['integration']['unique'] )
            file_text += 'Unit Cell:  %7.2f %7.2f %7.2f %7.2f %7.2f %7.2f\n' % dset['integration']['unit_cell']
            file_text += 'Cell E.S.D: %7.2g %7.2g %7.2g %7.2g %7.2g %7.2g\n' % dset['integration']['unit_cell_esd']
            file_text += 'Mosaicity:  %7.2f\n' % dset['integration']['mosaicity']
            file_text += "Standard deviation of spot position:    %5.3f (pix)\n" % dset['integration']['stdev_spot']
            file_text += "Standard deviation of spindle position: %5.3f (deg)\n" % dset['integration']['stdev_spindle']
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
            
            for l in dset['integration']['statistics_table']:
                file_text += '%8.2f %7.2f%% %7.2f%% %7.2f%% %8.2f %8.2f %8.1f\n' % (
                    l['shell'],
                    l['completeness'],
                    l['r_meas'],
                    l['r_mrgdf'],
                    l['i_sigma'],
                    l['sig_ano'],
                    l['cor_ano']
                    )
            file_text += '%8s %7.2f%% %7.2f%% %7.2f%% %8.2f %8.2f %8.1f\n' % (
                    'Total',
                    dset['integration']['completeness'],
                    dset['integration']['r_meas'],
                    dset['integration']['r_mrgdf'],
                    dset['integration']['i_sigma'],
                    dset['integration']['sig_ano'],
                    dset['integration']['cor_ano']
                    )
            resol = dset['integration']['resolution']
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
                for l in dset['scaling']['statistics_table']:
                    file_text += '%8.2f %7.2f%% %7.2f%% %7.2f%% %8.2f %8.2f %8.1f\n' % (
                        l['shell'],
                        l['completeness'],
                        l['r_meas'],
                        l['r_mrgdf'],
                        l['i_sigma'],
                        l['sig_ano'],
                        l['cor_ano']
                        )
                file_text += '%8s %7.2f%% %7.2f%% %7.2f%% %8.2f %8.2f %8.1f\n' % (
                        'Total',
                        dset['scaling']['completeness'],
                        dset['scaling']['r_meas'],
                        dset['scaling']['r_mrgdf'],
                        dset['scaling']['i_sigma'],
                        dset['scaling']['sig_ano'],
                        dset['scaling']['cor_ano']
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
        print 'AutoXDS: Using %d CPUs.' % self.dataset_info[0]['cpu_count']
        print "AutoXDS: Output in directory '%s'." % self.work_directory
        description = 'Processing'
        adj = 'native'
        if self.options.get('command',None) == 'screen':
            description = 'Characterizing'
        elif self.options.get('command',None) == 'mad':
            adj = 'MAD'
        elif self.options.get('anomalous', False):
            adj = 'anomalous'
        print "AutoXDS: %s %d %s dataset(s)... " % (
            description, len(self.dataset_info), adj)
        
        for run_info in self.dataset_info:
            run_result = {}
            run_result['parameters'] = run_info
            
            # AutoIndexing
            print "AutoXDS: Autoindexing '%s'" % run_info['prefix']
            jobs = 'XYCORR INIT COLSPOT IDXREF'
            io.write_xds_input(jobs, run_info)
            utils.execute_xds()
            info = parser.parse_idxref('IDXREF.LP')
            run_result['autoindex'] = info
            
            #Integration
            print "AutoXDS: Integrating '%s'" % run_info['prefix']
            jobs = "DEFPIX INTEGRATE CORRECT"
            io.write_xds_input(jobs, run_info)
            utils.execute_xds_par()
            print "AutoXDS: Selecting spacegroup for '%s' ..." % run_info['prefix'],
            success = utils.execute_pointless()
            if not success:
                print 'WARNING: Could not run POINTLESS! Automatic data processing may fail!'
            else:
                sg_info = parser.parse_pointless('pointless.xml')
                run_result['space_group'] = sg_info                        
                run_info['unit_cell'] = utils.tidy_cell(sg_info['unit_cell'], sg_info['character'])
                run_info['space_group'] = sg_info['group_number']
                run_info['reindex_matrix'] = sg_info['reindex_matrix']
                print sg_info['group_number'], utils.SPACE_GROUP_NAMES[sg_info['group_number']], sg_info['character']
            
            # Rerun CORRECT in the right space group and scale
            print "AutoXDS: Merging reflections in '%s'" % run_info['prefix']
            jobs = "CORRECT"
            io.write_xds_input(jobs, run_info)
            success = utils.execute_xds_par()
            if not success:
                print 'ERROR: Could not run CORRECT! Automatic data processing can not proceed!'
                return
            info = parser.parse_correct('CORRECT.LP')
            run_result['integration'] = info

            
            if self.options.get('command', None) == 'screen':
                success = utils.execute_best(run_info['exposure_time'], self.options.get('anomalous', False))
                if not success:
                    print 'ERROR: Could not calculate Strategy!'
                else:
                    info = parser.parse_best('best.xml')
                    run_result['strategy'] = info
                success = utils.execute_distl(run_info['reference_image'])
                if success:
                    info = parser.parse_distl('distl.log')
                    run_result['image_analysis'] = info
                else:
                    print 'ERROR: Image analysis failed!'
                    run_result['image_analysis'] = {}
                
            
            run_result['files'] = utils.save_files(run_info['prefix'])
            self.results.append( run_result )
               
            # Select Cut-off resolution
            resol = utils.select_resolution( run_result['integration']['statistics_table'])
            run_result['integration']['resolution'] = resol

        # SCALE data set(s) if we are not screening
        command = self.options.get('command', None)
        output_file_list = []
        if command == 'mad':
            sections = []
            for rres in self.results:
                resol = rres['integration']['resolution']
                in_file = rres['files']['correct']
                sections.append(
                    {'anomalous': self.options.get('anomalous', False),
                     'output_file': "%s-XSCALE.HKL" % rres['files']['prefix'],
                     'inputs': [{'input_file': in_file, 'resolution': resol}],
                    }
                    )
                output_file_list.append("%s-XSCALE.HKL" % rres['files']['prefix'])
                rres['files']['xscale'] = output_file_list
        else:
            inputs = []
            for rres in self.results:
                resol = rres['integration']['resolution']
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
            'unit_cell': self.results[0]['integration']['unit_cell'],
            'space_group': self.results[0]['integration']['space_group'],
            'sections': sections
            }
        
        io.write_xscale_input(xscale_options)
        success = utils.execute_xscale()
        if not success:
            print 'ERROR: SCALING Failed!'
            return

        if len(output_file_list) == 1:
            info = parser.parse_xscale('XSCALE.LP', output_file_list[0])
            self.results[-1]['scaling'] = info
        else:
            for ofile, rres in zip(output_file_list, self.results):
                info = parser.parse_xscale('XSCALE.LP', ofile)
                rres['scaling'] = info
        
        # Calculate SCORE
        for rres in self.results:
            print "AutoXDS: Scoring data set '%s'..." % rres['files']['prefix'],
            resolution = rres['integration']['resolution']
            mosaicity = rres['integration']['mosaicity']
            std_spot = rres['integration']['stdev_spot']
            std_spindle= rres['integration']['stdev_spindle']
            i_sigma = rres['scaling']['i_sigma']
            if i_sigma < -99: 
                i_sigma = rres['integration']['i_sigma']
            r_meas= rres['scaling']['r_meas']
            if r_meas < -99:
                r_meas = rres['integration']['r_meas']
            st_table = rres['autoindex']['subtree_table']            
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
                out_file_root = ''.join(infile.split('.'))

                # CNS File
                out_files.append(out_file_root + ".CNS")
                xdsconv_options = {
                    'resolution': 0.0,     #rres['integration']['resolution'],
                    'unit_cell': rres['integration']['unit_cell'],
                    'space_group': rres['integration']['space_group'],
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
                    'resolution': 0.0,     #rres['integration']['resolution'],
                    'unit_cell': rres['integration']['unit_cell'],
                    'space_group': rres['integration']['space_group'],
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
                    'resolution': 0.0,     #rres['integration']['resolution'],
                    'unit_cell': rres['integration']['unit_cell'],
                    'space_group': rres['integration']['space_group'],
                    'format': 'CCP4_F',
                    'anomalous': self.options.get('anomalous', False),
                    'input_file': infile,
                    'output_file': out_file_root + ".CCP4F",
                    'freeR_fraction': 0.05,
                }
                io.write_xdsconv_input(xdsconv_options)
                utils.execute_xdsconv()

            rres['files']['xdsconv'] = out_files                
            

        elapsed = time.time() - t1
        print "AutoXDS: Done. Total time used:  %d min %d sec"  % (int(elapsed/60), int(elapsed % 60))          
       
