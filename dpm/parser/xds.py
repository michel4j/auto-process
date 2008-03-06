"""
Parsers for XDS Files

"""

import utils

class _ParseInfo: pass

_idxref = _ParseInfo() # object for keeping track of IDXREF parsing information
_integrate = _ParseInfo() # object for keeping track of IDXREF parsing information
_xparm = _ParseInfo()
_correct = _ParseInfo()
_xscale = _ParseInfo()

_idxref.summary_start = 'DIFFRACTION PARAMETERS USED AT START OF INTEGRATION'
_idxref.summary_end = 'DETERMINATION OF LATTICE CHARACTER AND BRAVAIS LATTICE'
_idxref.summary = """
 STANDARD DEVIATION OF SPOT    POSITION (PIXELS)  %7f
 STANDARD DEVIATION OF SPINDLE POSITION (DEGREES) %7f
 CRYSTAL MOSAICITY (DEGREES) %9f
 DIRECT BEAM COORDINATES (REC. ANGSTROEM)  %9f %9f %9f
 DETECTOR COORDINATES (PIXELS) OF DIRECT BEAM  %9f %9f
 DETECTOR ORIGIN (PIXELS) AT                   %9f %9f
 CRYSTAL TO DETECTOR DISTANCE (mm)    %9f
 LAB COORDINATES OF DETECTOR X-AXIS %9f %9f %9f
 LAB COORDINATES OF DETECTOR Y-AXIS %9f %9f %9f
 LAB COORDINATES OF ROTATION AXIS %9f %9f %9f
 COORDINATES OF UNIT CELL A-AXIS %9f %9f %9f
 COORDINATES OF UNIT CELL B-AXIS %9f %9f %9f
 COORDINATES OF UNIT CELL C-AXIS %9f %9f %9f
 REC. CELL PARAMETERS  %9f %9f %9f %7f %7f %7f
 UNIT CELL PARAMETERS  %9f %9f %9f %7f %7f %7f
 SPACE GROUP NUMBER  %5d
"""
_idxref.summary_vars = [
    ('stdev_spot',1),
    ('stdev_spindle',1),
    ('mosaicity',1),
    ('direct_beam',3),
    ('beam_center',2),
    ('detector_origin',2),
    ('distance',1),
    ('detector_x_axis',3),
    ('detector_y_axis',3),
    ('rotation_axis',3),
    ('cell_a_axis',3),
    ('cell_b_axis',3),
    ('cell_c_axis',3),
    ('rec_cell',6),
    ('unit_cell',6),
    ('spacegroup', 1)]
    
_idxref.lattice = " %5d        %2c     %8f    %6f %6f %6f %5f %5f %5f   %2d %2d %2d %2d %2d %2d %2d %2d %2d %2d %2d %2d\n"
_idxref.lattice_start = "DETERMINATION OF LATTICE CHARACTER AND BRAVAIS LATTICE"
_idxref.lattice_end = "AFTER ALL THE INDIVIDUAL PROGRAM STEPS HAVE BEEN CARRIED OUT"
_idxref.lattice_vars = [
    ('index',1),
    ('character',1),
    ('quality',1),
    ('unit_cell',6),
    ('reindex_matrix', 12)]
    
_idxref.subtree_start = "RESULTS FROM LOCAL INDEXING"
_idxref.subtree_end = "SELECTION OF THE INDEX ORIGIN"
_idxref.subtree =" %5d     %8d\n"
_idxref.subtree_vars = [('subtree',1),('population',1)]

_integrate.scales = " %5d  %2d %6f %8d %4d %6d %7d %5d %7f %7f\n"
_integrate.scales_vars = [
    ('frame_number',1),
    ('error_code',1),
    ('scale_factor',1),
    ('background_pixels',1),
    ('overloads',1),
    ('reflections',1),
    ('strong',1),
    ('unexpecteds',1),
    ('sigmab',1),
    ('mosaicity',1)]
    
_integrate.profile = "   %3d%3d%3d%3d%3d%3d%3d%3d%3d   %3d%3d%3d%3d%3d%3d%3d%3d%3d   %3d%3d%3d%3d%3d%3d%3d%3d%3d\n"
_integrate.batch_start = 'PROCESSING OF IMAGES'
_integrate.batch_end = 'INTEGRATED BY PROFILE FITTING'
_integrate.batch = "PROCESSING OF IMAGES  %7d ... %7d"
_integrate.batch_vars = [ ('batch_start',1), ('batch_end',1) ]
_integrate.summary = _idxref.summary
_integrate.summary_vars = _idxref.summary_vars

_xparm.pattern = """ %5d %11f %11f %11f %11f %11f
 %14f %14f %14f %14f
 %9d %9d %9f %9f
 %14f %14f %14f
 %14f %14f %14f
 %14f %14f %14f
 %14f %14f %14f
 %9d %9f %9f %9f %9f %9f %9f
 %14f %14f %14f
 %14f %14f %14f
 %14f %14f %14f"""

_xparm.vars = [
    ('first_frame',1),
    ('start_angle',1),
    ('delta_angle',1),
    ('rotation_axis',3),
    ('wavelength',1),
    ('beam_vector',3),
    ('detector_size',2),
    ('pixel_size',2),
    ('distance',1),
    ('detector_origin',2),
    ('detector_matrix',6),
    ('spacegroup',1),
    ('unit_cell', 6),
    ('cell_a_axis',3),
    ('cell_b_axis',3),
    ('cell_c_axis',3)  ]

_correct.summary = """
 USING %7d INDEXED SPOTS
 STANDARD DEVIATION OF SPOT    POSITION (PIXELS)  %7f
 STANDARD DEVIATION OF SPINDLE POSITION (DEGREES) %7f
 CRYSTAL MOSAICITY (DEGREES) %9f
 DIRECT BEAM COORDINATES (REC. ANGSTROEM)  %9f %9f %9f
 DETECTOR COORDINATES (PIXELS) OF DIRECT BEAM  %9f %9f
 DETECTOR ORIGIN (PIXELS) AT                   %9f %9f
 CRYSTAL TO DETECTOR DISTANCE (mm)    %9f
 LAB COORDINATES OF DETECTOR X-AXIS %9f %9f %9f
 LAB COORDINATES OF DETECTOR Y-AXIS %9f %9f %9f
 LAB COORDINATES OF ROTATION AXIS %9f %9f %9f
 COORDINATES OF UNIT CELL A-AXIS %9f %9f %9f
 COORDINATES OF UNIT CELL B-AXIS %9f %9f %9f
 COORDINATES OF UNIT CELL C-AXIS %9f %9f %9f
 REC. CELL PARAMETERS  %9f %9f %9f %7f %7f %7f
 UNIT CELL PARAMETERS  %9f %9f %9f %7f %7f %7f
 E.S.D. OF CELL PARAMETERS %8e%8e%8e%8e%8e%8e
 SPACE GROUP NUMBER %6d
"""
_correct.summary_start = "REFINEMENT OF DIFFRACTION PARAMETERS USING ALL IMAGES"
_correct.summary_end = "MEAN INTENSITY AS FUNCTION OF SPINDLE POSITION"
_correct.summary_vars = [
    ('indexed_spots',1),
    ('stdev_spot',1),
    ('stdev_spindle', 1),
    ('mosaicity',1),
    ('direct_beam',3),
    ('beam_center',2),
    ('detector_origin',2),
    ('distance',1),
    ('detector_x_axis',3),
    ('detector_y_axis',3),
    ('rotation_axis',3),
    ('cell_a_axis',3),
    ('cell_b_axis',3),
    ('cell_c_axis',3),
    ('rec_cell',6),
    ('unit_cell',6),
    ('unit_cell_esd', 6),
    ('space_group', 1)]
    
_correct.final_start = 'STATISTICS OF SAVED DATA SET'
_correct.final_end = 'WILSON STATISTICS OF DATA SET'
_correct.wilson_start = 'WILSON STATISTICS OF DATA SET'
_correct.wilson_end = 'HIGHER ORDER MOMENTS OF WILSON DISTRIBUTION'
_correct.wilson_line = 'WILSON LINE (using all data) : A= %7f B= %7f CORRELATION= %5f'
_correct.wilson_line_vars = [('A',1),('B',1),('correlation',1)]
_correct.wilson = ' %7d %9f %7f %11f   %9f %9f\n'
_correct.wilson_vars = [
    ('#',1),
    ('RES',1),
    ('SS',1),
    ('<I>',1),
    ('log(<I>)',1),
    ('BO',1)
    ]
_correct.statistics_start = 'WITH SIGNAL/NOISE >=  0.0 AS FUNCTION OF RESOLUTION'
_correct.statistics_end = 'WITH SIGNAL/NOISE >=  3.0 AS FUNCTION OF RESOLUTION'
_correct.statistics_all = "\n    total %11d %7d %9d %10f% %9f% %8f% %8d %7f %7f% %7f% %5d% %7f %7d"
_correct.statistics = "\n %8f %11d %7d %9d %10f% %9f% %8f% %8d %7f %7f% %7f% %5d% %7f %7d"
_correct.statistics_vars = [
    ('shell',1),
    ('observed',1),
    ('unique',1),
    ('possible',1),
    ('completeness',1),
    ('r_obs',1),
    ('r_exp',1),
    ('compared',1),
    ('i_sigma',1),
    ('r_meas',1),
    ('r_mrgdf',1),
    ('cor_ano',1),
    ('sig_ano',1),
    ('Nano',1)
    ]
_xscale.statistics_vars = _correct.statistics_vars
_xscale.statistics = _correct.statistics
_xscale.statistics_all = _correct.statistics_all
_xscale.statistics_start = _correct.statistics_start
_xscale.statistics_end = _correct.statistics_end

def parse_idxref(filename):
    """
    Parse XDS IDXREF.LP file and return a dictionary containing all parameters
    
    """
    info = {}
    info['lattice_table'] = []
    info['subtree_table'] = []
    
        
    data = utils.load_file(filename)
    
    #first read the refinement summary information
    sum_section, pos = utils.cut_section(_idxref.summary_start, _idxref.summary_end, data)
    sum_vals, pos = utils.scanf(_idxref.summary, sum_section)
    if sum_vals:
        for k,v in utils.cast_params(_idxref.summary_vars, sum_vals).items():
            info[k] = v
        

    # read lattice character table
    lat_section, pos = utils.cut_section(_idxref.lattice_start, _idxref.lattice_end, data)
    lat_line, lat_pos = utils.scanf(_idxref.lattice, lat_section)
    while lat_line:
        info['lattice_table'].append(utils.cast_params(_idxref.lattice_vars, lat_line))
        lat_line, lat_pos = utils.scanf(_idxref.lattice, lat_section, lat_pos)
    
    def _cmp(x,y):
        return cmp(x['quality'], y['quality'])
    
    info['lattice_table'].sort(_cmp)
        
    # read subtree table
    st_section, pos = utils.cut_section(_idxref.subtree_start, _idxref.subtree_end, data)
    st_line, st_pos = utils.scanf(_idxref.subtree, st_section)
    while st_line:
        info['subtree_table'].append(utils.cast_params(_idxref.subtree_vars, st_line))
        st_line, st_pos = utils.scanf(_idxref.subtree, st_section, st_pos)
    
    return info

def parse_correct(filename):
    """
    Parse XDS CORRECT.LP file and return a dictionary containing all parameters
    
    """

    info = {}
    info['statistics_table'] = []
    info['wilson_table'] = []
    info['wilson_line'] = None

    data = utils.load_file(filename)
    
    #first read the refinement summary information
    sum_section, pos = utils.cut_section(_correct.summary_start, _correct.summary_end, data)
    sum_vals, vpos = utils.scanf(_correct.summary, sum_section)
    if sum_vals:
        for k,v in utils.cast_params(_correct.summary_vars, sum_vals).items():
            info[k] = v
    
    #then read final statistics table
    fin_section, pos = utils.cut_section(_correct.final_start, _correct.final_end, data)
    stat_section, pos = utils.cut_section(_correct.statistics_start, _correct.statistics_end, fin_section)
    stat_line, stat_pos = utils.scanf(_correct.statistics, stat_section)
    while stat_line:
        info['statistics_table'].append(utils.cast_params(_correct.statistics_vars, stat_line))
        stat_line, stat_pos = utils.scanf(_correct.statistics, stat_section, stat_pos)
        
    stat, stat_pos = utils.scanf(_correct.statistics_all, stat_section)
    if stat:
         for k,v in utils.cast_params(_correct.statistics_vars[1:], stat).items():
             info[k] = v
        
    #then read wilson statistics information
    wilson_section, pos = utils.cut_section(_correct.wilson_start, _correct.wilson_end, data)
    wilson_line, pos = utils.scanf(_correct.wilson_line, wilson_section)
    info['wilson_line'] = utils.cast_params(_correct.wilson_line_vars, wilson_line)    
    wilson, w_pos =utils.scanf(_correct.wilson, wilson_section)
    while wilson:
        info['wilson_table'].append(utils.cast_params(_correct.wilson_vars,wilson))
        wilson, w_pos =utils.scanf(_correct.wilson, wilson_section, w_pos)
        
    return info

def parse_xscale(filename, output_file='XSCALE.HKL'):
    """
    Parse XDS XSCALE.LP file and return a dictionary containing all parameters
    
    """

    info = {}
    info['statistics_table'] = []
    info['wilson_table'] = []
    info['wilson_line'] = None

    data = utils.load_file(filename)
    
    #read final statistics table
    final_start = 'STATISTICS OF SCALED OUTPUT DATA SET : %s' % output_file
    final_end = 'STATISTICS OF INPUT DATA SET'
    stat_end = 'WITH SIGNAL/NOISE >=  1.0 AS FUNCTION OF RESOLUTION'
    fin_section, pos = utils.cut_section(final_start, final_end, data)
    stat_section, pos = utils.cut_section(_correct.statistics_start, stat_end, fin_section)
    
    stat_line, stat_pos = utils.scanf(_correct.statistics, stat_section)
    while stat_line:
        info['statistics_table'].append(utils.cast_params(_correct.statistics_vars, stat_line))
        stat_line, stat_pos = utils.scanf(_correct.statistics, stat_section, stat_pos)
        
    stat, stat_pos = utils.scanf(_correct.statistics_all, stat_section)
    if stat:
        for k,v in utils.cast_params(_correct.statistics_vars[1:], stat).items():
            info[k] = v
        
    #then read wilson statistics information
    wilson_st = 'WILSON STATISTICS OF SCALED DATA SET: %s' % output_file
    wilson_end = 'HIGHER ORDER MOMENTS OF WILSON DISTRIBUTION' 
    wilson_section, pos = utils.cut_section(wilson_st, wilson_end, data)
    wilson_line, pos = utils.scanf(_correct.wilson_line, wilson_section)
    info['wilson_line'] = utils.cast_params(_correct.wilson_line_vars, wilson_line)    
    wilson, w_pos = utils.scanf(_correct.wilson, wilson_section)
    while wilson:
        info['wilson_table'].append(utils.cast_params(_correct.wilson_vars, wilson))
        wilson, w_pos =utils.scanf(_correct.wilson, wilson_section, w_pos)
       
    return info    
