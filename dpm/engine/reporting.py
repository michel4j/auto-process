def save_log(self, filename='process.log'):
    if self.options.get('anomalous', False):
        adj = 'ANOMALOUS'
    else:
        adj = 'NATIVE'
    info = self.get_log_dict()
    os.chdir(self.top_directory)
    fh = open(filename, 'w')

    # print summary
    file_text = utils.format_section(info['summary'], level=1)
    for name, dset in info['details'].items():
        file_text += utils.text_heading("DETAILED RESULTS FOR %s DATASET: '%s'" % (adj, name), level=1)
        file_text += utils.format_section(dset['parameters'], level=2)
        if dset.get('strategy', None) is not None: 
            file_text += utils.text_heading("Data Collection Strategy", level=2)
            for key in ['summary','oscillation', 'overlap']:
                if key in ['oscillation', 'overlap']:
                    invert = True
                else:
                    invert = False
                file_text += utils.format_section(dset['strategy'][key], level=3, invert=invert)
        file_text += utils.text_heading("Lattice Character and Space Group Determination", level=2)
        file_text += utils.format_section(dset['symmetry']['lattices'], level=3, 
                        invert=True, fields=['No.','Character', 'Cell Parameters', 'Quality'])
        file_text += utils.format_section(dset['symmetry']['lattices'], level=3, 
                        invert=True, fields=['No.', 'Cell Volume','Reindexing Matrix'], show_title=False)
        file_text += utils.format_section(dset['symmetry']['space_groups'], level=3, invert=True)
        file_text += utils.format_section(dset['correction'], level=2, invert=True)
        if dset.get('scaling',None) is not None:
            file_text += utils.text_heading(dset['scaling']['title'], level=2)
            for key in ['shells','frames','frame_difference']:
                file_text += utils.format_section(dset['scaling'][key], level=3, invert=True)
    
    file_text += '\n\n'
    out_text = utils.add_margin(file_text, 1)
    fh.write(out_text)    
    fh.close()
    
def get_log_dict(self):
    if self.options.get('anomalous', False):
        adj = 'Anomalous'
    else:
        adj = 'Native'
    info = {}
    
    _section = {}
    _section['title'] = '%s Data Processing Summary' % adj
    _sum_keys = ['Dataset','Score [a]', 'Wavelength (A)',    'Space Group [b]',
                  'Unit Cell (A)', '        (deg)', 
                  'Cell Volume (A^3)', 'Resolution (A)[c]', 'All Reflections',
                  'Unique Reflections', 'Multiplicity', 'Completeness',
                  'Mosaicity', 'I/sigma(I) [d]', 'R-mrgd-F [e]',
                  'R-meas [f]', 'sigma(spot) (pix)', 'sigma(angle) (deg)','No. Ice rings',
                  ]
    _section['table'] = []
    resol_method = {
        0: 'Based on detector edge, or limitted by input parameters.',
        1: 'Based on I/sigma(I) > 1 cut-off.',
        2: 'Based on  R-mrgd-F < 40% cut-off.',
        3: 'Calculated by DISTL (see Zang et al, J. Appl. Cryst. (2006). 39, 112-119'
    }
    
    for dataset_name in self.dataset_names:
        dset = self.results[dataset_name]
        if dset.get('image_analysis', None) is not None:
            _ice_rings = dset['image_analysis']['summary']['ice_rings']
        else:
            _ice_rings = 'N/C'
        if dset.get('scaling', None) is not None:
            _summary = dset['scaling']
        else:
            _summary= dset['correction']
        _sum_values = [ dataset_name,
            '%0.2f' % (dset['crystal_score'],),
            '%7.4f' % (self.dataset_info[dataset_name]['wavelength'],),
            utils.SPACE_GROUP_NAMES[ dset['correction']['symmetry']['space_group']['sg_number'] ],
            '%0.1f %0.1f %0.1f' % dset['correction']['symmetry']['space_group']['unit_cell'][:3],
            '%0.1f %0.1f %0.1f' % dset['correction']['symmetry']['space_group']['unit_cell'][3:],
            '%0.0f' % (utils.cell_volume(dset['correction']['symmetry']['space_group']['unit_cell']),),
            '%0.2f' % _summary['resolution'][0],
            _summary['summary']['observed'],
            _summary['summary']['unique'],
            '%0.1f' % (float(_summary['summary']['observed'])/_summary['summary']['unique'],),
            '%0.1f%%' % (_summary['summary']['completeness'],),
            '%0.2f' % (dset['correction']['summary']['mosaicity'],),
            '%0.1f' % (_summary['summary']['i_sigma'],),
            '%0.1f%%' % (_summary['summary']['r_mrgdf'],),
            '%0.1f%%' % (_summary['summary']['r_meas'],),
            '%0.1f' % (dset['correction']['summary']['stdev_spot'],),
            '%0.1f' % (dset['correction']['summary']['stdev_spindle'],),
            _ice_rings,
            ]
        _section['table'].append(zip(_sum_keys, _sum_values))
    _section['notes'] = """[a] Data Quality Score for comparing similar data sets. > 0.8 Excellent, > 0.6 Good, > 0.5 Acceptable, > 0.4 Marginal, > 0.3 Barely usable
[b] NOTE: Automatic Space group selection is unreliable for incomplete data. See detailed results below.
[c] Resolution selection method: %s
[d] Average I/sigma(I) for all data.
[e] Redundancy independent R-factor. Diederichs & Karplus (1997), Nature Struct. Biol. 4, 269-275.
[f] Quality of amplitudes. see Diederichs & Karplus (1997), Nature Struct. Biol. 4, 269-275.""" % resol_method[_summary['resolution'][1]]
    info['summary'] = _section
    
    info['details'] = {}
    for dataset_name in self.dataset_names:
        info['details'][dataset_name] = {}
        dset = self.results[dataset_name]
        # print out data collection parameters
        
        if dset.get('parameters', None) is not None:
            _section = {}
            _section['title'] = 'Data Collection and Processing Parameters'
            _section['table'] = []
            _keys = ['Description', 'Detector Distance (mm)','Exposure Time (sec)', 'No. Frames', 'Starting Angle (deg)',
                     'Delta (deg)', 'Two Theta (deg)', 'Detector Origin (pix)', 'Detector Size (pix)',
                     'Pixel Size (um)', 'File Template','Data Directory', 'Output Directory']
            _data_dir = os.path.dirname(dset['parameters']['file_template'])
            _out_dir = dset['parameters']['working_directory']
            _rows = ['Parameters', dset['parameters']['distance'],
                    dset['parameters']['exposure_time'],
                    dset['parameters']['frame_count'],
                    dset['parameters']['start_angle'],
                    dset['parameters']['delta_angle'], 
                    dset['parameters']['two_theta'], 
                    '%0.0f x %0.0f' %  dset['parameters']['beam_center'],
                    '%d x %d' %  dset['parameters']['detector_size'], 
                    '%0.5f x %0.5f' %  (dset['parameters']['pixel_size'],dset['parameters']['pixel_size']) ,
                     os.path.basename(dset['parameters']['file_template']),
                     _data_dir,
                     _out_dir]
            _section['table'].append(zip(_keys, _rows))
            if dset['files']['output'] is not None:
                _section['notes'] = " *  Output Files: %s " % (', '.join(dset['files']['output']))
            else:
                _section['notes'] = ''
            info['details'][dataset_name]['parameters'] = _section
        
        # Print out strategy information
        if dset.get('strategy', None) and dset['strategy'].get('runs', None) is not None:
            _strategy = {}
            _strategy['summary'] = {}
            _strategy['summary']['title'] = 'Recommended Strategy for %s Data Collection' % adj
            _strategy['summary']['table'] = []
            _strategy_keys = ['', 'Attenuation (%)', 'Distance (mm)',    'Start Angle',
                  'Delta (deg)', 'No. Frames', 'Total Angle (deg)', 'Exposure Time (s) [a]',
                  'Overlaps?', '-- Expected Quality --', 'Resolution',
                  'Completeness (%)', 'Multiplicity',
                  'I/sigma(I) [b]', 'R-factor (%) [b]' ]
            for run in dset['strategy']['runs']:
                _name = run['name']
                if run['number'] == 1:
                    _res = '%0.2f [c]' % (dset['strategy']['resolution'],)
                    _cmpl = '%0.1f' % (dset['strategy']['completeness'],)
                    _mlt = '%0.1f' % (dset['strategy']['redundancy'],)
                    _i_sigma = '%0.1f (%0.1f)' % (dset['strategy']['prediction_all']['average_i_over_sigma'],
                                                  dset['strategy']['prediction_hi']['average_i_over_sigma'])
                    _r_fac = '%0.1f (%0.1f)' % (dset['strategy']['prediction_all']['R_factor'],
                                                dset['strategy']['prediction_hi']['R_factor'])
                else:
                    _res = _cmpl = _mlt = _i_sigma = _r_fac = '<--'
                    

                _strategy_vals = [_name, '%0.0f' % (dset['strategy']['attenuation'],), 
                  '%0.1f' % (run['distance'],), 
                  '%0.1f' % (run['phi_start'],),
                  '%0.2f' % (run['phi_width'],), 
                  '%0.0f' % (run['number_of_images'],), 
                  '%0.2f' % (run['phi_width'] * run['number_of_images'],), 
                  '%0.1f' % (run['exposure_time'],),
                  '%s' % (run['overlaps'],), '-------------',
                  _res, _cmpl, _mlt, _i_sigma, _r_fac,                      
                  ]
                _strategy['summary']['table'].append(zip(_strategy_keys,_strategy_vals))
            
            run = utils.get_xplan_strategy(dset)
            if run:
                _strategy_vals = ['Alternate [d]', 'N/C', 
                  '', 
                  '%0.1f' % (run['start_angle'],),
                  '%0.2f' % (run['delta_angle'],), 
                  '%0.0f' % (run['number_of_images'],), 
                  '%0.2f' % (run['total_angle'],), 
                  '',
                  '', '-------------',
                  run['resolution'], run['completeness'], 
                  run['multiplicity'], 'N/C', 'N/C',                      
                  ]
                    
                _strategy['summary']['table'].append(zip(_strategy_keys, _strategy_vals))
            _strategy['summary']['notes'] = """[a] NOTE: Recommended exposure time does not take into account overloads at low resolution!
[b] Values in parenthesis represent the high resolution shell.
[c] %s
[d] Strategy Calculated according to XDS and XPLAN.  Determined from the following tables."""  %  dset['strategy']['resolution_reasoning']
            
            _section = {}
            _section['title'] = 'Alternate Optimal Selection of Collection Range'
            _section['table'] = []
            for row in dset['strategy']['xplan']['summary']:
                n_row = SortedDict()
                for k,t in [('Start Angle','start_angle'),('Total Angle', 'total_angle'),('Completeness','completeness'), ('Multiplicity','multiplicity') ]:
                    n_row[k] = row[t]
                _section['table'].append(n_row.items())
            _section['notes'] = ''
            _strategy['oscillation'] = _section
            
            _section = {}
            _section['title'] = 'Maximum Delta Angle to Prevent Angular Overlap'
            _section['table'] = []
            for row in dset['indexing']['oscillation_ranges']:
                n_row = SortedDict()                
                for k,t in [('High Resolution Limit','resolution'),('Max. Angle Delta [a]', 'delta_angle')]:
                    n_row[k] = row[t]
                _section['table'].append(n_row.items())
            _section['notes'] ='[a] NOTE: Assumes a mosaicity of zero!'
            _strategy['overlap'] = _section
            info['details'][dataset_name]['strategy'] = _strategy
         
        _section = {}
        _section['lattices'] = {}
        _section['lattices']['title'] = 'Compatible Lattice Character and Bravais Lattices'
        _section['lattices']['table'] = []
        _sec_keys = ['No.', 'Character', 'Cell Parameters', 'Quality', 'Cell Volume', 'Reindexing Matrix']
        for l in dset['correction']['symmetry']['lattices']:
            id, lat_type = l['id']
            sg = utils.POINT_GROUPS[ lat_type ][0]
            sg_name = utils.SPACE_GROUP_NAMES[ sg ]
            row = [id, 
                '%6s %3d %2s' % (sg_name, sg, lat_type), 
                '%5.1f %5.1f %5.1f %5.1f %5.1f %5.1f' % utils.tidy_cell(l['unit_cell'], lat_type),
                l['quality'], utils.cell_volume( l['unit_cell'] ),
                '%2d %2d %2d %2d %2d %2d %2d %2d %2d %2d %2d %2d' % l['reindex_matrix'] ]
            _section['lattices']['table'].append(zip(_sec_keys, row))
        
        _section['space_groups'] = {}
        _section['space_groups']['title'] = 'Likely Space Groups and their probabilities'
        _section['space_groups']['table'] = []
        _sec_keys = ['Space Group','No.', 'Probability']
        sg_num = dset['correction']['symmetry']['space_group']['sg_number']
        sg_name = utils.SPACE_GROUP_NAMES[ sg_num ]
        for i, sol in enumerate(dset['space_group']['candidates']):
            if sg_num == sol['number'] and i== 0:
                sg_name = '* %s' % (utils.SPACE_GROUP_NAMES[ sol['number'] ])
            else:
                sg_name = '  %s' % (utils.SPACE_GROUP_NAMES[ sol['number'] ])
            row = [ sg_name,   sol['number'],    sol['probability']]
            _section['space_groups']['table'].append(zip(_sec_keys, row))
        u_cell = utils.tidy_cell(dset['space_group']['unit_cell'], dset['space_group']['character'])
        sg_name = utils.SPACE_GROUP_NAMES[ dset['space_group']['sg_number'] ]
        _section['space_groups']['notes'] = "[*] Selected:  %s,  #%s. " % ( 
            sg_name, dset['space_group']['sg_number'] )
        _section['space_groups']['notes'] += " Unit Cell: %5.1f %5.1f %5.1f %5.1f %5.1f %5.1f." % u_cell 
        _section['space_groups']['notes'] += " NOTE: Detailed statistics reported below use this selection. "    
        if dset['space_group']['type'] == 'PointGroup':
            _section['space_groups']['notes'] += """
[!] Space Group is ambiguous. The lowest symmetry group of the high probability candidates has been chosen to permit reindexing in the future without loss of data!"""
        
        info['details'][dataset_name]['symmetry'] = _section
        
        # Print out integration results
        _section = {}
        _section['title'] = "Integration Statistics"
        _section['plot'] = []
        _keymap = [('Frame No.','frame'),('Scale Factor', 'scale'),('Overloads','overloads'), 
                   ('Reflections','reflections'), ('Mosaicity', 'mosaicity'),
                   ('Unexpected Spots','unexpected'), ('Divergence','divergence')]
        for row in dset['integration']['scale_factors']:
            n_row = SortedDict()
            for k,t in _keymap:
                n_row[k] = row[t]
            _section['plot'].append(n_row.items())
        _section['plot_axes'] = [('Frame No.',['Scale Factor']), ('Frame No.', ['Mosaicity']),('Frame No.',['Divergence'])]   
        info['details'][dataset_name]['integration'] = _section

        # Print out correction results
        _section = {}
        _section['title'] = "Correction Statistics"
        if dset.get('scaling', None) is not None:
            _data_key = 'table'
        else:
            _data_key = 'table+plot'
            _section['plot_axes'] = [('Resolution',['R_meas', 'R_mrgd-F', 'Completeness']),('Resolution', ['I/Sigma'])]
            if dset['parameters']['anomalous'] == True:
                _section['plot_axes'].append(('Resolution', ['SigAno']))
        _section[_data_key] = []
        for row in dset['correction']['statistics']:
            n_row = SortedDict()
            for k,t in [('Resolution','shell'),('Completeness', 'completeness'),('R_meas','r_meas'), ('R_mrgd-F','r_mrgdf'), ('I/Sigma','i_sigma'), ('SigAno','sig_ano'), ('AnoCorr','cor_ano')]:
                n_row[k] = row[t]
            _section[_data_key].append(n_row.items())
        resol = dset['correction']['resolution']
        _section['notes'] = "Preliminary resolution cut-off (%s):  %5.2f" % (resol_method[resol[1]], resol[0])    
        info['details'][dataset_name]['correction'] = _section
        
        # Print out scaling results
        if dset.get('scaling', None) is not None:
            _section = {}
            _section['title'] = "Scaling Statistics"
            _section['shells'] = {}
            _section['shells']['title'] = "Statistics presented by resolution shell"
            _data_key = 'table+plot' 
            _section['shells'][_data_key] = []
            for row in dset['scaling']['statistics']:
                n_row = SortedDict()
                for k, t in [('Resolution', 'shell'), ('Completeness', 'completeness'), ('R_meas', 'r_meas'), ('R_mrgd-F', 'r_mrgdf'), ('I/Sigma', 'i_sigma'), ('SigAno', 'sig_ano'), ('AnoCorr', 'cor_ano')]:
                    n_row[k] = row[t]
                _section['shells'][_data_key].append(n_row.items())
                
            _section['shells']['plot_axes'] = [('Resolution', ['R_meas', 'R_mrgd-F', 'Completeness']), ('Resolution', ['I/Sigma'])]
            if self.options.get('anomalous', False):
                _section['shells']['plot_axes'].append(('Resolution', ['SigAno']))
                  
            _section['frames'] = {}
            _section['frames']['title'] = "Statistics presented by frame"
            _section['frames']['plot'] = []
            for row in dset['scaling']['frame_statistics']:
                n_row = SortedDict()
                for k, t in [('Frame No', 'frame'), ('Intensity', 'i_obs'), ('No. Misfits', 'n_misfit'), ('R_meas', 'r_meas'), ('I/Sigma', 'i_sigma'), ('Unique', 'unique'), ('Corr', 'corr')]:
                    n_row[k] = row[t]
                _section['frames']['plot'].append(n_row.items())
            _section['frames']['plot_axes'] = [('Frame No.', ['R_meas']), ('Frame No.', ['I/Sigma', 'Corr']), ('Frame No.', ['No. Misfits', 'Unique'])]
           
            _section['frame_difference'] = {}
            _section['frame_difference']['title'] = "Statistics presented by frame difference"
            _section['frame_difference']['plot'] = []
            for row in dset['scaling']['diff_statistics']:
                n_row = SortedDict()
                for k, t in [('Frame difference', 'frame_diff'), ('R_d', 'rd'), ('R_d (friedel)', 'rd_friedel'), ('R_d (non-friedel)', 'rd_non_friedel'), ('No. Reflections', 'n_refl'), ('Friedel Reflections', 'n_friedel'), ('Non-Friedel Reflections', 'n_non_friedel')]:
                    n_row[k] = row[t]
                _section['frame_difference']['plot'].append(n_row.items())
            _section['frame_difference']['plot_axes'] = [('Frame difference.', ['R_d', 'R_d (friedel)', 'R_d (non-friedel)']), ('Frame difference', ['No. Reflections', 'Friedel Reflections', 'Non-Friedel Reflections'])]
        
            info['details'][dataset_name]['scaling'] = _section   

    return info

    def get_json_data(self):
        info = []
        
        for dataset_name in self.dataset_names:
            _dataset_info = {}
            dset = self.results[dataset_name]
            
            # read dataset file if present and use that to figure out the data_id, crystal_id, experiment_id
            data_id = None
            crystal_id = None
            exp_id = None
            dataset_file = os.path.join(
                              os.path.dirname(dset['parameters']['file_template']),
                              '%s.SUMMARY' % (dataset_name))

            if os.path.exists(dataset_file):
                dataset_info = json.load(file(dataset_file))
                data_id = dataset_info.get('id')
                crystal_id = dataset_info.get('crystal_id')
                exp_id = dataset_info.get('experiment_id')
            
            if dset.get('image_analysis', None) is not None:
                _ice_rings = dset['image_analysis']['summary']['ice_rings']
            else:
                _ice_rings = -1
            
            if dset.get('scaling', None) is not None:
                _summary = dset['scaling']
            else:
                _summary= dset['correction']
            _sum_keys = ['name', 'data_id', 'crystal_id', 'experiment_id', 'score', 'space_group_id', 'cell_a','cell_b', 'cell_c', 'cell_alpha', 'cell_beta','cell_gamma',
                     'resolution','reflections', 'unique','multiplicity', 'completeness','mosaicity', 'i_sigma',
                     'r_meas','r_mrgdf', 'sigma_spot', 'sigma_angle','ice_rings', 'url', 'wavelength']
            _sum_values = [
                dataset_name,
                data_id,
                crystal_id,
                exp_id,
                dset['crystal_score'], 
                dset['correction']['symmetry']['space_group']['sg_number'],
                dset['correction']['symmetry']['space_group']['unit_cell'][0],
                dset['correction']['symmetry']['space_group']['unit_cell'][1],
                dset['correction']['symmetry']['space_group']['unit_cell'][2],
                dset['correction']['symmetry']['space_group']['unit_cell'][3],
                dset['correction']['symmetry']['space_group']['unit_cell'][4],
                dset['correction']['symmetry']['space_group']['unit_cell'][5],
                _summary['resolution'][0],
                _summary['summary']['observed'],
                _summary['summary']['unique'],
                float(_summary['summary']['observed'])/_summary['summary']['unique'],
                _summary['summary']['completeness'],
                dset['correction']['summary']['mosaicity'],
                _summary['summary']['i_sigma'],
                _summary['summary']['r_meas'],
                _summary['summary']['r_mrgdf'],
                dset['correction']['summary']['stdev_spot'],
                dset['correction']['summary']['stdev_spindle'],
                _ice_rings,
                dset['parameters']['working_directory'],
                dset['parameters']['wavelength'],
                ]
            _dataset_info['result'] = dict(zip(_sum_keys, _sum_values))
            _dataset_info['result']['details'] = {}
            if dset['files'].get('output') is not None:
                _dataset_info['result']['details']['output_files'] = dset['files']['output']
            
            # compatible lattices and space group selection
            _section = {}
            _t = Table(dset['correction']['symmetry']['lattices'])
            _id = SortedDict(_t['id'])
            _section['id'] = _id.keys()
            _section['type'] = _id.values()
            _cell_fmt = '%5.1f %5.1f %5.1f %5.1f %5.1f %5.1f'
            _section['unit_cell'] = [_cell_fmt % c for c in _t['unit_cell']]
            _section['quality'] = _t['quality']
            _section['volume'] = [utils.cell_volume(c) for c in _t['unit_cell']]
            _dataset_info['result']['details']['compatible_lattices'] = _section
            
            _section = {}
            _t = Table(dset['space_group']['candidates'])
            _section['space_group'] = _t['number']
            _section['name'] = [utils.SPACE_GROUP_NAMES[n] for n in  _section['space_group']]
            _section['probability'] = _t['probability']            
            _dataset_info['result']['details']['spacegroup_selection'] = _section 

            # Harvest screening details
            if self.options.get('mode', None) == 'screen':
                _dataset_info['result']['kind'] = AUTOXDS_SCREENING
                if dset.get('strategy') is not None and dset['strategy'].get('runs') is not None:
                    _strategy = dset['strategy']
                    # harvest old strategy
                    _strategy_keys = ['name', 'attenuation', 'distance',    'start_angle',
                        'delta_angle', 'total_angle', 'exposure_time',
                        'exp_resolution', 'exp_completeness', 'exp_multiplicity',
                        'exp_i_sigma', 'exp_r_factor', 'energy',
                        ]
                    run = dset['strategy']['runs'][0]
                    _strategy_vals = [
                      dataset_name,
                      _strategy['attenuation'], 
                      run['distance'], run['phi_start'], run['phi_width'], 
                      run['phi_width'] * run['number_of_images'], run['exposure_time'],
                      _strategy['resolution'], _strategy['completeness'],
                      _strategy['redundancy'], _strategy['prediction_all']['average_i_over_sigma'],
                      _strategy['prediction_all']['R_factor'],
                      ]
                    _dataset_info['strategy'] = dict(zip(_strategy_keys,_strategy_vals))
                    
                    # harvest new strategy
                    _section = {
                        'name': dataset_name,
                        'attenuation': _strategy['attenuation'], 
                        'resolution': _strategy['resolution'],
                        'distance': run['distance'],
                        'start_angle': run['phi_start'],
                        'delta_angle': run['phi_width'],
                        'total_angle': run['phi_width'] * run['number_of_images'],
                        'exposure_time': run['exposure_time'],
                        'resolution_reasoning': _strategy['resolution_reasoning'],                  
                        'completeness':    _strategy['completeness'],
                        'r_factor':  _strategy['prediction_all']['R_factor'],
                        'i_sigma': _strategy['prediction_all']['average_i_over_sigma'],
                        'multiplicity': _strategy['redundancy'],
                        'frac_overload': _strategy['prediction_all']['fract_overload'],
                        }
                    _dataset_info['result']['details']['strategy'] = _section
                    
                    # overlap_analysis and wedge analysis
                    _st_details =_strategy.get('details', {})
                    _dataset_info['result']['details']['overlap_analysis'] = _st_details.get('delta_statistics')
                    _dataset_info['result']['details']['wedge_analysis'] = _st_details.get('completeness_statistics')
                    
                    
                    # shell_statistics
                    _st_shell = _st_details.get('shell_statistics', {})
                    _res_shells = [(x+y)/2.0 for x,y in zip(_st_shell.get('min_resolution',[]), _st_shell.get('max_resolution',[]))]
                    if len(_res_shells) > 1:
                        _section = {
                            'shell': _res_shells[:-1],
                            'completeness': [x*100 for x in _st_shell['completeness'][:-1]],
                            'r_factor': _st_shell['R_factor'][:-1],
                            'i_sigma': _st_shell['average_i_over_sigma'][:-1],
                            'multiplicity': _st_shell['redundancy'][:-1],
                            'frac_overload': _st_shell['fract_overload'][:-1],
                            }
                        _dataset_info['result']['details']['predicted_quality'] = _section
 
                    # exposure time statistics
                    _st_time = _st_details.get('time_statistics', {})
                    _res_shells = _st_time.get('resolution_max',[])
                    if len(_res_shells) > 0:
                        _section = {
                            'resolution': _res_shells,
                            'exposure_time': _st_time.get('ex_time'),
                            }
                        _dataset_info['result']['details']['exposure_analysis'] = _section
                   
                        
            else:  
                _dataset_info['result']['kind'] = AUTOXDS_PROCESSING
                # Print out integration results
                _section = {}
                _t = Table(dset['integration']['scale_factors'])
                for k in ['frame','scale','overloads','reflections','mosaicity','unexpected','divergence']:
                    _section[k] = _t[k]
                    
                if dset.get('scaling') is not None:
                    if dset['scaling'].get('frame_statistics') is not None:                     
                        _t = Table(dset['scaling']['frame_statistics'])
                        _section['frame_no'] = _t['frame']
                        for k in ['i_obs', 'n_misfit', 'r_meas', 'i_sigma', 'unique', 'corr']:
                            _section[k] = _t[k]
                    if dset['scaling'].get('diff_statistics') is not None:
                        _t = Table(dset['scaling']['diff_statistics'])
                        _dataset_info['result']['details']['diff_statistics'] = {}
                        for k in ['frame_diff', 'rd', 'rd_friedel', 'rd_non_friedel', 'n_refl', 'n_friedel', 'n_non_friedel']:
                            _dataset_info['result']['details']['diff_statistics'][k] = _t[k]
                _dataset_info['result']['details']['frame_statistics'] = _section
                
                _section = {}
                _t = Table(dset['integration']['batches'])
                for k in ['range','unit_cell','stdev_spot','stdev_spindle','mosaicity','distance','beam_center']:
                    _section[k] = _t[k]
                _dataset_info['result']['details']['integration_batches'] = _section
                    
                # Print out correction results
                _section = {}
                if dset.get('scaling') is not None and dset['scaling'].get('statistics') is not None:
                    _t = Table(dset['scaling']['statistics'])
                else:
                    _t = Table(dset['correction']['statistics'])
                for k in ['completeness','r_meas','r_mrgdf','i_sigma','sig_ano','cor_ano']:
                    _section[k] = _t[k][:-1] # don't get 'total' row
                _section['shell'] = [float(v) for v in _t['shell'][:-1]]
                _dataset_info['result']['details']['shell_statistics'] = _section
                
                # Print out standard errors
                if dset['correction'].get('standard_errors') is not None:
                    _section = {}
                    _t = Table(dset['correction']['standard_errors'])
                    _section['shell'] = [sum(v)/2.0 for v in _t['resol_range'][:-1]] # don't get 'total' row
                    for k in ['chi_sq', 'i_sigma', 'r_obs', 'r_exp','n_obs', 'n_accept', 'n_reject']:
                        _section[k] = _t[k][:-1]
                    _dataset_info['result']['details']['standard_errors'] = _section
                    
                #correction factors
                _dataset_info['result']['details']['correction_factors'] = dset['correction'].get('correction_factors')

                # Print out wilson_plot, cum int dist, twinning test
                if dset.get('data_quality') is not None:
                    if dset['data_quality'].get('wilson_plot') is not None:
                        _section = {}
                        _t = Table(dset['data_quality']['wilson_plot'])
                        for k in ['inv_res_sq', 'log_i_sigma']:
                            _section[k] = _t[k]
                        _dataset_info['result']['details']['wilson_plot'] = _section
                    if dset['data_quality'].get('cum_int_dist') is not None:
                        _section = {}
                        _t = Table(dset['data_quality']['cum_int_dist'])
                        for k in ['z', 'exp_acentric', 'exp_centric', 'obs_acentric', 'obs_centric', 'twin_acentric']:
                            _section[k] = _t[k]
                        _dataset_info['result']['details']['cum_int_dist'] = _section
                    if dset['data_quality'].get('twinning') is not None:
                        _section = {}
                        _t = Table(dset['data_quality']['twinning'])
                        for k in ['abs_l', 'observed', 'twinned', 'untwinned']:
                            _section[k] = _t[k]
                        _dataset_info['result']['details']['twinning_l_test'] = _section
                    if dset['data_quality'].get('wilson_line') is not None:
                        _dataset_info['result']['details']['wilson_line'] = dset['data_quality']['wilson_line']
                    if dset['data_quality'].get('wilson_scale') is not None:
                        _dataset_info['result']['details']['wilson_scale'] = dset['data_quality']['wilson_scale']
                    if dset['data_quality'].get('twinning_l_statistic') is not None:
                        _dataset_info['result']['details']['twinning_l_statistic'] = dset['data_quality']['twinning_l_statistic']
                       
            info.append(_dataset_info)
        return info
    
    def export_json(self, filename, err=None, traceback=None, code=1):

        result_list = self.get_json_data()
        names = [v['result']['name'] for v in result_list]
        
        # read previous json_file and obtain id from it if one exists:
        json_file_name = os.path.join(self.top_directory, filename)
        if os.path.exists(json_file_name):
            old_json = json.load(file(json_file_name))
            for info in old_json['result']:
                dataset_name = info['result']['name']
                if dataset_name in names:
                    pos = names.index(dataset_name)
                    result_list[pos]['id'] = info['result'].get('id')
                    
        # save json information to file
        if err is not None:
            error = {'message': err, "traceback": traceback, "code": code }
        else:
            error = None
            
        info = {
            'result': result_list,
            'error': error,
        }
        
        # save process.json
        os.chdir(self.top_directory)
        fh = open(filename, 'w')
        json.dump(info, fh)
        fh.close()
        
        # save debug.json
        fh = open('debug.json', 'w')
        json.dump(self.results, fh)
        fh.close()
        
        
        #generate html reports
        from dpm.utils import htmlreport
        for report in result_list:
            report_directory = os.path.join(report['result']['url'],'report')
            _logger.info('Generating report in %s ...' % (report_directory))
            if not os.path.exists(report_directory):
                os.makedirs(report_directory)
            if self.options.get('mode', None) == 'screen':
                try:
                    htmlreport.create_screening_report(report, report_directory)
                except:
                    pass
            else:
                try:
                    htmlreport.create_full_report(report, report_directory)
                except:
                    pass         
