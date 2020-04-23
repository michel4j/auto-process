import inspect
import json
import os
import re
import shutil
import subprocess
import warnings

import numpy
from mxio import read_image
from scipy import interpolate

from autoprocess.utils import xdi, fitio, log, misc
from autoprocess.utils.ellipse import fit_ellipse

SHARE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'share')

try:
    from scipy.signal import savgol_filter
except:
    from autoprocess.utils.misc import savgol_filter

warnings.filterwarnings('ignore')

XSTEP = 0.05
BACKSTOP_OFFSET = 200
CENTER_SEARCH_LIMIT = 500

logger = log.get_module_logger('powder')


class Fit2DFile(object):
    def __init__(self, filename, format):
        self.rawfile = filename
        self.format = format
        path, ext = os.path.splitext(self.rawfile)
        if self.format == 'TIFF':
            self.filename = '{}.{}'.format(path, 'tiff')
        else:
            self.filename = self.rawfile
        self.name = os.path.basename(path)

    def __enter__(self):
        if self.format == 'TIFF':
            try:
                os.symlink(self.rawfile, self.filename)
            except OSError:
                pass
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if self.format == 'TIFF':
            os.unlink(self.filename)
        return True


def peak_width(a, x, w=30):
    left = numpy.where(a[x - w:x] > a[x] / 2)
    right = numpy.where(a[x:x + w] > a[x] / 2)
    left = w if left else left[0][0]
    right = 0 if not right else right[0][-1]
    return right + w - left


def find_peaks(y, width=11, sensitivity=0.01, smooth=True):
    yfunc = interpolate.interp1d(numpy.arange(len(y)), y, fill_value='extrapolate')
    width = width if width % 2 else width + 1  # force width to be odd
    hw = width // 2
    hw = hw if hw % 2 else hw + 1  # force width to be odd
    ypp = savgol_filter(y, width, 2, deriv=2)
    ypp[ypp > 0] = 0.0
    ypp *= -1
    yp = savgol_filter(ypp, hw, 1, deriv=1)

    peak_str = numpy.array([True, True, False, False]).tostring()
    data_str = (yp > 0.0).tostring()

    def get_peak(pos):
        return pos, yfunc(pos), 2 * peak_width(y, int(pos), width) + 1

    peak_positions = [get_peak(m.start() + 1.5) for m in re.finditer(peak_str, data_str)]
    ymax = max(y)
    return numpy.array([
        v for v in peak_positions if (v[1] >= sensitivity * ymax and v[2])
    ])


def peak_search(xy, width=11, sensitivity=0.01, smooth=True):
    peaks = find_peaks(xy[:, 1], width=width, sensitivity=sensitivity, smooth=smooth)
    xfunc = interpolate.interp1d(numpy.arange(len(xy[:, 0])), xy[:, 0], fill_value='extrapolate')
    x = xfunc(peaks[:, 0])
    w = xfunc(peaks[:, 0] + peaks[:, 2]) - x
    peaks[:, 0] = x
    peaks[:, 2] = w
    return peaks


def peak_search2(xo, yo, width=11, sensitivity=0.01, smooth=True):
    peaks = find_peaks(yo, width=width, sensitivity=sensitivity, smooth=smooth)
    xfunc = interpolate.interp1d(numpy.arange(len(xo)), xo, fill_value='extrapolate')
    x = xfunc(peaks[:, 0])
    w = xfunc(peaks[:, 0] + peaks[:, 2]) - x
    peaks[:, 0] = x
    peaks[:, 2] = w
    return peaks


def baseline(values):
    cdev = values.std()
    orig = len(values)
    pdev = cdev + 100
    mx = values.max()
    delta = 3
    while (abs(pdev - cdev) > 0.1) and (mx > values.min() + cdev * 2):
        pdev = cdev
        values = values[values < mx]
        mx = values.max()
        cdev = values.std()
    return values


def angle_slice(x, angle, width=1):
    angle = angle if angle <= 180 else angle - 360.0
    slice = numpy.radians(angle)
    w = numpy.radians(width) / 2
    return (x > slice - w) & (x < slice + w)


def calc_profile(r, data):
    intensities = numpy.bincount(r, data)
    counts = numpy.bincount(r) + 1
    return (intensities / counts)


def norm_curve(s):
    ns = numpy.log(1 + 1000 * (s - s.min()) / (s.max() - s.min()))
    return ns


class PeakSorter(object):
    def __init__(self, reference, max_size=10, width_factor=1):
        self.reference = reference[reference[:, 1].argsort()[::-1][:max_size]]
        self.tree = [[] for i in range(self.reference.shape[0])]
        self.width_factor = width_factor

    def add_peaks(self, peaks, angle):
        for x, y, w in peaks:
            diffs = numpy.abs(self.reference[:, 0] - x)
            idx = numpy.argmin(diffs)
            if diffs[idx] <= self.width_factor * (self.reference[idx, 2] + w) and y >= self.reference[idx, 1] * 0.2:
                self.tree[idx].append([x, float(angle)])
                self.reference[idx, 0] = x  # update x position to next peak
                self.reference[idx, 2] = w


class FrameProfiler(object):
    def __init__(self, filename):
        self.frame = read_image(filename)
        self.nx, self.ny = self.frame.data.shape
        self.x_axis = numpy.arange(self.nx)
        self.y_axis = numpy.arange(self.ny)
        self.cx, self.cy = self.frame.header['beam_center']
        self.rot_x, self.rot_y = 0.0, 0.0
        self.mask = (self.frame.data > 0.0) & (self.frame.data < self.frame.header['saturated_value'])

    def r2q(self, r):
        return 2 * numpy.pi / r

    def r2tt(self, r):
        return numpy.degrees(numpy.arctan(r / self.frame.header['distance']))

    def transform(self, size=180, rot=(None, None)):
        rsize, asize = max(self.nx, self.ny) / 2, size

        r = self.radii(rotx=rot[0], roty=rot[1])[self.mask]
        a = self.azimuth(rotx=rot[0], roty=rot[1])[self.mask]

        rmin, rmax = r.min(), r.max()
        amin, amax = a.min(), a.max()

        self.ri = numpy.linspace(rmin, rmax, rsize)
        self.ai = numpy.linspace(amin, amax, asize)

        # interpolation functions from index to r and a values
        self.i2r = interpolate.interp1d(numpy.arange(rsize), self.ri, assume_sorted=True)
        self.i2a = interpolate.interp1d(numpy.arange(asize), self.ai, assume_sorted=True)

        self.PX, self.PY = self.cart(self.ri, self.ai)
        self.rdata = numpy.zeros((asize, rsize))
        for i in range(asize):
            for j in range(rsize):
                if self.PX[i, j] < 0 or self.PY[i, j] < 0: continue
                if self.PX[i, j] >= self.nx or self.PY[i, j] >= self.ny: continue
                self.rdata[i, j] = self.frame.data[int(self.PX[i, j]), int(self.PY[i, j])]

    def shiftr(self, data):
        asize, rsize = data.shape
        offsets = numpy.zeros((asize,))
        last_i = 0
        sel = numpy.isfinite(data[0, :])
        last_avg = data[0, sel].mean()
        while last_avg < 0:
            last_i += 1
            sel = numpy.isfinite(data[0, :])
            last_avg = data[last_i, sel].mean()

        for i in range(last_i + 1, asize):
            sel = numpy.isfinite(data[0, :])
            avg = data[i, sel].mean()
            if (avg / last_avg) < 0.5 or last_avg < 0:
                continue
            else:
                offset = calc_shift(data[last_i, :], data[i, :])
                if offset < -20 or offset > 20: continue
                offsets[i] = offset
                last_i = i
                last_avg = avg

        offsets = numpy.cumsum(offsets).astype(int)
        pad = abs(min(0, offsets.min()))
        offsets += pad
        sdata = numpy.zeros_like(data)
        for i, offset in enumerate(offsets):
            sdata[i, offset:] = data[i, :(rsize - offset)]
        return sdata, offsets

    def profile(self, sub_mask=None):
        mask = (self.frame.data > 0.0) & (self.frame.data < self.frame.header['saturated_value'])
        if sub_mask is not None:
            mask &= sub_mask
        r = self.radii()[mask].ravel()
        data = self.frame.data[mask].ravel()
        prof = calc_profile(r.astype(int), data)
        r_axis = numpy.arange(r.max())
        fprof = numpy.dstack([r_axis, prof])[0]
        return fprof

    def from_polar(self, r, theta):
        return self.cx + r * numpy.cos(theta), self.cy + r * numpy.sin(theta)

    def cart(self, r, theta):
        return self.cx + r[None, :] * numpy.cos(theta[:, None]), self.cy + r[None, :] * numpy.sin(theta[:, None])

    def azimuth(self, rotx=None, roty=None):
        if rotx is None or roty is None:
            rotx, roty = numpy.radians(self.rot_x), numpy.radians(self.rot_y)
        xo = (self.x_axis - self.cx)
        yo = (self.y_axis - self.cy)
        x = xo * numpy.cos(rotx)
        y = yo * numpy.cos(roty)
        return numpy.arctan2(x[:, None], y[None, :])

    def radii(self, rotx=None, roty=None):
        if rotx is None or roty is None:
            rotx, roty = numpy.radians(self.rot_x), numpy.radians(self.rot_y)
        xo = (self.x_axis - self.cx)
        yo = (self.y_axis - self.cy)
        x = xo * numpy.cos(rotx)
        y = yo * numpy.cos(roty)
        return (numpy.hypot(x[:, None], y[None, :]))


class FrameAnalyser(object):
    def __init__(self, *files):
        self.files = [os.path.abspath(filename) for filename in misc.uniquify(files)]
        self.filename = self.files[0]
        self.directory = os.getcwd()
        dbdir = os.path.join(os.path.expanduser('~'), '.config/autoprocess')
        if not os.path.exists(dbdir):
            os.makedirs(dbdir)
        self.db_file = os.path.join(dbdir, 'powder.idb')
        if not os.path.exists(self.db_file):
            logger.warning('Calibration file missing! Must perform at least one calibrate before integrating')

        # prepare xdi_headers
        self.data_types = {
            'names': ['twotheta', 'd', 'Q', 'counts'],
            'formats': [float, float, float, int],
        }
        self.data = {}
        self.first_column = None
        self.frame_name = '0000'

    def add_data(self, d):
        name = self.frame_name
        self.data_types['names'].insert(-1, name)
        self.data_types['formats'].insert(-1, int)

        if not 'counts' in self.data:
            self.first_column = name
            tt = numpy.radians(d[:, 0])
            self.data['Q'] = (4 * numpy.pi / self.frame.header['wavelength']) * numpy.sin(tt / 2)
            self.data['twotheta'] = numpy.degrees(tt)
            self.data['d'] = self.frame.header['wavelength'] / (2 * numpy.sin(tt / 2))
            self.data['counts'] = numpy.copy(d[:, 1])
            self.data[name] = d[:, 1]
        else:
            self.data['counts'] += d[:, 1]
            self.data[name] = d[:, 1]

    def set_file(self, filename):
        self.filename = filename
        self.profiler = FrameProfiler(self.filename)
        self.frame = self.profiler.frame
        self.mask = (self.frame.data > 0.0) & (self.frame.data < self.frame.header['saturated_value'])
        self.cx, self.cy = self.frame.header['beam_center']
        self.rot_x, self.rot_y = 0.0, 0.0
        self.size = min(self.profiler.nx - self.cx, self.cx, self.profiler.ny - self.cy, self.profiler.ny)
        file_pattern = re.compile(r'^(?P<base>.+)_(?P<num>\d{3,6})(?P<ext>\.?[\w.]+)?$')
        m = file_pattern.match(os.path.basename(filename)).groupdict()
        self.frame_name = m['num']
        self.group_name = m['base']

    def get_xy(self, twotheta, azimuth):
        r = self.frame.header['distance'] * numpy.tan(numpy.radians(twotheta)) / self.frame.header['pixel_size']
        return self.cx + r * numpy.sin(numpy.radians(azimuth)), self.cy + r * numpy.cos(numpy.radians(azimuth))

    def find_rings(self, samples=25, width=2):
        # find rings in the image by integrating along radial directions
        peaks_list = []
        sizes = []
        reference_rings = -1
        reference = None
        for angle in numpy.arange(0., 360., 360 / samples):
            prof = self.integrate_angle(angle, width=width)
            peaks = peak_search(prof, width=15, sensitivity=0.01)
            num_rings = len(peaks)
            if num_rings > reference_rings:
                reference = peaks
                reference_rings = len(peaks)
            sizes.append(peaks[:, 2].max())
            peaks_list.append((peaks, angle))

        reference = peaks_list[0][0]
        # Group the peaks into bins corresponding to rings
        peak_sorter = PeakSorter(reference, max_size=20, width_factor=2)
        for peaks, angle in peaks_list:
            peak_sorter.add_peaks(peaks, angle)

        width = numpy.median(sizes) / self.frame.header['pixel_size']
        coords = numpy.array(peak_sorter.tree[0])

        group_sizes = numpy.array([len(group) for group in peak_sorter.tree])
        # best_group = numpy.array(peak_sorter.tree[numpy.argmax(group_sizes)])
        logger.warning('Group Sizes: {}'.format(group_sizes))

        x, y = self.get_xy(coords[:, 0], coords[:, 1])
        ellipse = list(zip(x, y))
        rings = [self.get_xy(group[0][0], group[0][1]) for group in peak_sorter.tree[1:]]
        angles = [group[0][0] for group in peak_sorter.tree[1:]]

        return {
            'ellipse': ellipse,
            'rings': rings[:10],
            'ring_width': width * 5,
            'angles': angles[:10],
        }

    def show_rings(self, samples=40, width=2):
        from matplotlib import pyplot as plt
        peak_sorter = None
        sizes = []
        plt.imshow(self.frame.data)
        for angle in numpy.arange(0., 360., 360 / samples):
            prof = self.integrate_angle(angle, width=width)
            peaks = peak_search(prof, width=50, sensitivity=0.05)
            sizes.append(peaks[:, 2].max())
            if not peak_sorter:
                peak_sorter = PeakSorter(peaks, max_size=10)
            else:
                peak_sorter.add_peaks(peaks, angle)
        width = numpy.median(sizes) / self.frame.header['pixel_size']

        for i, group in enumerate(peak_sorter.tree):
            if len(group) < 0.5 * samples: continue
            coords = numpy.array(group)
            x, y = self.get_xy(coords[:, 0], coords[:, 1])
            plt.scatter(y, x, s=5)
        plt.show()
        coords = numpy.array(peak_sorter.tree[0])
        x, y = self.get_xy(coords[:, 0], coords[:, 1])
        ellipse = list(zip(x, y))
        rings = [self.get_xy(group[0][0], group[0][1]) for group in peak_sorter.tree[1:]]

        return {
            'ellipse': ellipse,
            'rings': rings,
            'ring_width': width * 5,
        }

    def fit_ellipses(self, samples=120, width=10):
        peak_sorter = None
        for angle in numpy.arange(30., 360., 360 / samples):
            prof = self.integrate_angle(angle, width=width)
            peaks = peak_search(prof, width=4, sensitivity=0.3)
            if not peak_sorter:
                peak_sorter = PeakSorter(peaks, max_size=20)
            else:
                peak_sorter.add_peaks(peaks, angle)
        fits = []
        for i, group in enumerate(peak_sorter.tree):
            if len(group) < 0.5 * samples: continue
            coords = numpy.array(group)
            x, y = self.get_xy(coords[:, 0], coords[:, 1])
            fits.append(self.fit_points(x, y))
        return fits

    def calibrate(self):
        from xvfbwrapper import Xvfb
        self.set_file(self.files[0])

        logger.info('Detecting strong rings in frame {}:{} ...'.format(self.group_name, self.frame_name))
        params = self.find_rings()
        if len(params['rings']) > 5 and len(params['ellipse']) >= 5:
            logger.info(
                'Sufficient number ({}, {}) of rings at: {} deg'.format(
                    len(params['rings']),
                    len(params['ellipse']),
                    ', '.join(['{:0.1f}'.format(a) for a in params['angles']])
                )
            )
        else:
            logger.warning(
                'Insufficient number ({}, {}) of rings found at: {} deg'.format(
                    len(params['rings']),
                    len(params['ellipse']),
                    ', '.join(['{:0.1f}'.format(a) for a in params['angles']])
                )
            )
            logger.warning('Calibration may fail. Use a frame with clearly separated diffraction rings!')

        for key in ['wavelength', 'distance', 'format', 'detector_size', 'pixel_size', 'beam_center']:
            params[key] = self.frame.header[key]

        dim = numpy.ceil(max(params['detector_size']) / 1000.) * 1000
        with Fit2DFile(self.filename, self.frame.header['format']) as imgfile:
            params['file_name'] = imgfile.filename
            params['directory'] = self.directory
            params['data_name'] = imgfile.name
            params['db_file'] = self.db_file
            fitio.write_calib_macro(params, macro_file='calib.mac')

            with Xvfb():
                args = ['fit2d', '-dim{0:0.0f}x{0:0.0f}'.format(dim), '-maccalib.mac']
                logger.info('Running calibration through fit2d ...')
                if os.path.exists(self.db_file):
                    logger.warning('Calibration file will be overwritten')
                subprocess.check_output(args, timeout=120, stderr=subprocess.STDOUT)

            os.remove('calib.mac')
            data_file = '{}.chi'.format(params['data_name'])
            if os.path.exists(data_file):
                data = numpy.loadtxt(data_file, skiprows=4)
                self.add_data(data)
                os.remove(data_file)

        params['type'] = 'Calibration'
        self.report(params, self.data)
        self.save_xdi('{}.xdi'.format(self.group_name))

    def integrate(self, intensity=False):
        from xvfbwrapper import Xvfb
        params = {}

        for filename in self.files:
            self.set_file(filename)
            for key in ['wavelength', 'distance', 'format', 'detector_size', 'pixel_size', 'beam_center']:
                params[key] = self.frame.header[key]

            dim = numpy.ceil(max(params['detector_size']) / 1000.) * 1000
            with Fit2DFile(self.filename, self.frame.header['format']) as imgfile:
                params['file_name'] = imgfile.filename
                params['data_name'] = imgfile.name
                params['directory'] = self.directory
                params['intensity'] = intensity
                params['db_file'] = self.db_file
                if not os.path.exists(self.db_file):
                    logger.error('Calibration file missing! Must perform at least one calibrate before integrating')
                    raise IOError('File not found!')

                fitio.write_integrate_macro(params, macro_file='integrate.mac')
                with Xvfb():
                    logger.info('Integrating frame {}: {} ...'.format(self.group_name, self.frame_name))
                    args = ['fit2d', '-dim{0:0.0f}x{0:0.0f}'.format(dim), '-macintegrate.mac']
                    subprocess.check_output(args, timeout=120, stderr=subprocess.STDOUT)
                os.remove('integrate.mac')
            data_file = '{}.chi'.format(params['data_name'])
            if os.path.exists(data_file):
                data = numpy.loadtxt(data_file, skiprows=4)
                self.add_data(data)
                os.remove(data_file)
        params['type'] = 'Integration'
        self.save_xdi('{}.xdi'.format(self.group_name))
        self.report(params, self.data)

    def save_xdi(self, filename):
        logger.info('Saving XDI formatted data: {}'.format(filename))
        if len(self.files) == 1:
            i = self.data_types['names'].index(self.frame_name)
            self.data_types['names'].pop(i)
            self.data_types['formats'].pop(i)
        rec_data = numpy.zeros(self.data['twotheta'].shape[0], dtype=self.data_types)
        for key in self.data_types['names']:
            rec_data[key] = self.data[key]

        units = {
            'twotheta': 'degrees',
            'd': 'Angstrom',
        }
        comments = 'Azimuthal Profile'
        xdi_data = xdi.XDIData(data=rec_data, comments=comments, version='AutoProcess/4.0')
        xdi_data['Mono.name'] = 'Si 111'

        for i, name in enumerate(self.data_types['names']):
            key = 'Column.{}'.format(i + 1)
            xdi_data[key] = (name, units.get(name))
        xdi_data.save(filename)

    def read_db(self):
        if not os.path.exists(self.db_file):
            logger.error('Calibration file missing! Must perform at least one calibrate before integrating')
            return {}
        else:
            with open(self.db_file, 'r') as handle:
                data = handle.read()
            lines = data.split('\n')
            return dict(list(zip(lines[0::2], lines[1::2])))

    def report(self, params, data):
        directory = params['directory']
        info = self.read_db()
        report = {
            'id': None,
            'directory': directory,
            'filename': 'report.json',
            'score': 0.0,
            'data_id': None,
        }

        report_file = os.path.join(directory, report['filename'])
        text_file = os.path.join(directory, 'report.txt')

        # read previous json_file and obtain id from it if one exists:
        if os.path.exists(report_file):
            old_report = misc.load_json(report_file)
            report['id'] = old_report.get('id')

        article = 'using' if params['type'] == 'Calibration' else 'of'
        report['kind'] = 'XRD Analysis'
        report['title'] = 'Azimuthal {} {} "{}"'.format(params['type'], article, params['data_name'])
        report['details'] = [
            {
                'title': "Azimuthal Integration",
                'content': [
                    calib_table(params, info),
                    profile_plot(params, data),
                ]
            }
        ]

        # save
        with open(report_file, 'w') as handle:
            json.dump(report, handle)

        shutil.copy(os.path.join(SHARE_DIR, 'report.html'), directory)
        shutil.copy(os.path.join(SHARE_DIR, 'report.min.js'), directory)
        shutil.copy(os.path.join(SHARE_DIR, 'report.min.css'), directory)

    def radial_average(self, params=None):
        # initialize

        if params:
            self.profiler.cx = params.get('cx', self.profiler.cx)
            self.profiler.cy = params.get('cy', self.profiler.cy)
            self.profiler.rot_x = params.get('rotx', self.profiler.rot_x)
            self.profiler.rot_y = params.get('roty', self.profiler.rot_y)

        prof = self.profiler.profile()
        fileroot, ext = os.path.splitext(self.filename)
        self.profiler.save_xdi(prof, '{}.xdi'.format(fileroot))

        peaks = find_peaks(prof[:, 1], width=5)
        return prof

    def fit_points(self, x, y):
        try:
            ellipse = fit_ellipse(y, x)
            tilt = numpy.arctan2(ellipse.half_long_axis - ellipse.half_short_axis, ellipse.half_short_axis)
            angle = (ellipse.angle + numpy.pi / 2.0) % numpy.pi
            cos_tilt = numpy.cos(tilt)
            sin_tilt = numpy.sin(tilt)
            cos_tpr = numpy.cos(angle)
            sin_tpr = numpy.sin(angle)
            rot2 = numpy.arcsin(sin_tilt * sin_tpr)  # or pi-
            rot1 = numpy.arccos(
                min(1.0, max(-1.0, (cos_tilt / numpy.sqrt(1 - sin_tpr * sin_tpr * sin_tilt * sin_tilt)))))  # + or -
            if cos_tpr * sin_tilt > 0:
                rot1 = -rot1
            rot3 = 0
            return {
                'tilt': numpy.degrees(tilt),
                'angle': numpy.degrees(angle),
                'rotation': 0.0,
                'success': True,
                'rotx': numpy.degrees(rot1),
                'roty': numpy.degrees(rot2),
                'cx': ellipse.cx,
                'cy': ellipse.cy,
            }
        except:
            return {
                'tilt': 0.0,
                'angle': 0.0,
                'rotation': 0.0,
                'rotx': 0.0,
                'roty': 0.0,
                'success': False
            }

    def integrate_angle(self, angle, width=2):
        """Bresenham's line algorithm"""
        azimuth = numpy.radians(angle)
        x, y = int(self.cx), int(self.cy)
        x2 = int(self.size * numpy.sin(azimuth))
        y2 = int(self.size * numpy.cos(azimuth))
        lw = width

        steep = 0
        coords = []
        dx = abs(x2 - x)
        if (x2 - x) > 0:
            sx = 1
        else:
            sx = -1
        dy = abs(y2 - y)
        if (y2 - y) > 0:
            sy = 1
        else:
            sy = -1
        if dy > dx:
            steep = 1
            x, y = y, x
            dx, dy = dy, dx
            sx, sy = sy, sx
        d = (2 * dy) - dx

        for i in range(0, dx):
            if steep:
                coords.append((y, x))
            else:
                coords.append((x, y))
            while d >= 0:
                y = y + sy
                d = d - (2 * dx)
            x = x + sx
            d = d + (2 * dy)
        coords.append((x2, y2))

        data = numpy.zeros((len(coords), 3))
        n = 0
        for ix, iy in coords:
            ix = max(1, ix)
            iy = max(1, iy)
            data[n][0] = n
            src = self.frame.data[ix - lw:ix + lw, iy - lw:iy + lw]
            sel = src & self.mask[ix - lw:ix + lw, iy - lw:iy + lw]
            if sel.sum():
                val = src[sel].mean()
            else:
                val = numpy.nan
            data[n][2] = val
            d = numpy.sqrt((ix - coords[0][0]) ** 2 + (iy - coords[0][1]) ** 2) * self.frame.header['pixel_size']
            data[n][1] = numpy.degrees(numpy.arctan(d / self.frame.header['distance']))
            n += 1
        return data[:, 1:]


def calib_table(params, db_info):
    return {
        'title': 'Experiment Parameters',
        'kind': 'table',
        'header': 'column',
        'data': [
            ['Wavelength (A)', '{:0.4f}'.format(params['wavelength'])],
            ['Detector Distance (mm)', '{:0.4f}'.format(params['distance'])],
            ['Detector Pixel Size (um)', '{:0.4f}'.format(params['pixel_size'])],
            ['File Format', params['format']],
            ['Detector Tilt (deg)', '{:0.4f}'.format(numpy.degrees(float(db_info['TILT_ANGLE'])))],
            ['Detector Tilt Rotation (deg)', '{:0.2f}'.format(numpy.degrees(float(db_info['TILT_ROTATION'])))],
            ['Beam Center (pix)', '{:0.2f}, {:0.2f}'.format(float(db_info['X_BEAM_CENTRE']),
                                                            params['detector_size'][1] - float(
                                                                db_info['Y_BEAM_CENTRE']))],
        ],
    }


def profile_plot(params, data):
    return {
        'kind': 'lineplot',
        'data': {
            'x': ['Two Theta'] + [row for row in data['twotheta']],
            'y1': [['Intensity'] + [row for row in data['counts']], ],
            'y1-label': 'Integrated Intensity'
        },
        'notes': inspect.cleandoc(
            """
            *  The above plots use data generated by Fit2D. A P Hammersley, S O Svensson, M Hanfland, A N Fitch, 
            and D Hausermann, High Pressure Research, 14, pp235-248, (1996).
            """
        )
    }
