"""
Input/Output routines for XDS and file conversion utilities

"""

import os

import numpy
import multiprocessing
from autoprocess.utils import misc

DEFAULT_DELPHI = 8
if os.environ.get('DPS_NODES'):
    HOSTS = {
        x.split(':')[0]: int(x.split(':')[1]) for x in os.environ['DPS_NODES'].split()
    }
else:
    HOSTS = {
        'localhost': multiprocessing.cpu_count()
    }


def closest_factor(val, root):
    x = int(val)
    if x == 0:
        return 1
    for i in range(x):
        if root % (x + i) == 0:
            return x + i
        elif root % (x - i) == 0:
            return x - i
    return x


def get_job_params(num_frames, delta, delphi=DEFAULT_DELPHI):
    nodes = len(HOSTS)
    cores = sum(HOSTS.values())
    max_cpus = misc.get_cpu_count()
    raw_batch_size = (delphi / delta)
    batch_size = closest_factor(raw_batch_size, max_cpus)
    delphi = batch_size * delta
    max_jobs = cores // batch_size

    return max(1, max_jobs // 2), batch_size, delphi


def write_xds_input(jobs, parameters):
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
    # defaults
    params = {
        'refine_index': 'CELL BEAM ORIENTATION AXIS',
        'refine_integrate': 'DISTANCE POSITION BEAM ORIENTATION'
    }
    params.update(parameters)
    params['min_valid_value'] = 1
    params['profile_grid_size'] = 13

    if params.get('detector_type').lower() in ['q4', 'q210', 'q4-2x', 'q210-2x', 'q315', 'q315-2x']:
        detector = 'ADSC'
    elif params.get('detector_type').lower() in ['mar165', 'mx300', 'mx300he', 'mar225', 'mar325']:
        detector = 'CCDCHESS'

    elif 'pilatus' in params.get('detector_type').lower():
        detector = 'PILATUS'
        params['min_spot_size'] = 3
        params['fixed_scale_factor'] = True
        params['min_valid_value'] = 0
        params['saturated_value'] = 1048500
        params['sensor_thickness'] = 1.0
    elif 'eiger' in params.get('detector_type').lower():
        detector = 'EIGER'
        params['min_spot_separation'] = 4
        params['cluster_radius'] = 2
        params['min_valid_value'] = 0
        # params['untrusted'] = [
        #     (0, 4150, 513, 553),
        #     (0, 4150, 1064, 1104),
        #     (0, 4150, 1615, 1655),
        #     (0, 4150, 2166, 2206),
        #     (0, 4150, 2717, 2757),
        #     (0, 4150, 3268, 3308),
        #     (0, 4150, 3819, 3859),
        #     (1029, 1042, 0, 4371),
        #     (2069, 2082, 0, 4371),
        #     (3109, 3122, 0, 4371),
        # ]

    else:
        detector = 'CCDCHESS'

    num_frames = params['data_range'][1] - params['data_range'][0] + 1
    num_jobs, batch_size, delphi = get_job_params(
        num_frames, params['delta_angle'], min(params.get('max_delphi', 8), DEFAULT_DELPHI)
    )
    params['jobs'] = jobs
    params['detector'] = detector
    params['sensor_thickness'] = params.get('sensor_thickness', 0.0)
    params['num_jobs'] = num_jobs
    params['batch_size'] = batch_size
    params['delphi'] = delphi
    params['cluster_nodes'] = ' '.join(list(HOSTS.keys()))
    params['sigma'] = params.get('sigma', 4)
    params['friedel'] = str(not params.get('anomalous', False)).upper()
    params['space_group'] = params.get('reference_spacegroup', params.get('space_group', 0))
    params['resolution'] = params.get('resolution', 1.0)
    params['detector_yaxis'] = (
        0.0,
        numpy.cos(numpy.radians(params['two_theta'])),
        -1 * numpy.sin(numpy.radians(params['two_theta']))
    )
    job_text = (
        "!- XDS.INP ----------- Generated by AutoProcess\n"
        "JOB=   {jobs}\n"
        "CLUSTER_NODES= {cluster_nodes}\n"
    ).format(**params)

    dataset_text = (
        "!------------------- Dataset parameters\n"
        "X-RAY_WAVELENGTH=  {wavelength:7.5f}\n"
        "DETECTOR_DISTANCE= {distance:5.1f}\n"
        "STARTING_ANGLE=    {start_angle:5.1f}\n"
        "STARTING_FRAME=    {start_angle}\n"
        "OSCILLATION_RANGE= {delta_angle:4.2f}\n"
        "NAME_TEMPLATE_OF_DATA_FRAMES={file_template}\n"
        "FRIEDEL'S_LAW= {friedel}\n"
        "DATA_RANGE=    {data_range[0]} {data_range[1]}\n"
        "DELPHI=    {delphi:4.2f} \n"
    ).format(**params)

    for r_s, r_e in params.get('skip_range', []):
        dataset_text += "EXCLUDE_DATA_RANGE=    {} {}\n".format(r_s, r_e)

    for r_s, r_e in params['spot_range']:
        dataset_text += "SPOT_RANGE=    {} {}\n".format(r_s, r_e)

    if params.get('background_range'):
        dataset_text += "BACKGROUND_RANGE=  {background_range[0]} {background_range[1]}\n".format(**params)

    if params.get('space_group'):
        # space group and cell parameters
        dataset_text += (
            "SPACE_GROUP_NUMBER=    {space_group}\n"
            "UNIT_CELL_CONSTANTS=   {unit_cell[0]:0.3f} {unit_cell[1]:0.3f} {unit_cell[2]:0.3f} "
            "{unit_cell[3]:0.3f} {unit_cell[4]:0.3f} {unit_cell[5]:0.3f}\n"
        ).format(space_group=params['space_group'], unit_cell=params['unit_cell'])

        # reindexing matrix
        if params.get('reindex_matrix'):
            dataset_text += "REIDX={} {} {} {} {} {} {} {} {} {} {} {}\n".format(*params['reindex_matrix'])

    # reference data
    if params.get('reference_data'):
        dataset_text += "REFERENCE_DATA_SET=    {reference_data}\n".format(**params)

    beamline_text = (
        "!----------------- Beamline parameters\n"
        "DETECTOR= {detector}\n"
        "NX={detector_size[0]}    NY= {detector_size[1]}\n"
        "QX={pixel_size:7.5f} QY={pixel_size:7.5f}\n"
        "ORGX={beam_center[0]:5.0f}  ORGY={beam_center[1]:5.0f}\n"
        "SENSOR_THICKNESS= {sensor_thickness:0.3f}\n"
        "MINIMUM_VALID_PIXEL_VALUE= {min_valid_value}\n"
        "OVERLOAD= {saturated_value}\n"
        "STRONG_PIXEL= {sigma:5.0f}\n"
        "MINIMUM_ZETA= 0.05\n"
        "TRUSTED_REGION=0.00 1.2\n"
        "TEST_RESOLUTION_RANGE= 50.0 1.0\n"
        "RESOLUTION_SHELLS= {resolution:5.2f}\n"
        "TOTAL_SPINDLE_ROTATION_RANGES= 90 360 30\n"
        "STARTING_ANGLES_OF_SPINDLE_ROTATION= 0 180 15\n"
        "VALUE_RANGE_FOR_TRUSTED_DETECTOR_PIXELS= 6000 30000\n"
        "INCLUDE_RESOLUTION_RANGE=50.0 0.0\n"
        "ROTATION_AXIS= 1.0 0.0 0.0\n"
        "INCIDENT_BEAM_DIRECTION=0.0 0.0 1.0\n"
        "FRACTION_OF_POLARIZATION=0.99\n"
        "POLARIZATION_PLANE_NORMAL= 0.0 1.0 0.0\n"
        "DIRECTION_OF_DETECTOR_X-AXIS= 1.000 0.000 0.000\n"
        "DIRECTION_OF_DETECTOR_Y-AXIS= {detector_yaxis[0]:0.3f} {detector_yaxis[1]:0.3f} {detector_yaxis[2]:0.3f}\n"

    ).format(**params)

    extra_text = "!----------------- Extra parameters\n"
    if params.get('min_spot_separation'):
        extra_text += 'SEPMIN= {min_spot_separation}\n'
    if params.get('min_spot_size'):
        extra_text += 'MINIMUM_NUMBER_OF_PIXELS_IN_A_SPOT= {min_spot_size}\n'
    if params.get('cluster_radius'):
        extra_text += 'CLUSTER_RADIUS= {cluster_radius}\n'
    if params.get('shells'):
        extra_text += 'RESOLUTION_SHELLS= {}\n'.format(' '.join(['{:0.2f}'.format(x) for x in params['shells']]))
    if params.get('strict_correction'):
        extra_text += 'STRICT_ABSORPTION_CORRECTION= {}\n'.format(str(params.get('strict_absorption', False)).upper())
    if params.get('refine_index'):
        extra_text += 'REFINE(IDXREF)= {refine_index}\n'
    if params.get('refine_integrate'):
        extra_text += 'REFINE(INTEGRATE)= {refine_integrate}\n'
    if params.get('profile_grid_size'):
        extra_text += 'NUMBER_OF_PROFILE_GRID_POINTS_ALONG_ALPHA/BETA= {profile_grid_size}\n'
    if params.get('fixed_scale_factor'):
        extra_text += 'DATA_RANGE_FIXED_SCALE_FACTOR= {data_range[0]} {data_range[1]} 1.0\n'
    for rectangle in params.get('untrusted', []):
        extra_text += 'UNTRUSTED_RECTANGLE= {} {} {} {}\n'.format(*rectangle)
    extra_text = extra_text.format(**params)

    with open('XDS.INP', 'w') as outfile:
        outfile.write(job_text)
        outfile.write(dataset_text)
        outfile.write(beamline_text)
        outfile.write(extra_text)


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

    header = "!-XSCALE.INP--------File generated by auto.process \n"
    header += "MAXIMUM_NUMBER_OF_PROCESSORS=%d \n" % misc.get_cpu_count()

    body = ""
    shells = []
    friedel = 'FALSE' if params['sections'][0].get('anomalous') else 'TRUE'
    strict_abs = 'TRUE' if params.get('strict_absorption', False) else 'FALSE'

    for i, section in enumerate(params['sections']):
        body += "OUTPUT_FILE={}\n".format(section['output_file'])
        if section.get('reindex_matrix'):
            body += "REIDX={:2d} {:2d} {:2d} {:2d} {:2d} {:2d} {:2d} {:2d} {:2d} {:2d} {:2d} {:2d}\n".format(*section['reindex_matrix'])
        if section.get('space_group') and section.get('unit_cell'):
            body += "SPACE_GROUP_NUMBER={:d} \n".format(section['space_group'])
            body += "UNIT_CELL_CONSTANTS={:6.2f} {:6.2f} {:6.2f} {:4.2f} {:4.2f} {:4.2f} \n".format(*section['unit_cell'])
        body += f"FRIEDEL'S_LAW={friedel}\n"
        body += f"STRICT_ABSORPTION_CORRECTION={strict_abs}\n"

        if i == 0:
            shells = section.get('shells')
        elif section.get('shells')[-1] < shells[-1]:
            shells = section.get('shells')

        for _input in section['inputs']:
            star = '*' if _input.get('reference', False) else ' '
            body += "INPUT_FILE={}{} \n".format(star, _input['input_file'])
            body += "INCLUDE_RESOLUTION_RANGE= 50 {:5.2f}\n".format(_input.get('resolution', 0))
            if section.get('crystal'):
                body += "CRYSTAL_NAME={}\n".format(section['crystal'])

    if shells:
        header += 'RESOLUTION_SHELLS= {}\n'.format(' '.join([f'{x:0.2f}' for x in shells]))

    file_text = header + body + "!-------------------File generated by auto.process \n"
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
