import functools
import gzip
import json
import math
import os
import pwd
import shutil

import msgpack
import numpy
import msgpack_numpy

from prettytable import PrettyTable

# Physical Constants
_h = 4.13566733e-15  # eV.s
_c = 299792458e10  # A/s

# direction vector of kappa axis on 08B1-1 when omega is at 0.0 deg
KAPPA_AXIS = numpy.array([0.91354546, 0.3468, 0.21251931])


def code_matches_all(code, *args):
    return all([code | v == code for v in args])


def code_matches_any(code, *args):
    return any([code | v == code for v in args])


def code_matches_only(code, *args):
    return code == functools.reduce(lambda x, y: x | y, args)


def code_matches_none(code, *args):
    return not (any([code | v == code for v in args]))


def get_cpu_count():
    return os.sysconf('SC_NPROCESSORS_ONLN')


def energy_to_wavelength(energy):
    """Convert energy in keV to wavelength in angstroms."""
    if energy == 0.0:
        return 0.0
    return (_h * _c) / (energy * 1000.0)


def wavelength_to_energy(wavelength):
    """Convert wavelength in angstroms to energy in keV."""
    if wavelength == 0.0:
        return 0.0
    return (_h * _c) / (wavelength * 1000.0)


def air(e):
    p = [1.00000857e+00, -3.10243288e-04, 3.01020914e+00]
    return 1.0 - (p[0] * math.exp(p[1] * (e ** p[2])))


def get_project_name():
    return pwd.getpwuid(os.geteuid())[0]


def get_home_dir():
    return pwd.getpwuid(os.geteuid())[5]


def backup_files(*args):
    for filename in args:
        if os.path.exists(filename):
            index = 0
            while os.path.exists('%s.%0d' % (filename, index)):
                index += 1
            shutil.copy(filename, '%s.%0d' % (filename, index))
    return


def backup_special_file(filename, suffix):
    if os.path.exists(filename):
        shutil.copy(filename, '%s.%s' % (filename, suffix))
    return


def file_requirements(*args):
    all_exist = True
    for f in args:
        if not os.path.exists(f):
            all_exist = False
            break
    return all_exist


def combine_names(names):
    """
    Return a combined name to represent a set of names
    """

    return '-'.join([_f for _f in [os.path.commonprefix(names), 'combined'] if _f])


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
            bkdir = "%s-bk%02d" % (workdir, count)
            exists = os.path.isdir(bkdir)
        shutil.move(workdir, bkdir)
        os.makedirs(workdir)


def calc_angle(v1, v2):
    v1 = numpy.array(v1, dtype=numpy.float64) / numpy.linalg.norm(v1)
    v2 = numpy.array(v2, dtype=numpy.float64) / numpy.linalg.norm(v2)
    cs = numpy.dot(v1, v2)
    sn = numpy.linalg.norm(numpy.cross(v1, v2))
    a = numpy.arctan2(sn, cs)
    if a > numpy.pi / 2.0:
        a = a - numpy.pi
    return a


def make_rot_matrix(direction, angle):
    """
    Create a rotation matrix corresponding to the rotation around a general
    axis by a specified angle.

    R = dd^T + cos(a) (I - dd^T) + sin(a) skew(d)

    Parameters:

        angle : float a
        direction : array d
    """
    angle = angle * numpy.pi / 180.0

    d = numpy.array(direction, dtype=numpy.float64)
    d /= numpy.linalg.norm(d)

    eye = numpy.eye(3, dtype=numpy.float64)
    ddt = numpy.outer(d, d)
    skew = numpy.array([[0, d[2], -d[1]],
                        [-d[2], 0, d[0]],
                        [d[1], -d[0], 0]], dtype=numpy.float64)

    mtx = ddt + numpy.cos(angle) * (eye - ddt) + numpy.sin(angle) * skew
    return mtx


def rotate_vector(vec, mtxa):
    mtx = numpy.matrix(mtxa, dtype=numpy.float64)
    vec = numpy.matrix(vec, dtype=numpy.float64)
    nvec = mtx * vec.getT()

    if vec.shape == (1, 3):
        return nvec.getT().getA1()
    else:
        return nvec.getT().getA()


def optimize_xtal_offset(info, kappa_axis=KAPPA_AXIS):
    """Optimize the kappa and Phi rotations required to align the 
    longest cell axis closest to the spindle axis
    
    input:
        - info is a dictionary produced by parser.xds.parse_xparm
        - kappa_axis is the direction vector of the kappa axis at zero spindle rotation
    """

    STEP = 5  # How coarse should the brute force search be in degrees?

    axis_names = ['cell_a_axis', 'cell_b_axis', 'cell_c_axis']
    longest_axis = max(list(zip(info['unit_cell'], axis_names)))[1]
    kmat = make_rot_matrix(kappa_axis, STEP)
    orig_offset = abs(calc_angle(info[longest_axis], info['rotation_axis'])) * 180.0 / numpy.pi
    offsets = []
    cell_axis = info[longest_axis]
    rot_axis = info['rotation_axis']

    for kappa in range(0, 180, STEP):
        for phi in range(0, 360, STEP):
            pmat = make_rot_matrix(rot_axis, phi)
            nc_axis = rotate_vector(cell_axis, pmat)  # first apply phi rotation to cell axis
            kmat = make_rot_matrix(kappa_axis, kappa)
            nc_axis = rotate_vector(nc_axis, kmat)  # then add kappa rotation to cell axis

            offset = abs(calc_angle(nc_axis, rot_axis)) * 180.0 / numpy.pi
            p_ax = rotate_vector(rot_axis, kmat)
            chi_offset = abs(calc_angle(p_ax, rot_axis)) * 180.0 / numpy.pi
            offsets.append((offset, kappa, phi, chi_offset))

    # offset dimensions
    ks = len(list(range(0, 180, STEP)))
    ps = len(list(range(0, 360, STEP)))

    opt_offset, opt_kappa, opt_phi, chi_offset = min(offsets)
    _out = {
        'kappa': opt_kappa,
        'phi': opt_phi,
        'chi': chi_offset,
        'longest_axis': axis_names.index(longest_axis),
        'offset': orig_offset,
        'best_offset': opt_offset,
        'data': numpy.array(offsets),
        'shape': (ks, ps),
    }
    return _out


class Table(object):
    def __init__(self, t):
        self._table = t
        self.size = len(self._table)
        self.hidden_columns = []

    def __repr__(self):
        return "<Table (%d rows)\n%s\n>" % (self.size, str(self))

    def __str__(self):
        return self.get_text()

    def get_text(self, full=False):
        x = PrettyTable(list(self.keys()))
        if self.size < 7 or full:
            for i in range(self.size):
                x.add_row(self.row(i))
        else:
            for i in range(3):
                x.add_row(self.row(i))
            x.add_row(['...'] * len(list(self.keys())))
            for i in range(self.size - 3, self.size):
                x.add_row(self.row(i))
        return x.get_string()

    def keys(self):
        return [k for k in list(self._table[0].keys()) if k not in self.hidden_columns]

    def hide(self, *args):
        self.hidden_columns.extend(args)

    def show_all(self):
        self.hidden_columns = []

    def row(self, i):
        if i < len(self._table):
            return [v for k, v in list(self._table[i].items()) if k not in self.hidden_columns]

    def rows(self, slice=":"):
        pre, post = slice.split(':')
        if pre.strip() == '':
            pre = 0
        else:
            pre = int(pre)
        if post.strip() == '':
            post = self.size
        else:
            post = int(post)
            if post < 0: post = self.size + post

        return [self.row(i) for i in range(self.size) if i >= pre and i < post]

    def column(self, key):
        return [r[key] for r in self._table]

    def sort(self, key, reverse=False):
        self._table.sort(key=lambda x: x[key])
        if reverse:
            self._table = self._table[::-1]

    def __getitem__(self, s):
        vals = [r[s] for r in self._table]
        return vals


class rTable(Table):
    def __init__(self, t):
        self._table = []
        keys = list(t.keys())
        for i in range(len(t[keys[0]])):
            d = {}
            for k in keys:
                d[k] = t[k][i]
            self._table.append(d)
        self.size = len(self._table)
        self.hidden_columns = []


class sTable(Table):
    def __init__(self, t):
        self.table = PrettyTable()
        self.table.field_names = t[0]
        for row in t[1:]:
            self.table.add_row(row)
        self.table.align[t[0][0]] = "l"

    def __str__(self):
        return self.table.get_string()


# Ordered Dict from Django

class SortedDict(dict):
    """
    A dictionary that keeps its keys in the order in which they're inserted.
    """

    def __new__(cls, *args, **kwargs):
        instance = super(SortedDict, cls).__new__(cls, *args, **kwargs)
        instance.keyOrder = []
        return instance

    def __init__(self, data=None):
        if data is None:
            data = {}
        super(SortedDict, self).__init__(data)
        if isinstance(data, dict):
            self.keyOrder = list(data.keys())
        else:
            self.keyOrder = []
            for key, value in data:
                if key not in self.keyOrder:
                    self.keyOrder.append(key)

    def __deepcopy__(self, memo):
        from copy import deepcopy
        return self.__class__([(key, deepcopy(value, memo))
                               for key, value in self.items()])

    def __setitem__(self, key, value):
        super(SortedDict, self).__setitem__(key, value)
        if key not in self.keyOrder:
            self.keyOrder.append(key)

    def __delitem__(self, key):
        super(SortedDict, self).__delitem__(key)
        self.keyOrder.remove(key)

    def __iter__(self):
        for k in self.keyOrder:
            yield k

    def pop(self, k, *args):
        result = super(SortedDict, self).pop(k, *args)
        try:
            self.keyOrder.remove(k)
        except ValueError:
            # Key wasn't in the dictionary in the first place. No problem.
            pass
        return result

    def popitem(self):
        result = super(SortedDict, self).popitem()
        self.keyOrder.remove(result[0])
        return result

    def items(self):
        return list(zip(self.keyOrder, list(self.values())))

    def iteritems(self):
        for key in self.keyOrder:
            yield key, super(SortedDict, self).__getitem__(key)

    def keys(self):
        return self.keyOrder[:]

    def iterkeys(self):
        return iter(self.keyOrder)

    def values(self):
        return list(map(super(SortedDict, self).__getitem__, self.keyOrder))

    def itervalues(self):
        for key in self.keyOrder:
            yield super(SortedDict, self).__getitem__(key)

    def update(self, dict_):
        for k, v in list(dict_.items()):
            self.__setitem__(k, v)

    def setdefault(self, key, default):
        if key not in self.keyOrder:
            self.keyOrder.append(key)
        return super(SortedDict, self).setdefault(key, default)

    def value_for_index(self, index):
        """Returns the value of the item at the given zero-based index."""
        return self[self.keyOrder[index]]

    def insert(self, index, key, value):
        """Inserts the key, value pair before the item with the given index."""
        if key in self.keyOrder:
            n = self.keyOrder.index(key)
            del self.keyOrder[n]
            if n < index:
                index -= 1
        self.keyOrder.insert(index, key)
        super(SortedDict, self).__setitem__(key, value)

    def copy(self):
        """Returns a copy of this object."""
        # This way of initializing the copy means it works for subclasses, too.
        obj = self.__class__(self)
        obj.keyOrder = self.keyOrder[:]
        return obj

    def __repr__(self):
        """
        Replaces the normal dict.__repr__ with a version that returns the keys
        in their sorted order.
        """
        return '{%s}' % ', '.join(['%r: %r' % (k, v) for k, v in list(self.items())])

    def clear(self):
        super(SortedDict, self).clear()
        self.keyOrder = []


class DotDict(dict):
    def __getattr__(self, attr):
        return self.get(attr, None)

    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


def save_pid(file_path):
    with open(file_path, 'w') as handle:
        handle.write('{}\n'.format(os.getpid()))


def load_json(filename):
    with open(filename, 'r') as handle:
        info = json.load(handle)
    return info


def load_chkpt(filename='process.chkpt'):
    with gzip.open(filename, 'rb') as handle:
        info = msgpack.load(handle, object_hook=msgpack_numpy.decode)
    return info


def savgol_filter(data, window_length, polyorder, deriv=0):
    """
        applies a Savitzky-Golay filter
        input parameters:
        - data => data as a 1D numpy array
        - kernel => a positiv integer > 2*order giving the kernel size
        - order => order of the polynomal
        - deriv => derivative to return default (smooth only)
        returns smoothed data as a numpy array

        invoke like:
        smoothed = savitzky_golay(<rough>, [kernel = value], [order = value]
    """
    try:
        window_length = abs(int(window_length))
        polyorder = abs(int(polyorder))
    except ValueError:
        raise ValueError("kernel and order have to be of type int (floats will be converted).")
    if window_length % 2 != 1: window_length += 1
    if window_length < 1: window_length = 1

    if window_length < polyorder + 2:
        raise TypeError("kernel is to small for the polynomals\nshould be > order + 2")

    # a second order polynomal has 3 coefficients
    order_range = list(range(polyorder + 1))
    half_window = (window_length - 1) // 2
    b = numpy.mat([[k ** i for i in order_range] for k in range(-half_window, half_window + 1)])
    # since we don't want the derivative, else choose [1] or [2], respectively
    assert deriv <= 2
    m = numpy.linalg.pinv(b).A[deriv]
    window_size = len(m)
    half_window = (window_size - 1) // 2

    # precompute the offset values for better performance
    offsets = list(range(-half_window, half_window + 1))
    offset_data = list(zip(offsets, m))

    smooth_data = list()

    # temporary data, extended with a mirror image to the left and right
    firstval = data[0]
    lastval = data[len(data) - 1]
    # left extension: f(x0-x) = f(x0)-(f(x)-f(x0)) = 2f(x0)-f(x)
    # right extension: f(xl+x) = f(xl)+(f(xl)-f(xl-x)) = 2f(xl)-f(xl-x)
    leftpad = numpy.zeros(half_window) + 2 * firstval
    rightpad = numpy.zeros(half_window) + 2 * lastval
    leftchunk = data[1:1 + half_window]
    leftpad = leftpad - leftchunk[::-1]
    rightchunk = data[len(data) - half_window - 1:len(data) - 1]
    rightpad = rightpad - rightchunk[::-1]
    data = numpy.concatenate((leftpad, data))
    data = numpy.concatenate((data, rightpad))

    for i in range(half_window, len(data) - half_window):
        value = 0.0
        for offset, weight in offset_data:
            value += weight * data[i + offset]
        smooth_data.append(value)
    return numpy.array(smooth_data)


def uniquify(seq):
    seen = set()
    seen_add = seen.add
    return [x for x in seq if not (x in seen or seen_add(x))]
