#!/usr/bin/env python

import re
import numpy
import os
import json
from autoprocess.libs.imageio import read_image
from autoprocess.utils import xdi
from autoprocess.utils.ellipse import fit_ellipse
from scipy import signal, interp, optimize, interpolate


XSTEP = 0.05
BACKSTOP_OFFSET = 200
CENTER_SEARCH_LIMIT = 500


def peak_width(a, x, w=30):
    left = numpy.where(a[x - w:x] > a[x] / 2)
    right = numpy.where(a[x:x + w] > a[x] / 2)
    left = w if left else left[0][0]
    right = 0 if not right else right[0][-1]
    return right + w - left


def find_peaks(y, width=11, sensitivity=0.01, smooth=True):
    yfunc = interpolate.interp1d(numpy.arange(len(y)), y)
    width = width if width % 2 else width + 1  # force width to be odd
    hw = width // 2
    hw = hw if hw % 2 else hw + 1  # force width to be odd
    ypp = signal.savgol_filter(y, width, 2, deriv=2)
    ypp[ypp > 0] = 0.0
    ypp *= -1
    yp = signal.savgol_filter(ypp, hw, 1, deriv=1)

    peak_str = numpy.array([True, True, False, False]).tostring()
    data_str = (yp > 0.0).tostring()

    def get_peak(pos):
        return pos, yfunc(pos), 2*peak_width(y, int(pos), width) + 1

    peak_positions = [get_peak(m.start() + 1.5) for m in re.finditer(peak_str, data_str)]
    ymax = max(y)
    return numpy.array([
        v for v in peak_positions if (v[1] >= sensitivity * ymax and v[2])
    ])


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


def calc_shift(original, match):
    s1 = norm_curve(original)
    s2 = norm_curve(match)
    sel = numpy.isfinite(s1) & numpy.isfinite(s2)
    z = signal.fftconvolve(s1[sel], s2[sel][::-1])
    lags = numpy.arange(z.size) - (s2.size - 1)
    return (lags[numpy.argmax(numpy.abs(z))])


def calc_scale(original, match):
    s1 = norm_curve(original)
    s2 = norm_curve(match)
    sel = numpy.isfinite(s1) & numpy.isfinite(s2)
    params = [0, 1.0]
    x = numpy.arange(sel.sum())
    out, result = optimize.leastsq(prof_err, params[:], args=(match, original, x), maxfev=25000)
    offset, scale = out
    return offset, scale


def corr_shift(s1, s2):
    corr = signal.correlate(s1, s2)
    return numpy.where(corr == corr.max())[0] % s1.shape[0]


def prof_err(coeffs, p1, p2, x):
    offset, scale = coeffs[:]
    ynew = interp((x + offset) * scale, p1, x)
    return (numpy.log(p2) - numpy.log(ynew)) * p1


def fit_geom(x, y):
    try:
        ellipse = fit_ellipse(y, x)
        tilt = numpy.arctan2(ellipse.half_long_axis - ellipse.half_short_axis, ellipse.half_short_axis)
        cos_tilt = numpy.cos(tilt)
        sin_tilt = numpy.sin(tilt)
        angle = (ellipse.angle + numpy.pi / 2.0) % numpy.pi
        cos_tpr = numpy.cos(angle)
        sin_tpr = numpy.sin(angle)
        rot2 = numpy.arcsin(sin_tilt * sin_tpr)  # or pi-
        rot1 = numpy.arccos(
            min(1.0, max(-1.0, (cos_tilt / numpy.sqrt(1 - sin_tpr * sin_tpr * sin_tilt * sin_tilt)))))  # + or -
        if cos_tpr * sin_tilt > 0:
            rot1 = -rot1
        rot3 = 0
        return (rot1, rot2, rot3)
    except:
        pass

class PeakSorter(object):
    def __init__(self, reference):
        self.reference = reference
        self.tree = [[] for i in range(self.reference.shape[0])]

    def add_peaks(self, peaks, angle):
        for x, y, w in peaks:
            diffs = numpy.abs(self.reference[:,0] - x)
            idx = numpy.argmin(diffs)
            if diffs[idx] <= self.reference[idx,2] and y >= self.reference[idx,1]*0.2:
                self.tree[idx].append([x, float(angle)])


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
        return 2*numpy.pi/r

    def r2tt(self, r):
        return numpy.degrees(numpy.arctan(r/self.frame.header['distance']))

    def transform(self, size=180, rot=(None, None)):
        rsize, asize = max(self.nx, self.ny)/2, size

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
            rotx, roty = self.rot_x, self.rot_y
        x = (self.x_axis - self.cx) * numpy.cos(rotx)
        y = (self.y_axis - self.cy) * numpy.cos(roty)
        return numpy.arctan2(x[:, None], y[None, :])

    def radii(self, rotx=None, roty=None):
        if rotx is None or roty is None:
            rotx, roty = self.rot_x, self.rot_y
        x = (self.x_axis - self.cx) * numpy.cos(rotx)
        y = (self.y_axis - self.cy) * numpy.cos(roty)
        return (numpy.hypot(x[:, None], y[None, :]))

    def save_xdi(self, prof, filename):
        data_types = {
            'names': ['twotheta', 'd', 'Q', 'counts'],
            'formats': [float, float, float, int],
        }
        sel = prof[:,0] > 0
        src = prof[sel,:]
        data = numpy.zeros(src.shape[0], dtype=data_types)
        tt = numpy.arctan((src[:,0] * self.frame.header['pixel_size'])/self.frame.header['distance'])

        data['Q'] = (4*numpy.pi/self.frame.header['wavelength'])*numpy.sin(tt/2)
        data['twotheta'] = numpy.degrees(tt)
        data['d'] = self.frame.header['wavelength'] / (2*numpy.sin(tt/2))
        data['counts'] = src[:, 1]
        units = {
            'twotheta': 'degrees',
            'd': 'Angstrom',
        }
        comments = 'Azimuthal Profile'
        xdi_data = xdi.XDIData(data=data, comments=comments, version='AutoProcess/4.0')
        xdi_data['Mono.name'] =  'Si 111'

        for i, name in enumerate(data_types['names']):
            key = 'Column.{}'.format(i + 1)
            xdi_data[key] = (name, units.get(name))

        xdi_data.save(filename)


def calibrate(filename):
    # initialize
    calc = FrameProfiler(filename)

    # pass 1
    cx = calc.cx
    cy = calc.cy
    calc.transform(size=30)

    # Calculate approximate center
    for i in range(2):
        calc.cx = cx
        calc.cy = cy
        calc.transform(size=30)
        data = calc.rdata
        data, offsets = calc.shiftr(data)

        adx, ady = calc.from_polar(-calc.ri[offsets], calc.ai)
        vx, vy = calc.cx - adx.mean(), calc.cy - ady.mean()
        cx = calc.cx - 2 * vx
        cy = calc.cy - 2 * vy

    calc.cx = cx
    calc.cy = cy
    calc.transform(size=90)
    data = calc.rdata

    # circles
    sel = data > 0
    data[data <= 0] = 0
    prof = data.sum(axis=0) / sel.sum(axis=0)
    pks = find_peaks(prof, width=5)
    peaks = pks[pks[:,0] > BACKSTOP_OFFSET]

    peak_sorter = PeakSorter(peaks)
    for i in range(data.shape[0]):
        a = calc.i2a(i)
        prof = data[i, :]
        lpks = find_peaks(prof, width=5, sensitivity=0.05)
        if lpks.shape[0] == 0: continue
        sel = lpks[:,0] > BACKSTOP_OFFSET
        peak_sorter.add_peaks(lpks[sel], a)


    rots = []
    for i, group in enumerate(peak_sorter.tree):
        if len(group) < 10: continue
        coords = numpy.array(group)
        rvals = calc.i2r(coords[:,0])
        x, y = calc.from_polar(rvals, coords[:,1])
        rot = fit_geom(x, y)
        if rot:
            rots.append(rot)
            rotx, roty, _ = rot
            calc.transform(size=90, rot=(rotx*10, roty))
            calc.rot_x, calc.rot_y = rotx, roty

    if rots:
        rotx, roty, rotz = numpy.array(rots).mean(axis=0)
        calc.rot_x, calc.rot_y = rotx, roty
        prof = calc.profile()

        fileroot, ext = os.path.splitext(filename)
        calc.save_xdi(prof, '{}.xdi'.format(fileroot))

        peaks = find_peaks(prof, width=5)
        print json.dumps({'peak_count': len(peaks)})


def radial_profile(filename, cx=None, cy=None, rotx=None, roty=None):
    # initialize
    calc = FrameProfiler(filename)
    if cx and cy:
        calc.cx = cx
        calc.cy = cy
    if rotx and roty:
        calc.rot_x = rotx
        calc.rot_y = roty

    prof = calc.profile()
    fileroot, ext = os.path.splitext(filename)
    calc.save_xdi(prof, '{}.xdi'.format(fileroot))

    peaks = find_peaks(prof, width=5)
    print json.dumps({'peak_count': len(peaks)})

