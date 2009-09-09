"""
Parsers for XDS Files

"""
import re, numpy
import utils


class _ParseInfo: pass

_xparm = _ParseInfo()

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

def parse_idxref(filename='IDXREF.LP'):
    return utils.parse_file(filename, config='idxref.ini')

def parse_correct(filename='CORRECT.LP'):
    return utils.parse_file(filename, config='correct.ini')

def parse_xscale(filename='XSCALE.LP', output_file='XSCALE.HKL'):
    info = utils.parse_file(filename, config='xscale.ini')
    return info

def parse_integrate(filename='INTEGRATE.LP'):
     return utils.parse_file(filename, config='integrate.ini')

def get_profile(raw_data):
    def _str2arr(s):
        l = [int(v) for v in re.findall('.{3}', s)]
        a = numpy.array(l).reshape((9,9))
        return a
    data = []

    for line in raw_data:
        if len(line) > 2:
            l = line[3:-1]
            data.append(l)

    slice_str = ['']*9

    for i in range(27):
        section = data[i].split('   ')
        sl =  i//9 * 3
        for j in range(3):
            slice_str[sl+j] += section[j]
    
    return numpy.array(map(_str2arr, slice_str))
