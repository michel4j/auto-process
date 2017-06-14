
import os
import sys
import fnmatch
import re
import numpy
import json
from scipy.ndimage import measurements
from scipy.ndimage import filters

from dpm.utils import misc
from dpm.libs.imageio import read_header, read_image
from dpm.utils.log import get_module_logger
import dpm.errors

_logger = get_module_logger(__name__)

def _all_files(root, patterns='*'):
    """ 
    Return a list of all the files in a directory matching the pattern
    
    """
    patterns = patterns.split(';')
    _, _, files = os.walk(root).next()
    sfiles = []
    for name in files:
        for pattern in patterns:
            if fnmatch.fnmatch(name,pattern):
                sfiles.append(name)
    sfiles.sort()
    return sfiles

def detect_beam_peak(filename):
    img_info =read_image(filename)
    img = img_info.image
    img_array = numpy.fromstring(img.tostring(), numpy.uint32)
    img_array.shape = img.size[1], img.size[0]
      
    # filter the array so that features less than 8 pixels wide are blurred out
    # assumes that beam center is at least 8 pixels wide
    arr = filters.gaussian_filter(img_array, 8)
    beam_y, beam_x = measurements.maximum_position(arr)
    
    # valid beam centers must be within the center 1/5 region of the detector surface
    shape = img_array.shape
    cmin = [2 * v/5 for v in shape]
    cmax = [3 * v/5 for v in shape]
    good = False
    if cmin[0] < beam_y < cmax[0] and cmin[1] < beam_x < cmax[1]:
        good = True
        
    return beam_x, beam_y, good
    


def get_parameters(img_file):
    """ 
    Determine parameters for the data set represented by img_fiile
    returns a dictionary of results
    
    """
    directory, filename = os.path.split(os.path.abspath(img_file))

    file_pattern = re.compile('^(?P<base>.+_)(?P<num>\d{3,6})(?P<ext>\.?[\w.]+)?$')
    fm = file_pattern.match(filename)
    if fm:
        if fm.group('ext') is not None:
            extension = fm.group('ext')
        else:
            extension = ''
        filler = '?' * len(fm.group('num'))
        xds_template = "%s%s%s" % (fm.group('base'), filler, extension)
    else:
        _logger.error("Filename `%s` not recognized as dataset." % filename)
        raise dpm.errors.DatasetError('Filename not recognized')
        
    file_list = list( _all_files(directory, xds_template) )
    frame_count = len(file_list)
    if frame_count == 0:
        _logger.error("Dataset not found")
        raise dpm.errors.DatasetError('Dataset not found')
        
    fm = file_pattern.search(file_list[0])
    first_frame = int (fm.group('num'))
    _dataset_name = fm.group('base')
    if _dataset_name[-1] in ['_', '.', '-']:
        _dataset_name = _dataset_name[:-1]    
    
    _overwrite_beam = False
    if first_frame == 0: 
        first_frame = 1
        _ow_beam_x, _ow_beam_y, _overwrite_beam = detect_beam_peak(os.path.join(directory, file_list[0]))
        if _overwrite_beam:
            _logger.info('%s: New beam origin from frame 000 [%d, %d].' % (_dataset_name, _ow_beam_x, _ow_beam_y))
        file_list = file_list[1:]
        frame_count = len(file_list) 
        
    reference_image = os.path.join(directory, file_list[0])
    if not (os.path.isfile(reference_image) and os.access(reference_image, os.R_OK)):
        _logger.info("File '%s' not found, or unreadable." % reference_image)
        sys.exit(1)
                
    info = read_header(reference_image)
    info['energy'] = misc.wavelength_to_energy(info['wavelength'])
    info['first_frame'] = first_frame
    info['frame_count'] = frame_count
    info['name'] = _dataset_name
    info['file_template'] = os.path.join(directory, xds_template)        
    if _overwrite_beam:
        info['beam_center'] = (_ow_beam_x, _ow_beam_y)
    
    # Generate a list of wedges. each wedge is a tuple. The first value is the
    # first frame number and the second is the number of frames in the wedge
    wedges = []
    _wedge = [0,0]
    for i, f in enumerate(file_list):
        _fm = file_pattern.match(f)
        _fn = int(_fm.group('num'))
        _frame = (f, _fn)
        if i == 0:
            _wedge = [_fn, 1]
        else:
            if (_wedge[0] + _wedge[1]) == _fn:
                _wedge[1] += 1
            else:
                if (_wedge[1]) > 0:
                    wedges.append(_wedge)
                    _wedge = [_fn, 1]
    if (_wedge[0]) > 0:
        wedges.append(_wedge)

    # determine spot ranges from wedges
    # up to 4 degrees per wedge starting at 0 and 45 and 90

    spot_range = []
    _spot_span = int(4.0//info['delta_angle']) # frames in 4 deg
    _first_wedge = wedges[0]
    
    for _ang in [0.0, 45.0, 90.0]:
        _rs = _first_wedge[0] + int(_ang//info['delta_angle'])
        _re = _rs + _spot_span
        _exp_set  = set(range(_rs, _re))
        for wedge in wedges:
            _obs_set = set(range(wedge[0], wedge[0] + wedge[1]))
            _range = (_exp_set & _obs_set)
            if len(_range) > 0:
                spot_range.append((min(_range), max(_range)))
    last_frame = wedges[-1][0] + wedges[-1][1] - 1

    missing = []
    for i, wedge in enumerate(wedges):
        if i > 0:
            _re = wedge[0]-1
            missing.append([_rs, _re])
        _rs = wedge[0] + wedge[1]

    biggest_wedge = sorted(wedges, key=lambda x: x[1], reverse=True)[0]

    info['spot_range'] = spot_range
    info['data_range'] = (first_frame, last_frame)
    info['reference_image'] = reference_image
    info['background_range'] = (biggest_wedge[0], biggest_wedge[0] + min(10, biggest_wedge[1]) - 1)
    info['skip_range'] = missing
    info['max_delphi'] = info['delta_angle'] * biggest_wedge[1]
    return info

