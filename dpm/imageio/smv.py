"""
MarCCD TIFF format readers

"""

import struct
import math
import re
def read_header(filename):
    """
    Read SMV image headers
    returns a dictionary of header parameters
    
    """
    info = {}
    
    myfile = open(filename,'r')
    raw = myfile.read(512)
    raw_entries = raw.split('\n')
    tmp_info = {}
    epat = re.compile('^(?P<key>[\w]+)=(?P<value>.+);')
    for line in raw_entries:
        m = epat.match(line)
        if m:
            tmp_info[m.group('key').lower()] = m.group('value').strip()
    # Read remaining header if any
    _header_size = int(tmp_info['header_bytes'])
    if _header_size > 512:
        raw = myfile.read(_header_size-512)
        raw_entries = raw.split('\n')
        for line in raw_entries:
            m = epat.match(line)
            if m:
                tmp_info[m.group('key').lower()] = m.group('value').strip()
    myfile.close()
        
    info['oscillation_range'] = float(tmp_info['osc_range'])
    info['distance']  = float(tmp_info['distance'])
    info['wavelength']  = float(tmp_info['wavelength'])
    info['exposure_time'] = float(tmp_info['time'])
    info['pixel_size'] = (float(tmp_info['pixel_size']), float(tmp_info['pixel_size']))
    orgx = float(tmp_info['beam_center_x'])/info['pixel_size'][0]
    orgy =float(tmp_info['beam_center_y'])/info['pixel_size'][1]
    info['detector_origin'] = (orgx, orgy)
    info['detector_size'] = (int(tmp_info['size1']), int(tmp_info['size2']))
    # use image center if detector origin is (0,0)
    if sum(info['detector_origin']) <  0.1:
        info['detector_origin'] = (info['detector_size'][0]/2, info['detector_size'][1]/2)
    info['starting_angle'] = float(tmp_info['osc_start'])
    if tmp_info.get('twotheta') is not None:
        info['two_theta'] = float(tmp_info['twotheta'])
    else:
        info['two_theta'] = 0.0
    info['file_format'] = 'SMV'

    return info
