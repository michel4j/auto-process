
import os
import sys
import fnmatch
import shutil
import re

from dpm.utils import units
from dpm.utils import peaks
from bcm.utils.imageio import read_header
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

def get_parameters(img_file):
    """ 
    Determine parameters for the data set represented by img_fiile
    returns a dictionary of results
    
    """
    directory, filename = os.path.split(os.path.abspath(img_file))

    file_pattern = re.compile('^(?P<base>[\w-]+\.?)(?<!\d)(?P<num>\d{3,4})(?P<ext>\.?[\w.]+)?$')
    fm = file_pattern.match(filename)
    if fm:
        if fm.group('ext') is not None:
            extension = fm.group('ext')
        else:
            extension = ''
        filler = '?' * len(fm.group('num'))
        xds_template = "%s%s%s" % (fm.group('base'), filler, extension)
    else:
        _logger.error("File `%s` is not recognized as a standard dataset filename." % filename)
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
        _ow_beam_x, _ow_beam_y, _overwrite_beam = peaks.detect_beam_peak(os.path.join(directory, file_list[0]))
        if _overwrite_beam:
            _logger.info('%s: direct beam file found. New beam center [%d, %d].' % (_dataset_name, _ow_beam_x, _ow_beam_y))
        file_list = file_list[1:]
        frame_count = len(file_list) 
        
    reference_image = os.path.join(directory, file_list[0])
    if not (os.path.isfile(reference_image) and os.access(reference_image, os.R_OK)):
        _logger.info("File '%s' does not exist, or is not readable." % reference_image)
        sys.exit(1)
                
    info = read_header(reference_image)
    info['energy'] = units.wavelength_to_energy(info['wavelength'])
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
    info['spot_range'] = spot_range
    info['data_range'] = (first_frame, last_frame)
    info['reference_image'] = reference_image
            
    return info


def prepare_dir(workdir, backup=False):
    """ 
    Creates a work dir for autoprocess to run. Increments run number if 
    directory already exists.
    
    """
    
    exists = os.path.isdir(workdir)
    if not exists:
        os.makedirs(workdir)
    elif backup:
        count = 0
        while exists:
            count += 1
            bkdir = "%s.%02d" % (workdir, count)
            exists = os.path.isdir(bkdir)
        shutil.move(workdir, bkdir)
        os.makedirs(workdir)

