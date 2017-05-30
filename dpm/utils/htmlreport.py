# -*- coding: utf-8 -*-

import warnings
warnings.simplefilter("ignore") # ignore deprecation warnings

from dpm.utils import misc, xtal
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.ticker import Formatter, FormatStrFormatter, Locator
import numpy
import os
import sys


from django.conf import settings
settings.configure(TEMPLATE_DIRS=(os.path.join(os.path.dirname(__file__),'templates'),),
                   DEBUG=False,
                   TEMPLATE_DEBUG=False)
from django import template
from django.template import loader, Context

class ZipNode(template.Node):
    def __init__(self, vals, var_name):
        self.vals = vals
        self.var_name = var_name
    
    def render(self, context):
        _vals = [v.resolve(context) for v in self.vals]
        context[self.var_name] = zip(*_vals)
        return ''
        
register = template.Library()
@register.tag(name='zip')
def do_zip(parser, token):

    try:
        args = token.split_contents()
    except ValueError:
        msg = '"zip" tag requires at least 4 arguments'
        raise template.TemplateSyntaxError(msg)
    if len(args) < 5:
        msg = '"zip" tag requires at least 4 arguments'
        raise template.TemplateSyntaxError(msg)
    if args[-2] != 'as':
        msg = 'Last but one argument of "zip" tag must be "as"'
        raise template.TemplateSyntaxError(msg)
    var_name = args[-1]

    vals = map(template.Variable, args[1:-2])
    
    return ZipNode(vals, var_name)

try:
    template.builtins.append(register)
except AttributeError:
    template.base.builtins.append(register)


# Adjust Legend parameters
os.environ['HOME'] = misc.get_home_dir()
os.environ['MPLCONFIGDIR'] = os.path.join(os.environ['HOME'], '.matplotlibrc')

from matplotlib import rcParams
rcParams['legend.loc'] = 'best'
rcParams['legend.fontsize'] = 10
rcParams['legend.isaxes'] = False
rcParams['figure.facecolor'] = 'white'
rcParams['figure.edgecolor'] = 'white'
#rcParams['mathtext.fontset'] = 'cm'

PLOT_WIDTH = 8
PLOT_HEIGHT = 6
PLOT_DPI = 75
IMG_WIDTH = int(round(PLOT_WIDTH * PLOT_DPI))

class ResFormatter(Formatter):
    def __call__(self, x, pos=None):
        if x <= 0.0:
            return u""
        else:
            return u"%0.2f" % (x**-0.5)

class ResLocator(Locator):
    def __init__(self, steps=15):
        self.steps = steps
        
    def __call__(self):
        locs = numpy.linspace(0.0156, 1, self.steps)
        return locs

def get_min_max(a, dev=0.1, houtlier=10000, loutlier=-10000):
    a = numpy.array(a)
    _no_out = (a < houtlier) & (a > loutlier) 
    _std = a[_no_out].std()
    _avg = a[_no_out].mean()
    mn, mx = a[_no_out].min(), a[_no_out].max()
    dev = (mx-mn)*dev
    if (_avg - mn) > 3*_std:
        mn = _avg - 3*_std
    if (mx - _avg) > 3*_std:
        mx = _avg + 3*_std    
    return mn-dev, mx+dev

def plot_shell_stats(results, filename):

    data = results['details'].get('shell_statistics')
    if data is None:
        return
    shell = numpy.array(data['shell'])**-2
    fig = Figure(figsize=(PLOT_WIDTH, PLOT_HEIGHT), dpi=PLOT_DPI)
    ax1 = fig.add_subplot(211)
    ax1.plot(shell, data['completeness'], 'r-')
    ax1.set_ylabel('completeness (%)', color='r')
    ax11 = ax1.twinx()
    ax11.plot(shell, data['r_meas'], 'g-', label='R-meas')
    ax11.plot(shell, data['cc_half'], 'g:+', label='CC(1/2)')
    ax11.legend(loc='center left')
    ax1.grid(True)
    ax11.set_ylabel('R-factors (%)', color='g')
    for tl in ax11.get_yticklabels():
        tl.set_color('g')
    for tl in ax1.get_yticklabels():
        tl.set_color('r')
    ax1.yaxis.set_major_formatter(FormatStrFormatter('%0.0f'))
    ax11.yaxis.set_major_formatter(FormatStrFormatter('%0.0f'))
    ax1.set_ylim(0, 105)
    ax11.set_ylim((0, 105))

    ax2 = fig.add_subplot(212, sharex=ax1)
    ax2.plot(shell, data['i_sigma'], 'm-')
    ax2.set_xlabel('Resolution Shell')
    ax2.set_ylabel('I/SigmaI', color='m')
    ax21 = ax2.twinx()
    ax21.plot(shell, data['sig_ano'], 'b-')
    ax2.grid(True)
    ax21.set_ylabel('SigAno', color='b')
    for tl in ax21.get_yticklabels():
        tl.set_color('b')
    for tl in ax2.get_yticklabels():
        tl.set_color('m')
    ax2.yaxis.set_major_formatter(FormatStrFormatter('%0.0f'))
    ax21.yaxis.set_major_formatter(FormatStrFormatter('%0.1f'))
    ax2.set_ylim(0, get_min_max(data['i_sigma'], 0.1)[1])
    ax21.set_ylim(0, get_min_max(data['sig_ano'], 0.1)[1])

    ax1.xaxis.set_major_formatter(ResFormatter())
    ax1.xaxis.set_minor_formatter(ResFormatter())

    ax2.xaxis.set_major_formatter(ResFormatter())
    ax2.xaxis.set_minor_formatter(ResFormatter())

    canvas = FigureCanvas(fig)
    #response = HttpResponse(content_type='image/png')
    #canvas.print_png(response)
    canvas.print_png(filename)
    return os.path.basename(filename)

def plot_pred_quality(results, filename):

    data = results['details'].get('predicted_quality')
    if data is None:
        return
    shell = numpy.array(data['shell'])**-2
    fig = Figure(figsize=(PLOT_WIDTH, PLOT_HEIGHT), dpi=PLOT_DPI)
    ax1 = fig.add_subplot(211)
    ax1.plot(shell, data['completeness'], 'r-')
    ax1.set_ylabel('completeness (%)', color='r')
    ax11 = ax1.twinx()
    ax11.plot(shell, data['r_factor'], 'g-')
    ax11.legend(loc='center left')
    ax1.grid(True)
    ax11.set_ylabel('R-factor (%)', color='g')
    for tl in ax11.get_yticklabels():
        tl.set_color('g')
    for tl in ax1.get_yticklabels():
        tl.set_color('r')
    ax1.yaxis.set_major_formatter(FormatStrFormatter('%0.0f'))
    ax11.yaxis.set_major_formatter(FormatStrFormatter('%0.0f'))
    ax1.set_ylim((0, 105))
    ax11.set_ylim(0,  get_min_max(data['r_factor'], 0.1)[1])

    ax2 = fig.add_subplot(212, sharex=ax1)
    ax2.plot(shell, data['i_sigma'], 'm-')
    ax2.set_xlabel('Resolution Shell')
    ax2.set_ylabel('I/SigmaI', color='m')
    ax21 = ax2.twinx()
    ax21.plot(shell, data['multiplicity'], 'b-')
    ax2.grid(True)
    ax21.set_ylabel('Multiplicity', color='b')
    for tl in ax21.get_yticklabels():
        tl.set_color('b')
    for tl in ax2.get_yticklabels():
        tl.set_color('m')
    ax2.yaxis.set_major_formatter(FormatStrFormatter('%0.0f'))
    ax21.yaxis.set_major_formatter(FormatStrFormatter('%0.1f'))
    ax2.set_ylim(get_min_max(data['i_sigma'], 0.1))
    ax21.set_ylim(get_min_max(data['multiplicity'],0.1))


    ax1.xaxis.set_major_formatter(ResFormatter())
    ax1.xaxis.set_minor_formatter(ResFormatter())

    ax2.xaxis.set_major_formatter(ResFormatter())
    ax2.xaxis.set_minor_formatter(ResFormatter())

    canvas = FigureCanvas(fig)
    #response = HttpResponse(content_type='image/png')
    #canvas.print_png(response)
    canvas.print_png(filename)
    return os.path.basename(filename)

def plot_overlap_analysis(results, filename):
    
    data = results['details'].get('overlap_analysis')
    if data is None:
        return
    angle = data.pop('angle')
    
    fig = Figure(figsize=(PLOT_WIDTH, PLOT_HEIGHT * 0.7), dpi=PLOT_DPI)
    ax1 = fig.add_subplot(111)
    keys = [(float(k),k) for k in data.keys()]
    for _,k in sorted(keys):       
        ax1.plot(angle, data[k], label=k)
    ax1.set_ylabel('Maximum delta (deg)')
    ax1.grid(True)
    ax1.yaxis.set_major_formatter(FormatStrFormatter('%0.2f'))

    ax1.set_xlabel('Oscillation angle (deg)')
    ax1.legend()

    canvas = FigureCanvas(fig)
    canvas.print_png(filename)
    return os.path.basename(filename)


def plot_wedge_analysis(results, filename):
    
    data = results['details'].get('wedge_analysis')
    if data is None:
        return
    start_angle = data.pop('start_angle')
    
    fig = Figure(figsize=(PLOT_WIDTH, PLOT_HEIGHT), dpi=PLOT_DPI)
    ax1 = fig.add_subplot(111)
    keys = [(float(k),k) for k in data.keys()]
    for _,k in sorted(keys):       
        ax1.plot(start_angle, data[k], label="%s%%" % k)
    ax1.set_ylabel('Total Oscillation Angle (deg)')
    ax1.grid(True)
    ax1.yaxis.set_major_formatter(FormatStrFormatter('%0.2f'))

    ax1.set_xlabel('Starting angle (deg)')
    ax1.legend()

    canvas = FigureCanvas(fig)
    canvas.print_png(filename)
    return os.path.basename(filename)

def plot_exposure_analysis(results, filename):
    
    data = results['details'].get('exposure_analysis')
    if data is None:
        return
    fig = Figure(figsize=(PLOT_WIDTH, PLOT_HEIGHT * 0.7), dpi=PLOT_DPI)
    ax1 = fig.add_subplot(111)
    ax1.plot(data['exposure_time'], data['resolution'])
    ax1.set_ylabel('Resolution')
    ax1.grid(True)
    ax1.yaxis.set_major_formatter(FormatStrFormatter('%0.2f'))

    exposure_time = results['details']['strategy'].get('exposure_time')
    if exposure_time is not None:
        ax1.axvline(x=exposure_time, color='r', label='optimal')
    ax1.set_xlabel('Exposure time (s)')
    ax1.legend()

    canvas = FigureCanvas(fig)
    canvas.print_png(filename)
    return os.path.basename(filename)

def plot_error_stats(results, filename):
    data = results['details'].get('standard_errors')
    if data is None:
        return    
    shell = numpy.array(data['shell'])**-2
    
    fig = Figure(figsize=(PLOT_WIDTH, PLOT_HEIGHT), dpi=PLOT_DPI)
    ax1 = fig.add_subplot(211)
    ax1.plot(shell, data['chi_sq'], 'r-')
    ax1.set_ylabel('Chi^2', color='r')
    ax11 = ax1.twinx()
    ax11.plot(shell, data['i_sigma'], 'b-')
    ax11.set_ylabel('I/Sigma', color='b')
    ax1.grid(True)
    for tl in ax11.get_yticklabels():
        tl.set_color('b')
    for tl in ax1.get_yticklabels():
        tl.set_color('r')
    ax1.yaxis.set_major_formatter(FormatStrFormatter('%0.1f'))
    ax11.yaxis.set_major_formatter(FormatStrFormatter('%0.1f'))
    ax1.set_ylim(get_min_max(data['chi_sq'], 0.2))
    ax11.set_ylim(0, get_min_max(data['i_sigma'], 0.1)[1])

    ax2 = fig.add_subplot(212, sharex=ax1)
    ax2.plot(shell, data['r_obs'], 'g-', label='R-observed')
    ax2.plot(shell, data['r_exp'], 'r:', label='R-expected')
    ax2.set_xlabel('Resolution Shell')
    ax2.set_ylabel('R-factors (%)')
    ax2.legend(loc='best')
    ax2.grid(True)
    ax2.yaxis.set_major_formatter(FormatStrFormatter('%0.0f'))
    ax2.set_ylim(0, get_min_max(data['r_obs'], 0.1)[1])

    ax1.xaxis.set_major_formatter(ResFormatter())
    ax1.xaxis.set_minor_formatter(ResFormatter())
    #ax1.xaxis.set_major_locator(ResLocator())

    ax2.xaxis.set_major_formatter(ResFormatter())
    ax2.xaxis.set_minor_formatter(ResFormatter())
    #ax2.xaxis.set_major_locator(ResLocator())

    canvas = FigureCanvas(fig)
    #response = HttpResponse(content_type='image/png')
    #canvas.print_png(response)
    canvas.print_png(filename)
    return os.path.basename(filename)


def plot_diff_stats(results, filename):
    
    data = results['details'].get('diff_statistics')
    if data is None:
        return
    fig = Figure(figsize=(PLOT_WIDTH, PLOT_HEIGHT * 0.7), dpi=PLOT_DPI)
    ax1 = fig.add_subplot(111)
    ax1.plot(data['frame_diff'], data['rd'], 'r-', label="all")
    ax1.set_ylabel('R-d')
    ax1.grid(True)
    ax1.yaxis.set_major_formatter(FormatStrFormatter('%0.2f'))

    ax1.plot(data['frame_diff'], data['rd_friedel'], 'm-', label="friedel")
    ax1.plot(data['frame_diff'], data['rd_non_friedel'], 'k-', label="non_friedel")
    ax1.set_xlabel('Frame Difference')
    ax1.set_ylim(get_min_max(data['rd_friedel'], 0.1))
    ax1.legend()

    canvas = FigureCanvas(fig)
    canvas.print_png(filename)
    return os.path.basename(filename)

def plot_wilson_stats(results, filename):
    
    data = results['details'].get('wilson_plot')

    if data is None:
        return

    fig = Figure(figsize=(PLOT_WIDTH, PLOT_HEIGHT * 0.7), dpi=PLOT_DPI)
    ax1 = fig.add_subplot(111)
    obs_data = zip(data['inv_res_sq'], data['mean_i'])
    obs_data.sort()
    obs_data = numpy.array(obs_data)
    ax1.plot(obs_data[:,0], obs_data[:,1], 'r-+', label='<I> observed')
    
    if data.get('expected_i'):
        exp_data = zip(data['inv_res_sq'], data['expected_i'])
        exp_data.sort()
        exp_data = numpy.array(exp_data)
        ax1.plot(exp_data[:,0], exp_data[:,1], 'b-', label='<I> expected')
        
    ax1.set_xlabel('Resolution')
    ax1.set_ylabel('<I>')
    ax1.grid(True)
    ax1.xaxis.set_major_formatter(ResFormatter())

    ax1.legend()
    #ax1.xaxis.set_major_locator(ResLocator(40))
    
    canvas = FigureCanvas(fig)
    #response = HttpResponse(content_type='image/png')
    #canvas.print_png(response)
    canvas.print_png(filename)
    return os.path.basename(filename)



def plot_twinning_stats(results, filename):
    
    data = results['details'].get('twinning_l_test')
    if data is None:
        return

    fig = Figure(figsize=(PLOT_WIDTH, PLOT_HEIGHT * 0.7), dpi=PLOT_DPI)
    ax1 = fig.add_subplot(111)
    ax1.plot(data['abs_l'], data['observed'], 'b-+', label='observed')
    ax1.plot(data['abs_l'], data['untwinned'], 'r-+', label='untwinned')
    ax1.plot(data['abs_l'], data['twinned'], 'm-+', label='twinned')
    ax1.set_xlabel('|L|')
    ax1.set_ylabel('P(L>=1)')
    ax1.grid(True)
    
    # set font parameters for the ouput table
    
    l_statistic = results['details'].get('twinning_l_statistic')
    if l_statistic is not None:
        fontpar = {}
        fontpar["family"]="monospace"
        fontpar["size"]=9
        info =  "Observed:     %0.3f\n" % l_statistic[0]
        info += "Untwinned:    %0.3f\n" % l_statistic[1]
        info += "Perfect twin: %0.3f\n" % l_statistic[2]
        fig.text(0.6,0.2, info, fontdict=fontpar, color='k')
    ax1.legend()
    canvas = FigureCanvas(fig)
    #response = HttpResponse(content_type='image/png')
    #canvas.print_png(response)
    canvas.print_png(filename)
    return os.path.basename(filename)


def plot_frame_stats(results, filename):

    data = results['details'].get('frame_statistics')
    if data is None:
        return
    fig = Figure(figsize=(PLOT_WIDTH, PLOT_HEIGHT), dpi=PLOT_DPI)
    ax1 = fig.add_subplot(311)
    ax1.plot(data['frame'], data['scale'], 'r+')
    ax1.set_ylabel('Scale Factor', color='r')
    ax11 = ax1.twinx()
    ax11.plot(data['frame'], data['mosaicity'], 'g+')
    ax1.grid(True)
    ax11.set_ylabel('Mosaicity', color='g')
    for tl in ax11.get_yticklabels():
        tl.set_color('g')
    for tl in ax1.get_yticklabels():
        tl.set_color('r')
    ax1.yaxis.set_major_formatter(FormatStrFormatter('%0.2f'))
    ax11.yaxis.set_major_formatter(FormatStrFormatter('%0.2f'))
    ax1.set_ylim(get_min_max(data['scale'], 0.2))
    ax11.set_ylim(get_min_max(data['mosaicity'], 0.2))

    ax2 = fig.add_subplot(312, sharex=ax1)
    ax2.plot(data['frame'], data['divergence'], 'm+')
    ax2.set_ylabel('Divergence', color='m')
    ax2.set_ylim(get_min_max(data['divergence'], 0.2))
    ax2.yaxis.set_major_formatter(FormatStrFormatter('%0.3f'))
    ax2.grid(True)
    bot_ax = ax2
    if data.get('frame_no') is not None:
        ax21 = ax2.twinx()
        ax21.plot(data['frame_no'], data['i_sigma'], 'b.')

        ax21.set_ylabel('I/Sigma(I)', color='b')
        for tl in ax21.get_yticklabels():
            tl.set_color('b')
        for tl in ax2.get_yticklabels():
            tl.set_color('m')

        ax3 = fig.add_subplot(313, sharex=ax1)
        ax3.plot(data['frame_no'], data['r_meas'], 'k.')
        ax3.set_ylabel('R-meas', color='k')
        ax31 = ax3.twinx()
        ax31.plot(data['frame_no'], data['unique'], 'c.')
        ax3.set_ylim(get_min_max(data['divergence'], 0.5, houtlier=10))
        ax31.set_ylim(-0.1, None)

        ax3.grid(True)
        ax31.set_ylabel('Unique Reflections', color='c')
        for tl in ax31.get_yticklabels():
            tl.set_color('c')
        for tl in ax3.get_yticklabels():
            tl.set_color('k')
        ax21.yaxis.set_major_formatter(FormatStrFormatter('%0.2f'))
        ax3.yaxis.set_major_formatter(FormatStrFormatter('%0.3f'))
        bot_ax = ax3
    bot_ax.set_xlabel('Frame')
    
        

    canvas = FigureCanvas(fig)
    #response = HttpResponse(content_type='image/png')
    #canvas.print_png(response)
    canvas.print_png(filename)
    return os.path.basename(filename)


def plot_batch_stats(results, filename):

    
    data = results['details'].get('integration_batches')
    if data is None:
        return
    
    frames = map(numpy.mean, data['range'])
    beam_x, beam_y = zip(*data['beam_center'])
    cell_a, cell_b, cell_c, cell_alpha, cell_beta, cell_gamma = zip(*data['unit_cell'])
    
    fig = Figure(figsize=(PLOT_WIDTH, PLOT_HEIGHT*1.2), dpi=PLOT_DPI)
    ax1 = fig.add_subplot(411)
    ax1.plot(frames, data['mosaicity'], 'r-')
    ax1.set_ylabel('Mosaicity', color='r')
    ax11 = ax1.twinx()
    ax11.plot(frames, data['distance'], 'g-')
    ax1.grid(True)
    ax11.set_ylabel('Distance', color='g')
    for tl in ax11.get_yticklabels():
        tl.set_color('g')
    for tl in ax1.get_yticklabels():
        tl.set_color('r')
    ax1.yaxis.set_major_formatter(FormatStrFormatter('%0.1f'))
    ax11.yaxis.set_major_formatter(FormatStrFormatter('%0.1f'))
    ax11.set_ylim(get_min_max(data['distance'], 0.1))
    ax1.set_ylim(get_min_max(data['mosaicity'], 0.1))

    ax2 = fig.add_subplot(412, sharex=ax1)
    ax2.plot(frames, data['stdev_spot'], 'm-')
    ax2.set_ylabel('spot dev.', color='m')
    ax2.set_ylim(get_min_max(data['stdev_spot'],0.1))
    ax2.yaxis.set_major_formatter(FormatStrFormatter('%0.2f'))
    ax2.grid(True)
    ax21 = ax2.twinx()
    ax21.plot(frames, data['stdev_spindle'], 'b-')
    ax21.set_ylabel('spindle dev.', color='b')
    for tl in ax21.get_yticklabels():
        tl.set_color('b')
    for tl in ax2.get_yticklabels():
        tl.set_color('m')

    ax3 = fig.add_subplot(413, sharex=ax1)
    ax3.plot(frames, cell_a, label='a')
    ax3.plot(frames, cell_b, label='b')
    ax3.plot(frames, cell_c, label='c')
    
    ax3.set_xlabel('Frame Number')
    ax3.set_ylabel('Unit Cell', color='k')
    ax31 = ax3.twinx()
    ax31.plot(frames, beam_x, label='beam-x')
    ax31.plot(frames, beam_y, label='beam-y')
    ax3.grid(True)
    ax31.set_ylabel('Beam dev. (pix)', color='c')
    for tl in ax31.get_yticklabels():
        tl.set_color('c')
    for tl in ax3.get_yticklabels():
        tl.set_color('k')
    ax21.yaxis.set_major_formatter(FormatStrFormatter('%0.1f'))
    ax3.yaxis.set_major_formatter(FormatStrFormatter('%0.3f'))
    ax31.yaxis.set_major_formatter(FormatStrFormatter('%0.2f'))

    canvas = FigureCanvas(fig)
    #response = HttpResponse(content_type='image/png')
    #canvas.print_png(response)
    canvas.print_png(filename)
    return os.path.basename(filename)



def create_full_report(data, directory):

    report_file = os.path.join(directory,'index.html')
    html=open(report_file, 'w')

    try:
        results = data['result']
        results['space_group_name'] = xtal.SPACE_GROUP_NAMES[results['space_group_id']]
        results['centric'] = '-X,-Y,-Z' in xtal.XTAL_TABLES[results['space_group_id']]['symmetry_operators']
    except KeyError:
        sys.exit(1)

    t = loader.get_template("report.html")    
    c = Context({
            'object': results,
            })
    
    html.write(t.render(c))
    html.close()

    # create plots
    plot_shell_stats(results, os.path.join(directory, 'shell.png'))
    plot_error_stats(results, os.path.join(directory, 'stderr.png'))
    plot_frame_stats(results, os.path.join(directory, 'frame.png'))
    plot_diff_stats(results, os.path.join(directory, 'diff.png'))
    plot_wilson_stats(results, os.path.join(directory, 'wilson.png'))
    plot_twinning_stats(results, os.path.join(directory, 'twinning.png'))
    #plot_batch_stats(results, os.path.join(directory, 'batch.png'))


    return os.path.basename(report_file)

def create_screening_report(data, directory):

    report_file = os.path.join(directory,'index.html')
    html=open(report_file, 'w')

    try:
        results = data['result']
        results['space_group_name'] = xtal.SPACE_GROUP_NAMES[results['space_group_id']]
        results['centric'] = '-X,-Y,-Z' in xtal.XTAL_TABLES[results['space_group_id']]['symmetry_operators']
    except KeyError:
        sys.exit(1)

    t = loader.get_template("screening-report.html")
    c = Context({
            'object': results,
            })
    
    html.write(t.render(c))
    html.close()
    # create plots
    plot_pred_quality(results, os.path.join(directory, 'quality.png'))
    plot_exposure_analysis(results, os.path.join(directory, 'exposure.png'))
    plot_overlap_analysis(results, os.path.join(directory, 'overlap.png'))
    plot_wedge_analysis(results, os.path.join(directory, 'wedge.png'))

    return os.path.basename(report_file)
