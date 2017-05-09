"""
Input/Output routines for XDS and file conversion utilities

"""
import math
import os

import numpy

from dpm.utils import misc

DEFAULT_DELPHI = 6.0

def closest_factor(val, root):
    x = int(val)
    if x == 0:
        return 1
    for i in range(x):
        if root % (x + i) == 0:
            return x + i
        elif root % (x-i) == 0:
            return x - i
    return x


def get_job_params(num_frames, delta, delphi=DEFAULT_DELPHI):
    max_cpus = misc.get_cpu_count()
    raw_batch_size = (delphi/delta)
    batch_size = closest_factor(raw_batch_size, max_cpus)
    delphi = batch_size * delta
    max_jobs = numpy.ceil(num_frames / float(batch_size))

    return max_jobs, batch_size, delphi


def write_xds_input(jobs, params):
    """
    Create XDS.INP file using parameters in the dictionary params
    jobs = XYCORR INIT COLSPOT IDXREF DEFPIX INTEGRATE CORRECT
    params = {
        'wavelength': float
        'distance': float
        'start_angle': float
        'first_frame': int
        'delta_angle': float
        'space_group': int
        'unit_cell' : tuple of 6 floats
        'reindex_matrix': tuple of 12 ints OR None
        'file_template': str (full/relative path including directory)
        'file_format': str (TIFF)
        'data_range' : tuple of 2 ints
        'spot_range' : list of (tuple of 2 ints)'s
        'skip_range' : list of (tuple of 2 ints)'s
        'detector_size': tuple of 2 ints
        'pixel_size' : float
        'two_theta': float
        'saturated_value': float
        'beam_center': tuple of 2 floats
        'min_spot_size': int or None
        'min_spot_seperation': int or None
        'cluster_radius': int or None
        'sigma': float or None default (6)
        'reference_data': filename OR None
        'shells': list of numbers or None
        'anomalous': True or False default False
        'strict_absorption': True or False default False
    }
    
    """
    friedel = {
        True: 'FALSE',
        False: 'TRUE'
    }

    directory, xds_template = os.path.split(params['file_template'])
    # if template is longer calculate relative path:
    _file_template = params['file_template']
    if len(_file_template) > 80:
        try:
            rel_dir = os.path.relpath(directory)
            _file_template = os.path.join(rel_dir, xds_template)
        except:
            pass

    if params.get('detector_type') in ['q4', 'q210', 'q4-2x', 'q210-2x', 'q315', 'q315-2x']:
        detector = 'ADSC'
    elif params.get('detector_type') in ['mar165', 'mx300', 'mx300he', 'mar225', 'mar325']:
        detector = 'CCDCHESS'
    elif params.get('detector_type') in ['PILATUS_6M', 'PILATUS3_6M', '6m']:
        detector = 'PILATUS'
        params['min_spot_size'] = numpy.ceil(params.get('min_spot_size', 9) / (params['pixel_size'] / .05))
    else:
        detector = 'CCDCHESS'

    num_frames = params['data_range'][1] - params['data_range'][0] + 1
    num_jobs, batch_size, delphi = get_job_params(
        num_frames, params['delta_angle'], min(params.get('max_delphi', 6), DEFAULT_DELPHI)
    )

    file_text = "!-XDS.INP-----------File generated by autoprocess \n"
    file_text += "JOB=%s \n" % (jobs)
    file_text += "MAXIMUM_NUMBER_OF_PROCESSORS=%d \n" % (batch_size)
    file_text += "MAXIMUM_NUMBER_OF_JOBS=%d \n" % num_jobs
    file_text += "!-------------------Dataset parameters------- \n"
    file_text += "X-RAY_WAVELENGTH=%7.5f \n" % (params['wavelength'])
    file_text += "DETECTOR_DISTANCE=%5.1f \n" % (params['distance'])
    file_text += "STARTING_ANGLE=%5.1f \n" % (params['start_angle'])
    file_text += "STARTING_FRAME=%5d \n" % (params['first_frame'])
    file_text += "OSCILLATION_RANGE=%3.2f \n" % (params['delta_angle'])
    file_text += "DELPHI=%3.2f \n" % (delphi)
    if params.get('space_group'):
        if params.get('reference_spacegroup') is not None:
            file_text += "SPACE_GROUP_NUMBER=%d \n" % (params['reference_spacegroup'])
        else:
            file_text += "SPACE_GROUP_NUMBER=%d \n" % (params['space_group'])
        file_text += "UNIT_CELL_CONSTANTS=%6.2f %6.2f %6.2f %4.2f %4.2f %4.2f \n" % tuple(
            params.get('unit_cell', (0, 0, 0, 0, 0, 0)))

    if params.get('reindex_matrix') is not None:
        file_text += "REIDX=%2d %2d %2d %2d %2d %2d %2d %2d %2d %2d %2d %2d\n" % tuple(params['reindex_matrix'])

    file_text += "NAME_TEMPLATE_OF_DATA_FRAMES=%s\n" % (_file_template)
    file_text += "DATA_RANGE=%d %d \n" % (params['data_range'][0], params['data_range'][1])
    for r_s, r_e in params.get('skip_range', []):
        file_text += "EXCLUDE_DATA_RANGE=%d %d \n" % (r_s, r_e)
    if params.get('background_range'):
        file_text += "BACKGROUND_RANGE={} {} \n".format(params['background_range'][0], params['background_range'][1])

    for r_s, r_e in params['spot_range']:
        file_text += "SPOT_RANGE=%d %d \n" % (r_s, r_e)

    if params.get('reference_data') is not None:
        file_text += "REFERENCE_DATA_SET=%s \n" % (params['reference_data'])

    file_text += "!-------------------Beamline parameters-----  \n"
    file_text += "NX=%d    NY=%d  \n" % (params['detector_size'][0], params['detector_size'][1])
    file_text += "QX=%7.5f QY=%7.5f  \n" % (params['pixel_size'], params['pixel_size'])
    file_text += "ORGX=%d  ORGY=%d \n" % (params['beam_center'][0], params['beam_center'][1])
    file_text += """
    DETECTOR=%s
    MINIMUM_VALID_PIXEL_VALUE= 1
    OVERLOAD=%d
    MINIMUM_ZETA= 0.05
    TRUSTED_REGION=0.00 1.414
    TEST_RESOLUTION_RANGE= 75.0 0.0
    TOTAL_SPINDLE_ROTATION_RANGES= 10 180 10
    STARTING_ANGLES_OF_SPINDLE_ROTATION= 0 180 5
    VALUE_RANGE_FOR_TRUSTED_DETECTOR_PIXELS= 6000 30000
    INCLUDE_RESOLUTION_RANGE=50.0 0.0
    ROTATION_AXIS= 1.0 0.0 0.0
    INCIDENT_BEAM_DIRECTION=0.0 0.0 1.0
    FRACTION_OF_POLARIZATION=0.95
    POLARIZATION_PLANE_NORMAL= 0.0 1.0 0.0
    DIRECTION_OF_DETECTOR_X-AXIS= 1.000 0.000 0.000
    DIRECTION_OF_DETECTOR_Y-AXIS= 0.000 %0.3f %0.3f
    \n""" % (detector,
             params.get('saturated_value', 65535),
             math.cos(params['two_theta']),
             -1 * math.sin(params['two_theta']))
    file_text += '    STRONG_PIXEL= %d \n' % params.get('sigma', 5)
    if params.get('min_spot_separation') is not None:
        file_text += '    SEPMIN= %d \n' % params['min_spot_separation']
    if params.get('min_spot_size') is not None:
        file_text += '    MINIMUM_NUMBER_OF_PIXELS_IN_A_SPOT= %d \n' % params['min_spot_size']
    if params.get('cluster_radius') is not None:
        file_text += '    CLUSTER_RADIUS= %d \n' % params['cluster_radius']
    if params.get('shells') is not None:
        shells = map(lambda x: '%0.2f' % x, params['shells'])
        file_text += '    RESOLUTION_SHELLS= %s\n' % ' '.join(shells)
    if params.get('strict_correction') is not None:
        file_text += '    STRICT_ABSORPTION_CORRECTION= %s\n' % (friedel[params.get('strict_absorption', False)])
    if params.get('sensor_thickness') is not None:
        file_text += '    SENSOR_THICKNESS= %0.3f \n' % params['sensor_thickness']
    if params.get('refine_index') is not None:
        file_text += '    REFINE(IDXREF)=%s\n' % params['refine_index']

    file_text += "    FRIEDEL'S_LAW=%s\n" % (friedel[params.get('anomalous', False)])
    file_text += "!-------------------File generated by auto.process \n"

    outfile = open('XDS.INP', 'w')

    outfile.write(file_text)
    outfile.close()


def write_xscale_input(params):
    """
    Create XSCALE.INP file using parameters in the dictionary params
    
    params = {
        'strict_absorption': True or False default False
        'sections' : list of [ {
            'reindex_matrix': tuple of 12 ints, optional
            'space_group': int, optional
            'unit_cell': tuple of 6 floats, optional
            'anomalous': bool
            'output_file': str
            'crystal': str
            'inputs': list of [{'input_file': str, 'resolution': float, 'reference':bool}]
        }]
    }
    
    """

    friedel = {
        True: 'FALSE',
        False: 'TRUE'
    }

    file_text = "!-XSCALE.INP--------File generated by auto.process \n"
    file_text += "MAXIMUM_NUMBER_OF_PROCESSORS=%d \n" % misc.get_cpu_count()

    for section in params['sections']:
        file_text += "OUTPUT_FILE=%s\n" % section['output_file']
        if section.get('reindex_matrix'):
            file_text += "REIDX=%2d %2d %2d %2d %2d %2d %2d %2d %2d %2d %2d %2d\n" % tuple(section['reindex_matrix'])
        if section.get('space_group') and section.get('unit_cell'):
            file_text += "SPACE_GROUP_NUMBER=%d \n" % (section['space_group'])
            file_text += "UNIT_CELL_CONSTANTS=%6.2f %6.2f %6.2f %4.2f %4.2f %4.2f \n" % tuple(section['unit_cell'])
        file_text += "FRIEDEL'S_LAW=%s\n" % (friedel[section.get('anomalous', False)])
        file_text += "STRICT_ABSORPTION_CORRECTION=%s\n" % (friedel[params.get('strict_absorption', False)])
        for _input in section['inputs']:
            if _input.get('reference', False):
                star = '*'
            else:
                star = ' '
            file_text += "INPUT_FILE=%c%s \n" % (star, _input['input_file'])
            file_text += "INCLUDE_RESOLUTION_RANGE= 50 %5.2f\n" % _input.get('resolution', 0)
            if section.get('crystal'):
                file_text += "CRYSTAL_NAME=%s\n" % (section['crystal'])
    file_text += "!-------------------File generated by auto.process \n"
    outfile = open('XSCALE.INP', 'w')

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

    file_text = "!-XDSCONV.INP--------File generated by auto.process \n"
    file_text += "INPUT_FILE= %s  XDS_ASCII\n" % params['input_file']
    file_text += "OUTPUT_FILE=%s %s\n" % (params['output_file'], params['format'])
    file_text += "FRIEDEL'S_LAW=%s\n" % (friedel[params['anomalous']])
    file_text += "MERGE=FALSE\n"
    if params['freeR_fraction'] > 0.0:
        file_text += "GENERATE_FRACTION_OF_TEST_REFLECTIONS=%0.2f\n" % params['freeR_fraction']
    file_text += "!-------------------File generated by auto.process \n"
    outfile = open('XDSCONV.INP', 'w')
    outfile.write(file_text)
    outfile.close()
