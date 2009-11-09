"""
Input/Output routines for XDS and file conversion utilities

"""
import math
import utils
import tempfile
import os

def write_xds_input(jobs, params):
    """
    Create XDS.INP file using parameters in the dictionary params
    jobs = XYCORR INIT COLSPOT IDXREF DEFPIX INTEGRATE CORRECT
    params = {
        'cpu_count' int
        'wavelength': float
        'distance': float
        'starting_angle': float
        'starting_frame': int
        'oscillation_range': float
        'space_group': int
        'unit_cell' : tuple of 6 floats
        'reindex_matrix': tuple of 12 ints OR None
        'file_template': str (full/relative path including directory)
        'file_format': str (TIFF)
        'data_range' : tuple of 2 ints
        'spot_range' : list of (tuple of 2 ints)'s
        'detector_size': tuple of 2 ints
        'pixel_size' : tuple of 2 floats
        'detector_origin': tuple of 2 floats
        'min_spot_size': int or None
        'min_spot_seperation': int or None
        'cluster_radius': int or None
        'sigma': float or None default (6)
        'reference_data': filename OR None
        'shells': list of numbers or None
        'anomalous': True or False default False
    }
    
    """
    friedel = {
        True: 'FALSE',
        False: 'TRUE'
        }
    
    directory, xds_template = os.path.split(params['file_template'])
    # if template is longer calculate relative path:
    _file_template = params['file_template']
    if len(_file_template) > 50:
        try:
            rel_dir = os.path.relpath(directory)
            file_template = os.path.join(rel_dir, xds_template)
        except:
            pass
        
    # if template is still longer create symlink in tmp/xds:
    tmp_top = os.path.join(tempfile.gettempdir(), 'xds')
    if not os.path.exists(tmp_top):
        os.makedirs(tmp_top)
    if len(_file_template) > 50:
        tmp_dir = tempfile.mktemp(prefix='', dir=tmp_top)
        os.symlink(directory, tmp_dir)            
        _file_template = os.path.join(tmp_dir, xds_template)
    
    if params['detector_type'] in ['q4', 'q210','q4-2x','q210-2x','q315','q315-2x']:
        detector = 'ADSC'
    elif params['detector_type'] in ['mar165','mx300','mx300he','mar225','mar325']:
        detector = 'CCDCHESS'
    else:
        detector = 'CCDCHESS'
    
    
    file_text  = "!-XDS.INP-----------File generated by autoprocess \n"
    file_text += "JOB=%s \n" % ( jobs )
    file_text += "MAXIMUM_NUMBER_OF_PROCESSORS=%d \n" % max(1, params['cpu_count']/4)
    file_text += "MAXIMUM_NUMBER_OF_JOBS=%d \n" % max(2, params['cpu_count']/2)
    file_text += "MINUTE=0 \n"
    file_text += "!-------------------Dataset parameters------- \n"
    file_text += "X-RAY_WAVELENGTH=%7.5f \n" % (params['wavelength'])
    file_text += "DETECTOR_DISTANCE=%5.1f \n" % (params['distance'])
    file_text += "STARTING_ANGLE=%5.1f \n" % (params['starting_angle'])
    file_text += "STARTING_FRAME=%5d \n" % (params['starting_frame'])
    file_text += "OSCILLATION_RANGE=%3.2f \n" % (params['oscillation_range'])
    file_text += "SPACE_GROUP_NUMBER=%d \n" % (params['space_group'])
    file_text += "UNIT_CELL_CONSTANTS=%6.2f %6.2f %6.2f %4.2f %4.2f %4.2f \n" % params['unit_cell']
    
    if params['reindex_matrix'] is not None:
        file_text += "REIDX=%2d %2d %2d %2d %2d %2d %2d %2d %2d %2d %2d %2d\n" % (params['reindex_matrix'])
        
    file_text += "NAME_TEMPLATE_OF_DATA_FRAMES=%s\n" % (_file_template)
    file_text += "DATA_RANGE=%d %d \n" % (params['data_range'][0], params['data_range'][1])
    
    for r_s, r_e in params['spot_range']:
        file_text += "SPOT_RANGE=%d %d \n" % (r_s, r_e)

    reference = params.get('reference_data')
    if reference:
        file_text += "REFERENCE_DATA_SET=%s \n" %(params['reference_data'])
                
    file_text += "!-------------------Beamline parameters-----  \n"
    file_text += "NX=%d    NY=%d  \n" % (params['detector_size'][0], params['detector_size'][1])
    file_text += "QX=%7.5f QY=%7.5f  \n" % (params['pixel_size'][0], params['pixel_size'][1])
    file_text += "ORGX=%d  ORGY=%d \n" %(params['detector_origin'][0], params['detector_origin'][1])
    file_text += """
    DETECTOR=%s
    MINIMUM_VALID_PIXEL_VALUE= 0
    MIN_RFL_Rmeas= 30
    STRONG_PIXEL= %0.1f
    OVERLOAD=65000
    MINIMUM_ZETA= 0.075
    TRUSTED_REGION=0.00 1.25
    TOTAL_SPINDLE_ROTATION_RANGES= 10 180 10
    STARTING_ANGLES_OF_SPINDLE_ROTATION= 0 180 5
    VALUE_RANGE_FOR_TRUSTED_DETECTOR_PIXELS= 6000 30000
    INCLUDE_RESOLUTION_RANGE=50.0 0.0
    ROTATION_AXIS= 1.0 0.0 0.0
    INCIDENT_BEAM_DIRECTION=0.0 0.0 1.0
    FRACTION_OF_POLARIZATION=0.95
    POLARIZATION_PLANE_NORMAL= 1.0 0.0 0.0
    DIRECTION_OF_DETECTOR_X-AXIS= 1.000 0.000 0.000
    DIRECTION_OF_DETECTOR_Y-AXIS= 0.000 %0.3f %0.3f
    !AIR=%0.5f \n""" % (detector, params.get('sigma', 3),
                       math.cos(params['two_theta']), 
                       -1 * math.sin(params['two_theta']), 
                       utils.air(params['wavelength']) )
    if params.get('min_spot_separation') is not None:
        file_text +='    SEPMIN= %d \n' % params['min_spot_separation']
    if params.get('min_spot_size') is not None:
        file_text +='    MINIMUM_NUMBER_OF_PIXELS_IN_A_SPOT= %d \n' % params['min_spot_size']
    if params.get('cluster_radius') is not None:
        file_text +='    CLUSTER_RADIUS= %d \n' % params['min_spot_size']
    if params.get('shells') is not None:
        shells = map(lambda x:'%0.2f' % x, params['shells'])
        file_text +='    RESOLUTION_SHELLS= %s\n' % ' '.join(shells)
    
    file_text += "    FRIEDEL'S_LAW=%s\n" % (friedel[ params.get('anomalous', False) ])
    file_text += "!-------------------File generated by autoprocess \n"
    try:
        outfile = open('XDS.INP','w')
    except IOError, eStr:
        print "ERROR: Cannot open XDS.INP for writing: ", eStr

    outfile.write(file_text)
    outfile.close()

def write_xscale_input(params):
    """
    Create XSCALE.INP file using parameters in the dictionary params
    
    params = {
        'cpu_count': int
        'space_group': int
        'unit_cell': tuple of 6 floats
        'sections' : list of [ {
            'anomalous': bool
            'output_file': str
            'crystal': str
            'inputs': list of [{'input_file': str, 'resolution': float}]
        }]
    }
    
    """   
     
    friedel = {
        True: 'FALSE',
        False: 'TRUE'
        }
        
    file_text  = "!-XSCALE.INP--------File generated by autoxds \n"
    file_text += "MAXIMUM_NUMBER_OF_PROCESSORS=%d \n" % params['cpu_count']
    if params.get('space_group') is not None and params.get('unit_cell') is not None:
        file_text += "SPACE_GROUP_NUMBER=%d \n" % ( params['space_group'])
        file_text += "UNIT_CELL_CONSTANTS=%5.2f %5.2f %5.2f %4.2f %4.2f %4.2f \n" % params['unit_cell']
   
    for section in params['sections']:
        file_text += "OUTPUT_FILE=%s\n" % section['output_file']
        file_text += "FRIEDEL'S_LAW=%s\n" % (friedel[ section['anomalous'] ])
        for input in section['inputs']:
            file_text += "INPUT_FILE= %s  XDS_ASCII \n" % input['input_file']
            file_text += "INCLUDE_RESOLUTION_RANGE= 50 %5.2f\n" % input['resolution']
            if section.get('crystal', 'crystal1'):
                file_text += "CRYSTAL_NAME=%s\n" % (section['crystal'])
    file_text += "!-------------------File generated by autoxds \n"
    try:
        outfile = open('XSCALE.INP','w')
    except IOError, eStr:
        print "ERROR: Cannot open XSCALE.INP for writing: ", eStr

    outfile.write(file_text)
    outfile.close()

def write_xdsconv_input(params):
    """
    Create XDSCONV.INP file using parameters in the dictionary params
    
    params = {
        'space_group': int
        'unit_cell': tuple of 6 floats
        'anomalous': bool
        'format' : str
        'input_file': str
        'output_file' : str
        'freeR_fraction': float 0.0 < x < 1.0
    }
    
    """
       
    friedel = {True: 'FALSE', False: 'TRUE'}

    file_text  = "!-XDSCONV.INP--------File generated by autoxds \n"
    file_text += "SPACE_GROUP_NUMBER=%d \n" % (params['space_group'])
    file_text += "INPUT_FILE= %s  XDS_ASCII\n" % params['input_file']
    #file_text += "INCLUDE_RESOLUTION_RANGE= 40 %5.2f\n" % (params['resolution'])
    file_text += "UNIT_CELL_CONSTANTS=%5.2f %5.2f %5.2f %4.2f %4.2f %4.2f \n" % params['unit_cell']
    file_text += "OUTPUT_FILE=%s %s\n" % (params['output_file'], params['format'])
    file_text += "FRIEDEL'S_LAW=%s\n" % (friedel[ params['anomalous'] ])
    file_text += "MERGE=TRUE\n"
    file_text += "GENERATE_FRACTION_OF_TEST_REFLECTIONS=%0.2f\n" % params['freeR_fraction']
    file_text += "!-------------------File generated by autoxds \n"
    try:
        outfile = open('XDSCONV.INP','w')
    except IOError, eStr:
        print "ERROR: Cannot open XDSCONV.INP for writing: ", eStr

    outfile.write(file_text)
    outfile.close()

def write_f2mtz_input(params):
    """
    Create F2MTZ.INP file using parameters in the dictionary params
    
    params = {
        'output_file' : str
    }
    """
    
    file_text = "#!/bin/csh \n"
    file_text += "f2mtz HKLOUT temp.mtz < F2MTZ.INP\n"
    file_text += "cad HKLIN1 temp.mtz HKLOUT %s <<EOF\n" % params['output_file']
    file_text += "LABIN FILE 1 ALL\n"
    file_text += "END\n"
    file_text += "EOF\n"
    file_text += "/bin/rm temp.mtz\n"
    try:
        outfile = open('f2mtz.com','w')
    except IOError, eStr:
        print "ERROR: Cannot open f2mtz.com for writing: ", eStr

    outfile.write(file_text)
    outfile.close()
