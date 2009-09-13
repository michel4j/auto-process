"""
MarCCD TIFF format readers

"""

import struct
import math

def read_header(filename):
    """
    Read MARCCD image headers
    returns a dictionary of header parameters
    
    """
    info = {}
    
    myfile = open(filename,'rb')
    header_format = 'I16s39I80x' # 256 bytes
    statistics_format = '3Q7I9I40x128H' #128 + 256 bytes
    goniostat_format = '28i16x' #128 bytes
    detector_format = '5i9i9i9i' #128 bytes
    source_format = '10i16x10i32x' #128 bytes
    file_format = '128s128s64s32s32s32s512s96x' # 1024 bytes
    dataset_format = '512s' # 512 bytes
    image_format = '9437184H'
    
    marccd_header_format  = header_format + statistics_format + goniostat_format + detector_format 
    marccd_header_format += source_format + file_format + dataset_format + '512x'
    
    tiff_header = myfile.read(1024)
    header_pars = struct.unpack(header_format,myfile.read(256))
    statistics_pars = struct.unpack(statistics_format,myfile.read(128+256))
    goniostat_pars  = struct.unpack(goniostat_format,myfile.read(128))
    detector_pars = struct.unpack(detector_format, myfile.read(128))
    source_pars = struct.unpack(source_format, myfile.read(128))
    file_pars = struct.unpack(file_format, myfile.read(1024))
    dataset_pars = struct.unpack(dataset_format, myfile.read(512))
    myfile.close()
    
    info['oscillation_range'] = goniostat_pars[24] / 1e3
    info['distance']  = goniostat_pars[14] / 1e3
    info['wavelength']  = source_pars[3] / 1e5
    info['exposure_time'] = goniostat_pars[4] / 1e3
    info['detector_origin'] = (goniostat_pars[1]/1e3, goniostat_pars[2]/1e3)
    # use image center if detector origin is (0,0)
    if sum(info['detector_origin']) <  0.1:
        info['detector_origin'] = (header_pars[17]/2, header_pars[18]/2)
    info['detector_size'] = (header_pars[17], header_pars[18])
    info['pixel_size'] = (detector_pars[1]/1e6, detector_pars[2]/1e6)
    info['starting_angle'] = goniostat_pars[8] / 1e3
    info['two_theta'] = (goniostat_pars[7] / 1e3) * math.pi / -180.0
    info['file_format'] = 'TIFF'
    
    return info
