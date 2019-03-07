import fnmatch
import os
import re
import sys
import glob

import numpy
from scipy.ndimage import filters
from scipy.ndimage import measurements

import autoprocess.errors
from autoprocess.libs.imageio import read_header, read_image
from autoprocess.utils import misc
from autoprocess.utils.log import get_module_logger

logger = get_module_logger(__name__)


def _all_files(root, patterns='*'):
    """ 
    Return a list of all the files in a directory matching the pattern
    
    """
    patterns = patterns.split(';')
    _, _, files = os.walk(root).next()
    sfiles = []
    for name in files:
        for pattern in patterns:
            if fnmatch.fnmatch(name, pattern):
                sfiles.append(name)
    sfiles.sort()
    return sfiles


def detect_beam_peak(filename):
    img_info = read_image(filename)
    img = img_info.image
    img_array = numpy.fromstring(img.tostring(), numpy.uint32)
    img_array.shape = img.size[1], img.size[0]

    # filter the array so that features less than 8 pixels wide are blurred out
    # assumes that beam center is at least 8 pixels wide
    arr = filters.gaussian_filter(img_array, 8)
    beam_y, beam_x = measurements.maximum_position(arr)

    # valid beam centers must be within the center 1/5 region of the detector surface
    shape = img_array.shape
    cmin = [2 * v / 5 for v in shape]
    cmax = [3 * v / 5 for v in shape]
    good = False
    if cmin[0] < beam_y < cmax[0] and cmin[1] < beam_x < cmax[1]:
        good = True

    return beam_x, beam_y, good

def import_parameters(inp_file):
    with open(inp_file, 'r') as handle:
        data = handle.read()
        file_template = re.findall('^NAME_TEMPLATE_OF_DATA_FRAMES=(.+)$', data, re.MULTILINE)[0]
    img_file = glob.glob(file_template)[0]
    return get_parameters(img_file)


def summarize_list(full_frame_set):
    # takes a list of integers such as [1,2,3,4,6,7,8]
    # and reduces it to the string [(1,4),(6,8)]
    sum_list = []
    tmp_pairs = []
    full_set = list(set(full_frame_set))

    if len(full_set) == 0:
        return ""
    full_set.sort()
    cur = full_set.pop(0)
    tmp_pairs.append([cur, cur])
    while len(full_set) > 0:
        cur = full_set.pop(0)
        last_pair = tmp_pairs[-1]
        if (cur - last_pair[-1]) == 1:
            last_pair[-1] = cur
        else:
            tmp_pairs.append([cur, cur])

    return tmp_pairs


def summarize_gaps(frame_list):
    # takes a list of integers such as [1,2,3,4,7,8]
    # and reduces it to the string of skipped regions such as "[(5,6)]"

    complete_set = set(range(1, max(frame_list) + 1))
    frame_set = set(frame_list)
    full_set = list(complete_set.difference(frame_set))
    return summarize_list(full_set)


def get_parameters(img_file):
    """ 
    Determine parameters for the data set represented by img_fiile
    returns a dictionary of results
    
    """
    data = read_image(os.path.abspath(img_file))

    if not data.header['dataset'] or len(data.header['dataset']['sequence']) == 0:
        logger.error("Dataset not found")
        raise autoprocess.errors.DatasetError('Dataset not found')

    reference_image = data.header['dataset']['name'].format(data.header['dataset']['sequence'][0])
    if not (os.path.isfile(reference_image) and os.access(reference_image, os.R_OK)):
        logger.info("File '%s' not found, or unreadable." % reference_image)
        sys.exit(1)

    data = read_image(reference_image)
    info = data.header
    info['energy'] = misc.wavelength_to_energy(info['wavelength'])
    info['first_frame'] = info['dataset']['sequence'][0]
    info['frame_count'] = info['dataset']['sequence'][-1]
    info['name'] = info['dataset']['label']
    info['file_template'] = os.path.join(info['dataset']['directory'], info['dataset']['template'])

    # Generate a list of wedges. each wedge is a tuple. The first value is the
    # first frame number and the second is the number of frames in the wedge
    wedges = summarize_list(info['dataset']['sequence'])

    # determine spot ranges from wedges
    # up to 4 degrees per wedge starting at 0 and 45 and 90
    spot_range = []
    spot_span = int(4.0 // info['delta_angle'])  # frames in 4 deg
    first_wedge = wedges[0]

    for _ang in [0.0, 45.0, 90.0]:
        _rs = first_wedge[0] + int(_ang // info['delta_angle'])
        _re = _rs + spot_span
        _exp_set = set(range(_rs, _re))
        for wedge in wedges:
            _obs_set = set(range(wedge[0], wedge[0] + wedge[1]))
            _range = (_exp_set & _obs_set)
            if len(_range) > 0:
                spot_range.append((min(_range), max(_range)))

    biggest_wedge = sorted(wedges, key=lambda x: x[1], reverse=True)[0]

    info['spot_range'] = spot_range
    info['data_range'] = info['dataset']['sequence'][0], info['dataset']['sequence'][-1]
    info['reference_image'] = reference_image
    info['background_range'] = (biggest_wedge[0], biggest_wedge[0] + min(10, biggest_wedge[1]) - 1)
    info['skip_range'] = summarize_gaps(info['dataset']['sequence'])
    info['max_delphi'] = info['delta_angle'] * biggest_wedge[1]
    return info
