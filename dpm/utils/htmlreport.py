import warnings
warnings.simplefilter("ignore") # ignore deprecation warnings
import os
import sys
import numpy
from dpm.utils import json, misc
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.ticker import Formatter, FormatStrFormatter, Locator
from matplotlib.figure import Figure
from matplotlib.colors import LogNorm, Normalize
import matplotlib.cm as cm

from django.conf import settings
settings.configure(TEMPLATE_DIRS=(os.path.join(os.path.dirname(__file__),'templates'),),
                   DEBUG=False,
                   TEMPLATE_DEBUG=False)
from django import template
from django.template import Template, loader, Context

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
template.builtins.append(register)


# Adjust Legend parameters
from matplotlib import rcParams
rcParams['legend.loc'] = 'best'
rcParams['legend.fontsize'] = 10
rcParams['legend.isaxes'] = False
rcParams['figure.facecolor'] = 'white'
rcParams['figure.edgecolor'] = 'white'

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
    def __call__(self, *args, **kwargs):
        locs = numpy.linspace(0.0156, 1, 30 )
        return locs

def plot_shell_stats(results, filename):

    data = results['details']['shell_statistics']
    shell = numpy.array(data['shell'])**-2
    fig = Figure(figsize=(PLOT_WIDTH, PLOT_HEIGHT), dpi=PLOT_DPI)
    ax1 = fig.add_subplot(211)
    ax1.plot(shell, data['completeness'], 'r-')
    ax1.set_ylabel('completeness (%)', color='r')
    ax11 = ax1.twinx()
    ax11.plot(shell, data['r_meas'], 'g-', label='R-meas')
    ax11.plot(shell, data['r_mrgdf'], 'g:+', label='R-mrgd-F')
    ax11.legend(loc='center left')
    ax1.grid(True)
    ax11.set_ylabel('R-factors (%)', color='g')
    for tl in ax11.get_yticklabels():
        tl.set_color('g')
    for tl in ax1.get_yticklabels():
        tl.set_color('r')
    ax1.yaxis.set_major_formatter(FormatStrFormatter('%0.0f'))
    ax11.yaxis.set_major_formatter(FormatStrFormatter('%0.0f'))
    ax1.set_ylim((0, 105))
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
    ax2.set_ylim((-5, max(data['i_sigma'])+5))
    ax21.set_ylim((0, max(data['sig_ano'])+1))

    ax1.xaxis.set_major_formatter(ResFormatter())
    ax1.xaxis.set_minor_formatter(ResFormatter())
    ax1.xaxis.set_major_locator(ResLocator())
    ax2.xaxis.set_major_formatter(ResFormatter())
    ax2.xaxis.set_minor_formatter(ResFormatter())
    ax2.xaxis.set_major_locator(ResLocator())

    canvas = FigureCanvas(fig)
    #response = HttpResponse(content_type='image/png')
    #canvas.print_png(response)
    canvas.print_png(filename)
    return os.path.basename(filename)

def plot_error_stats(results, filename):
    data = results['details']['standard_errors']
    shell = numpy.array(data['shell'])**-2
    
    fig = Figure(figsize=(PLOT_WIDTH, PLOT_HEIGHT), dpi=PLOT_DPI)
    ax1 = fig.add_subplot(211)
    ax1.plot(shell, data['chi_sq'], 'r-')
    ax1.set_ylabel(r'$\chi^{2}$', color='r')
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
    ax1.set_ylim((0, 3))
    #ax11.set_ylim((0, 105))

    ax2 = fig.add_subplot(212, sharex=ax1)
    ax2.plot(shell, data['r_obs'], 'g-', label='R-observed')
    ax2.plot(shell, data['r_exp'], 'r:', label='R-expected')
    ax2.set_xlabel('Resolution Shell')
    ax2.set_ylabel('R-factors (%)')
    ax2.legend(loc='best')
    ax2.grid(True)
    ax2.yaxis.set_major_formatter(FormatStrFormatter('%0.0f'))
    ax2.set_ylim((0,105))

    ax1.xaxis.set_major_formatter(ResFormatter())
    ax1.xaxis.set_minor_formatter(ResFormatter())
    ax1.xaxis.set_major_locator(ResLocator())

    ax2.xaxis.set_major_formatter(ResFormatter())
    ax2.xaxis.set_minor_formatter(ResFormatter())
    ax2.xaxis.set_major_locator(ResLocator())

    canvas = FigureCanvas(fig)
    #response = HttpResponse(content_type='image/png')
    #canvas.print_png(response)
    canvas.print_png(filename)
    return os.path.basename(filename)


def plot_diff_stats(results, filename):
    
    data = results['details']['diff_statistics']
    fig = Figure(figsize=(PLOT_WIDTH, PLOT_HEIGHT * 0.6), dpi=PLOT_DPI)
    ax1 = fig.add_subplot(111)
    ax1.plot(data['frame_diff'], data['rd'], 'r-', label="all")
    ax1.set_ylabel('R-d')
    ax1.grid(True)
    ax1.yaxis.set_major_formatter(FormatStrFormatter('%0.2f'))

    ax1.plot(data['frame_diff'], data['rd_friedel'], 'm-', label="friedel")
    ax1.plot(data['frame_diff'], data['rd_non_friedel'], 'k-', label="non_friedel")
    ax1.set_xlabel('Frame Difference')
    ax1.legend()

    canvas = FigureCanvas(fig)
    canvas.print_png(filename)
    return os.path.basename(filename)

def plot_wilson_stats(results, filename):
    
    data = results['details']['wilson_plot']

    fig = Figure(figsize=(PLOT_WIDTH, PLOT_HEIGHT * 0.6), dpi=PLOT_DPI)
    ax1 = fig.add_subplot(111)
    plot_data = zip(data['inv_res_sq'], data['log_i_sigma'])
    plot_data.sort()
    plot_data = numpy.array(plot_data)
    ax1.plot(plot_data[:,0], plot_data[:,1], 'r-+')
    ax1.set_xlabel('Resolution')
    ax1.set_ylabel(r'$ln({<I>}/{\Sigma(f)^2})$')
    ax1.grid(True)
    ax1.xaxis.set_major_formatter(ResFormatter())
    ax1.xaxis.set_major_locator(ResLocator())
    
    # set font parameters for the ouput table
    wilson_line = results['details'].get('wilson_line')
    wilson_scale = results['details'].get('wilson_scale')
    if wilson_line is not None:
        fontpar = {}
        fontpar["family"]="monospace"
        fontpar["size"]=9
        info =  "Estimated B: %0.3f\n" % wilson_line[0]
        info += "sigma a: %8.3f\n" % wilson_line[1]
        info += "sigma b: %8.3f\n" % wilson_line[2]
        if wilson_scale is not None:
            info += "Scale factor: %0.3f\n" % wilson_scale    
        fig.text(0.55,0.65, info, fontdict=fontpar, color='k')

    canvas = FigureCanvas(fig)
    #response = HttpResponse(content_type='image/png')
    #canvas.print_png(response)
    canvas.print_png(filename)
    return os.path.basename(filename)

def plot_twinning_stats(results, filename):
    
    data = results['details']['twinning_l_test']

    fig = Figure(figsize=(PLOT_WIDTH, PLOT_HEIGHT * 0.6), dpi=PLOT_DPI)
    ax1 = fig.add_subplot(111)
    ax1.plot(data['abs_l'], data['observed'], 'b-+', label='observed')
    ax1.plot(data['abs_l'], data['untwinned'], 'r-+', label='untwinned')
    ax1.plot(data['abs_l'], data['twinned'], 'm-+', label='twinned')
    ax1.set_xlabel('$|L|$')
    ax1.set_ylabel('$P(L>=1)$')
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
    
    #try:
    #    project = request.user.get_profile()
    #    result = project.result_set.get(pk=id)
    #except:
    #    raise Http404
    # extract shell statistics to plot
    data = results['details']['frame_statistics']
    fig = Figure(figsize=(PLOT_WIDTH, PLOT_HEIGHT), dpi=PLOT_DPI)
    ax1 = fig.add_subplot(311)
    ax1.plot(data['frame'], data['scale'], 'r-')
    ax1.set_ylabel('Scale Factor', color='r')
    ax11 = ax1.twinx()
    ax11.plot(data['frame'], data['mosaicity'], 'g-')
    ax1.grid(True)
    ax11.set_ylabel('Mosaicity', color='g')
    for tl in ax11.get_yticklabels():
        tl.set_color('g')
    for tl in ax1.get_yticklabels():
        tl.set_color('r')
    ax1.yaxis.set_major_formatter(FormatStrFormatter('%0.1f'))
    ax11.yaxis.set_major_formatter(FormatStrFormatter('%0.2f'))
    ax1.set_ylim((min(data['scale'])-0.2, max(data['scale'])+0.2))
    ax11.set_ylim((min(data['mosaicity'])-0.01, max(data['mosaicity'])+0.01))

    ax2 = fig.add_subplot(312, sharex=ax1)
    ax2.plot(data['frame'], data['divergence'], 'm-')
    ax2.set_ylabel('Divergence', color='m')
    ax2.set_ylim((min(data['divergence'])-0.02, max(data['divergence'])+0.02))
    ax2.yaxis.set_major_formatter(FormatStrFormatter('%0.3f'))
    ax2.grid(True)
    if data.get('frame_no') is not None:
        ax21 = ax2.twinx()
        ax21.plot(data['frame_no'], data['i_sigma'], 'b-')

        ax21.set_ylabel('I/Sigma(I)', color='b')
        for tl in ax21.get_yticklabels():
            tl.set_color('b')
        for tl in ax2.get_yticklabels():
            tl.set_color('m')

        ax3 = fig.add_subplot(313, sharex=ax1)
        ax3.plot(data['frame_no'], data['r_meas'], 'k-')
        ax3.set_xlabel('Frame Number')
        ax3.set_ylabel('R-meas', color='k')
        ax31 = ax3.twinx()
        ax31.plot(data['frame_no'], data['unique'], 'c-')
        ax3.grid(True)
        ax31.set_ylabel('Unique Reflections', color='c')
        for tl in ax31.get_yticklabels():
            tl.set_color('c')
        for tl in ax3.get_yticklabels():
            tl.set_color('k')
        ax21.yaxis.set_major_formatter(FormatStrFormatter('%0.1f'))
        ax3.yaxis.set_major_formatter(FormatStrFormatter('%0.3f'))
        ax31.yaxis.set_major_formatter(FormatStrFormatter('%0.0f'))

    canvas = FigureCanvas(fig)
    #response = HttpResponse(content_type='image/png')
    #canvas.print_png(response)
    canvas.print_png(filename)
    return os.path.basename(filename)

def plot_profiles(results, filename):
    from mpl_toolkits.axes_grid import AxesGrid
    profiles = results['details'].get('integration_profiles')
    if profiles is None:
        return ''
    fig = Figure(figsize=(PLOT_WIDTH, PLOT_WIDTH), dpi=PLOT_DPI)
    cmap = cm.get_cmap('gray_r')
    norm = Normalize(None, 100, clip=True)
    grid = AxesGrid(fig, 111,
                    nrows_ncols = (9,10),
                    share_all=True,
                    axes_pad = 0,
                    label_mode = '1',
                    cbar_mode=None,
                    )
    for i, profile in enumerate(profiles):
        grid[i*10].plot([profile['x']],[profile['y']], 'cs', markersize=15)
        for loc in ['left','top','bottom','right']:
            grid[i*10].axis[loc].toggle(ticklabels=False, ticks=False)
        for j,spot in enumerate(profile['spots']):
            idx = i*10 + j+1
            _a = numpy.array(spot).reshape((9,9))
            intpl = 'nearest' #'mitchell'
            grid[idx].imshow(_a, cmap=cmap, norm=norm, interpolation=intpl)
            for loc in ['left','top','bottom','right']:
                grid[idx].axis[loc].toggle(ticklabels=False, ticks=False)
    canvas = FigureCanvas(fig)
    canvas.print_png(filename, bbox_inches='tight')
    return os.path.basename(filename)


def create_full_report(data, directory):

    report_file = os.path.join(directory,'index.html')
    html=open(report_file, 'w')

    try:
        results = data['result']
    except KeyError:
        sys.exit(1)

    # create plots
    plot_shell_stats(results, os.path.join(directory, 'shell.png'))
    plot_error_stats(results, os.path.join(directory, 'stderr.png'))
    plot_frame_stats(results, os.path.join(directory, 'frame.png'))
    plot_diff_stats(results, os.path.join(directory, 'diff.png'))
    plot_wilson_stats(results, os.path.join(directory, 'wilson.png'))
    plot_twinning_stats(results, os.path.join(directory, 'twinning.png'))

    t = loader.get_template("report.html")    
    c = Context({
            'object': results,
            })
    
    html.write(t.render(c))
    html.close()
    return os.path.basename(report_file)

# Currently the same
create_screening_report = create_full_report

if __name__ == '__main__':
    json_file = sys.argv[1]
    if os.path.exists(json_file):
        data = json.load(file(json_file))

        report_directory = os.path.join(
                                os.path.dirname(os.path.abspath(json_file)),
                                'report')
        if not os.path.exists(report_directory):
            os.mkdir(report_directory)
        
        for report in data['result']:
            report_directory = os.path.join(report['result']['url'],'report')
            if not os.path.exists(report_directory):
                os.makedirs(report_directory)
            create_full_report(report, report_directory)
                
