import copy

import numpy

CALIB_TEMPLATE = """POWDER DIFFRACTION (2-D)
INPUT
{file_name}
O.K.
O.K.
TILT
X-PIXEL SIZE
{pixel_size:0.4f}
Y-PIXEL SIZE
{pixel_size:0.4f}
DISTANCE
{distance:0.4f}
WAVELENGTH
{wavelength:0.6f}
X-BEAM CENTRE
{beam_x:0.3f}
Y-BEAM CENTRE
{beam_y:0.3f}
TILT ROTATION
0
ANGLE OF TILT
0
DETECTOR ROTATION
0.0
O.K.
O.K.
ELLIPSE COORDINATES
{coordinates}
1
INTEGRATE
O.K.
GEOMETRY COR. 
YES
CONSERVE INT.
{intensity}
MAX. ANGLE
{max_angle:0.2f}
O.K.
OUTPUT
CHIPLOT
FILE NAME
{data_name}.chi
O.K.
EXIT
SET-UP
SAVE FIT2D DEFAULTS
{db_file}
EXIT
EXIT FIT2D
YES
"""

INTEGRATE_TEMPLATE = """
SET-UP
LOAD FIT2D DEFAULTS
{db_file}
EXIT
POWDER DIFFRACTION (2-D)
INPUT
{file_name}
O.K.
O.K.
INTEGRATE
X-PIXEL SIZE
{pixel_size:0.4f}
Y-PIXEL SIZE
{pixel_size:0.4f}
DISTANCE
{distance:0.4f}
WAVELENGTH
{wavelength:0.6f}
O.K.
CONSERVE INT.
{intensity}
MAX. ANGLE
{max_angle:0.2f}
O.K.
OUTPUT
CHIPLOT
FILE NAME
{data_name}.chi
O.K.
EXIT
EXIT FIT2D
YES
"""


def write_calib_macro(parameters, macro_file='macro.mac'):
    """
    Create calib macro file for fit2d
    params = {
        'wavelength': float
        'distance': float
        'start_angle': float
        'first_frame': int
        'file_name': str (full/relative path including directory)
        'file_format': str (TIFF)
        'detector_size': tuple of 2 ints
        'pixel_size' : float
        'beam_center': tuple of 2 floats
        'ellipse': [(x1,y1), (x2,y2), ..., ]
        'rings': [(x1,y1), (x2,y2), ..., ]
        'ring_width': integer,
        'db_file': file path for defaults, will be overwritten
    }
    """

    # Fix Fit2D geometry
    max_x = max(
        parameters['detector_size'][0] - parameters['beam_center'][0],
        parameters['beam_center'][0],
    )
    max_y = max(
        parameters['detector_size'][1] - parameters['beam_center'][1],
        parameters['beam_center'][1],
    )
    max_r = 0.99 * numpy.sqrt(max_y ** 2 + max_x ** 2) * parameters['pixel_size']
    max_angle = numpy.degrees(numpy.arctan(max_r / parameters['distance']))

    params = copy.deepcopy(parameters)
    params.update({
        'beam_x': params['beam_center'][0],
        'beam_y': params['detector_size'][1] - params['beam_center'][1],
        'rings': [(x, params['detector_size'][1] - y) for x, y in params['rings']],
        'ellipse': [(x, params['detector_size'][1] - y) for x, y in params['ellipse']],
        'pixel_size': 1000 * params['pixel_size'],
        'intensity': 'YES' if params.get('intensity') else 'NO',
        'max_angle': max_angle
    })

    coords_text = [
                      '{:12d}'.format(len(params['ellipse']))
                  ] + [
                      '{:14.7E}\n{:14.7E}'.format(x, y) for x, y in params['ellipse']
                  ] + [
                      '{:12d}'.format(1),
                      '{:14.7E}\n{:14.7E}'.format(params['ellipse'][0][0] + params['ring_width'],
                                                  params['ellipse'][0][1] + params['ring_width']),
                      '{}'.format(len(params['rings'])),
                  ] + [
                      '{:14.7E}\n{:14.7E}'.format(x, y) for x, y in params['rings']
                  ]

    params['coordinates'] = '\n'.join(coords_text)
    macro = CALIB_TEMPLATE.format(**params)

    with open(macro_file, 'w') as outfile:
        outfile.write(macro)


def write_integrate_macro(parameters, macro_file='integrate.mac'):
    """
    Create calib macro file for fit2d
    params = {
        'wavelength': float
        'distance': float
        'start_angle': float
        'first_frame': int
        'file_name': str (full/relative path including directory)
        'file_format': str (TIFF)
        'detector_size': tuple of 2 ints
        'pixel_size' : float
        'beam_center': tuple of 2 floats
        'ellipse': [(x1,y1), (x2,y2), ..., ]
        'rings': [(x1,y1), (x2,y2), ..., ]
        'ring_width': integer,
        'intensity': bool (preserve intensities?),
        'db_file': file path for defaults
    }
    """

    # Fix Fit2D geometry
    max_x = max(
        parameters['detector_size'][0] - parameters['beam_center'][0],
        parameters['beam_center'][0],
    )
    max_y = max(
        parameters['detector_size'][1] - parameters['beam_center'][1],
        parameters['beam_center'][1],
    )
    max_r = 0.99 * numpy.sqrt(max_y ** 2 + max_x ** 2) * parameters['pixel_size']
    max_angle = numpy.degrees(numpy.arctan(max_r / parameters['distance']))

    params = copy.deepcopy(parameters)
    params.update({
        'beam_x': params['beam_center'][0],
        'beam_y': params['detector_size'][1] - params['beam_center'][1],
        'pixel_size': 1000 * params['pixel_size'],
        'intensity': 'YES' if params.get('intensity') else 'NO',
        'max_angle': max_angle
    })

    macro = INTEGRATE_TEMPLATE.format(**params)

    with open(macro_file, 'w') as outfile:
        outfile.write(macro)
