import warnings
warnings.simplefilter("ignore") # ignore deprecation warnings

import re
import string
import sys
import os
import numpy
try: 
    import json
except:
    import simplejson as json
    
import cStringIO
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.ticker import Formatter, FormatStrFormatter, Locator
from matplotlib.figure import Figure
from matplotlib.colors import LogNorm, Normalize
import matplotlib.cm as cm
from dpm.autoxds.utils import SPACE_GROUP_NAMES


# Adjust Legend parameters
os.environ['MPLCONFIGDIR'] = '/tmp/matplotlibrc'
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


HTML_TEMPLATE = """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN">
<html>
<head>
<title>AutoProcess - Data processing report</title>
<link href='http://fonts.googleapis.com/css?family=Ubuntu:regular,italic,bold,bolditalic' rel='stylesheet' type='text/css'>
<style type="text/css">
body {
 font-size: 14px; font-family: Ubuntu, sans-serif; line-height: 130%;
}
#result-page {
 margin: 0 auto; text-align:left; padding:0px;
}
#result-table {
 font-size: 88%; border-collapse:collapse; text-align:left; width: 100%;
}
#result-table th {
 color:#003399; font-size: 1.2em; font-weight:normal; padding:8px 8px;
}
#result-table td {
 border-top:1px solid #eee; padding:5px 8px;
}
#strategy-table {
 font-size: 88%; border-collapse:collapse; text-align:left; width: 45%;
}
#strategy-table td {
 border-top:1px solid #eee; padding:5px 8px;
}
.result-labels {
 font-weight: bold;
}
#result-summary {
 border-collapse:collapse; border:1px solid #ccc; float: left; text-align:left;
}
div.tablenotes {
 font-size: 90%; background:#EFF6FF none repeat scroll 0 0; padding: 20px; margin-bottom: 10px;
}
div.tablenotes h3 {
 padding: 0px; margin: 0px;
}
dl.note-list {
 margin-bottom: 0px;
}
dl.note-list dt {
 float: left; clear: left; text-align: right; font-weight: bold; color: #000;
}
dl.note-list dd {
 margin: 0 0 0 3em; padding: 0 0 0.5em 0;
}
h1, h2, h3, h4 {
 display: block;
 font-weight:normal; margin-top:1.4em;
 page-break-after: avoid;
}
#result-title h2{
 font-size:190%; line-height:1.2em; margin-bottom:0.8em; margin-top: 1em; color: #666666;
}
div.spacer {
 padding: 5px 0;
}
.clear {
clear: both !important;
}
.pagebreak {
clear: both !important; display: block; page-break-after: always;
}
p {
 margin: 0.7em 0px;
}
#result-page h3 {
 font-size: 130%; border-bottom: 1px dotted #ccc;
 margin-top: 0.3em; page-break-after: avoid;
}
.full {
 width: 100% !important;
}
.rtable {
 border-collapse:collapse; text-align:left; border: solid 1px #ccc; margin: 8px 0px;
}
.rtable th {
 color: rgb(102, 153, 204); font-weight: bold; padding:4px 4px; text-align: right; font-size: 80%;
}
.rtable td {
 text-align: right; font-family: Consolas, monospace; border-top:1px solid #eee; color:#666699; padding:5px 8px; font-size: 12px;
}
.floatleft {
 float: left;
}
.floatright {
 float: right;
}
div.image {
 display: block;
 margin: 0 auto;
 page-break-inside: avoid;
 float: none;
}
</style>
</head>
<body>
"""



class TAG:
    """Generic class for tags"""
    def __init__(self, inner_HTML="", **attrs):
        self.tag = self.__class__.__name__
        self.inner_HTML = inner_HTML
        self.attrs = attrs
        self.children = []
        self.brothers = []
    
    def __str__(self):
        res=cStringIO.StringIO()
        w=res.write
        if self.tag != "TEXT":
            w("<%s" %self.tag.lower())
            # attributes which will produce arg = "val"
            attr1 = [ k for k in self.attrs 
                if not isinstance(self.attrs[k],bool) ]
            w("".join([' %s="%s"' 
                %(k.replace('_','-').lower(),self.attrs[k]) for k in attr1]))
            # attributes with no argument
            # if value is False, don't generate anything
            attr2 = [ k.lower() for k in self.attrs if self.attrs[k] is True ]
            w("".join([' %s' %k for k in attr2]))
            w(">")
        if self.tag in ONE_LINE:
            w('\n')
        w(str(self.inner_HTML))
        for child in self.children:
            w(str(child))
        if self.tag in CLOSING_TAGS:
            w("</%s>" %self.tag.lower())
        if self.tag in LINE_BREAK_AFTER:
            w('\n')
        if hasattr(self,"brothers"):
            for brother in self.brothers:
                w(str(brother))
        return res.getvalue()

    def __le__(self,other):
        """Add a child"""
        if isinstance(other,str):
            other = TEXT(other)
        self.children.append(other)
        other.parent = self
        return self

    def __add__(self,other):
        """Return a new instance : concatenation of self and another tag"""
        res = TAG()
        res.tag = self.tag
        res.inner_HTML = self.inner_HTML
        res.attrs = self.attrs
        res.children = self.children
        res.brothers = self.brothers + [other]
        return res

    def __radd__(self,other):
        """Used to add a tag to a string"""
        if isinstance(other,str):
            return TEXT(other)+self
        else:
            raise ValueError,"Can't concatenate %s and instance" %other

    def __mul__(self,n):
        """Replicate self n times, with tag first : TAG * n"""
        res = TAG()
        res.tag = self.tag
        res.inner_HTML = self.inner_HTML
        res.attrs = self.attrs
        for i in range(n-1):
            res += self
        return res

    def __rmul__(self,n):
        """Replicate self n times, with n first : n * TAG"""
        return self*n

# list of tags, from the HTML 4.01 specification

CLOSING_TAGS =  ['A', 'ABBR', 'ACRONYM', 'ADDRESS', 'APPLET',
            'B', 'BDO', 'BIG', 'BLOCKQUOTE', 'BUTTON',
            'CAPTION', 'CENTER', 'CITE', 'CODE',
            'DEL', 'DFN', 'DIR', 'DIV', 'DL',
            'EM', 'FIELDSET', 'FONT', 'FORM', 'FRAMESET',
            'H1', 'H2', 'H3', 'H4', 'H5', 'H6',
            'I', 'IFRAME', 'INS', 'KBD', 'LABEL', 'LEGEND',
            'MAP', 'MENU', 'NOFRAMES', 'NOSCRIPT', 'OBJECT',
            'OL', 'OPTGROUP', 'PRE', 'Q', 'S', 'SAMP',
            'SCRIPT', 'SELECT', 'SMALL', 'SPAN', 'STRIKE',
            'STRONG', 'STYLE', 'SUB', 'SUP', 'TABLE',
            'TEXTAREA', 'TITLE', 'TT', 'U', 'UL',
            'VAR', 'BODY', 'COLGROUP', 'DD', 'DT', 'HEAD',
            'HTML', 'LI', 'P', 'TBODY','OPTION', 
            'TD', 'TFOOT', 'TH', 'THEAD', 'TR']

NON_CLOSING_TAGS =  ['AREA', 'BASE', 'BASEFONT', 'BR', 'COL', 'FRAME',
            'HR', 'IMG', 'INPUT', 'ISINDEX', 'LINK',
            'META', 'PARAM']

# create the classes
for tag in CLOSING_TAGS + NON_CLOSING_TAGS + ['TEXT']:
    exec("class %s(TAG): pass" %tag)
    
def Sum(iterable):
    """Return the concatenation of the instances in the iterable
    Can't use the built-in sum() on non-integers"""
    it = [ item for item in iterable ]
    if it:
        return reduce(lambda x,y:x+y, it)
    else:
        return ''

# whitespace-insensitive tags, determines pretty-print rendering
LINE_BREAK_AFTER = NON_CLOSING_TAGS + ['HTML','HEAD','BODY',
    'FRAMESET','FRAME',
    'TITLE','SCRIPT',
    'TABLE','TR','TD', 'TH','SELECT','OPTION',
    'FORM','DIV','DL','DD','P',
    'H1', 'H2', 'H3', 'H4', 'H5', 'H6',
    ]
# tags whose opening tag should be alone in its line
ONE_LINE = ['HTML','HEAD','BODY',
    'FRAMESET'
    'SCRIPT','TR','DL',
    'TABLE','SELECT','OPTION',
    'FORM','DIV'
    ]


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
    prefix = ''
    report_file = os.path.join(directory,'index.html')
    html=open(report_file, 'w')

    try:
        results = data['result']
        strategy = data.get('strategy', None)
    except KeyError:
        #base = data[data.keys()[0]]
        #results = base[base.keys()[0]]['result']
        sys.exit(1)

    clear = (DIV('', Class="clear"))    
    spacer = (DIV('', Class="clear spacer"))
    pagebreak = (DIV('', Class="pagebreak"))

    result_table_head = (COLGROUP(COL('', Class='result-labels'))
                         )
    sg_name = SPACE_GROUP_NAMES[results['space_group_id']]
    result_table_body = (TBODY(TR(TD('Score'+(SUP('[1]', Class="footnote")))+TD("%0.2f" % results['score']))+
                               TR(TD('Wavelength (A)')+TD(results['wavelength']))+    
                               TR(TD('Space Group'+(SUP('[2]', Class="footnote")))+TD(sg_name))+  
                               TR(TD('Unit Cell (A)')+TD("%0.1f %0.1f %0.1f <br> %0.1f %0.1f %0.1f" % (results['cell_a'], results['cell_b'], results['cell_c'], results['cell_alpha'], results['cell_beta'], results['cell_gamma'])))+  
                               TR(TD('Resolution'+(SUP('[3]', Class="footnote")))+TD("%0.2f" % results['resolution']))+  
                               TR(TD('All Reflections')+TD(results['reflections']))+
                               TR(TD('Unique Reflections')+TD(results['unique']))+
                               TR(TD('Multiplicity')+TD("%0.1f" % results['multiplicity']))+
                               TR(TD('Completeness (%)')+TD(results['completeness']))+
                               TR(TD('Mosaicity')+TD("%0.2f" % results['mosaicity']))+
                               TR(TD('I/Sigma (I)')+TD(results['i_sigma']))+
                               TR(TD('R-meas'+(SUP('[4]', Class="footnote")))+TD(results['r_meas']))+
                               TR(TD('R-mrgd-F'+(SUP('[5]', Class="footnote")))+TD(results['r_mrgdf']))+
                               TR(TD('Spot deviation')+TD(results['sigma_spot']))+
                               TR(TD('Spindle deviation')+TD(results['sigma_angle']))+
                               TR(TD('Ice Rings')+TD(results['ice_rings']))
                                  ))
    result_table = (TABLE(result_table_head+result_table_body, id="result-table", summary="Summary of data processing results."))                    

    summary = H3('Summary')+DIV(result_table, id="result-summary", style="width: %dpx;" % ((IMG_WIDTH/2) - 10))

    lattice_title = H3('Compatible Bravais Lattice Types')
    lattice_table = TABLE()
    lattice_table_head = THEAD(TR(TH('No.', scope="col")+
                                   TH('Lattice Type', scope="col")+
                                   TH('Cell Parameters', scope="col")+
                                   TH('Quality', scope="col")+
                                   TH('Cell Volume', scope="col")))
    lattice_table_body = TBODY()
    lattices = results['details']['compatible_lattices']
    for x in range(len(lattices['id'])):
        row = TR()
        row <= (TD(lattices['id'][x])+
                TD(lattices['type'][x]))
        unit_cell_td = ''
        unit_cells = lattices['unit_cell'][x].split()
        for y in range(len(unit_cells)):
            if y == 3:
                unit_cell_td = unit_cell_td + '<br>'
                unit_cell_td = unit_cell_td + str(unit_cells[y]) + ' '
            else:
                unit_cell_td = unit_cell_td + str(unit_cells[y]) + ' '
        row <= TD(unit_cell_td)
        row <= (TD(lattices['quality'][x])+
                TD("%i" % lattices['volume'][x]))
        lattice_table_body <= row
    lattice_table = TABLE(lattice_table_head+lattice_table_body, Class="rtable full", summary="Compatible lattices.")

    notes = (DIV(H3('Notes')+DL(DT('[1] - ')+DD('Data Quality Score for comparing similar data sets. Typically, values > 0.8 are excellent, > 0.6 are good, > 0.5 are acceptable, > 0.4 marginal, and &lt; 0.4 are Barely usable')+
                                DT('[2] - ')+DD('This space group was automatically assigned using POINTLESS (see P.R.Evans, Acta Cryst. D62, 72-82, 2005). This procedure is unreliable for incomplete datasets such as those used for screening. Please Inspect the detailed results below.')+
                                DT('[3] - ')+DD('Resolution selected based on a cut-off of I/sigma(I) > 1.0. Statistics presented reflect this resolution.')+
                                DT('[4] - ')+DD('Redundancy independent R-factor. (see Diederichs &amp; Karplus, 1997, Nature Struct. Biol. 4, 269-275.)')+
                                DT('[5] - ')+DD('Quality of amplitudes. (see Diederichs &amp; Karplus, 1997, Nature Struct. Biol. 4, 269-275.)'), Class="note-list"), 
                                Class="tablenotes floatright", style="width: %dpx;" % ((IMG_WIDTH/2) - 45)))   
   
    notes_spacegroup = (DIV(H3('Notes')+
                            P('The above table contains results from POINTLESS (see Evans, Acta Cryst. D62, 72-82, 2005).')+
                            P('Indistinguishable space groups will have similar probabilities. If two or more of the top candidates have the same probability, the one with the fewest symmetry assumptions is chosen. This usually corresponds to the point group,  trying out higher symmetry space groups within the top tier does not require re-indexing the data as they are already in the same setting.')+
                            P("For more detailed results, please inspect the output file 'pointless.log'."), Class="tablenotes"))
 
    pointless_table_head = THEAD(TR(TH('Selected', scope="col")+
                                   TH('Candidates', scope="col")+
                                   TH('Space Group No.', scope="col")+
                                   TH('Probability', scope="col")))
    pointless_table_body = TBODY()
    pointless = results['details']['spacegroup_selection']
    for x in range(len(pointless['name'])):
        row = TR()
        if x == 0:
            row <= (TD('*')+
                    TD(pointless['name'][x])+
                    TD(pointless['space_group'][x])+
                    TD(pointless['probability'][x]))
        else:
            row <= (TD('')+
                    TD(pointless['name'][x])+
                    TD(pointless['space_group'][x])+
                    TD(pointless['probability'][x]))
        pointless_table_body <= row
    pointless_table = H3('Automatic Space-Group Selection')+TABLE(pointless_table_head+pointless_table_body, Class="rtable full", summary="Spacegroup Selection.") 

    shell_title = H3('Statistics of final reflections by shell')
    shell_table_head = THEAD(TR(TH('Shell', scope="col")+
                              TH('Completeness', scope="col")+
                              TH('R'+SUB('meas'), scope="col")+
                              TH('R'+SUB('mrgd-F'), scope="col")+
                              TH('I/sigma (I)'+SUP('[1]', Class="footnote"), scope="col")+
                              TH('Sig'+SUB('ano')+SUP('[2]', Class="footnote"), scope="col"))) 
    shell_table_body = TBODY()
    shell_data = results['details']['shell_statistics']
    for x in range(len(shell_data['completeness'])):
        row = TR()
        row <= (TD(shell_data['shell'][x])+
                TD(shell_data['completeness'][x])+
                TD(shell_data['r_meas'][x])+
                TD(shell_data['r_mrgdf'][x])+
                TD(shell_data['i_sigma'][x])+
                TD(shell_data['sig_ano'][x]))
        shell_table_body <= row
    shell_table = TABLE(shell_table_head + shell_table_body, Class="rtable full", summary="Statistics of dataset by shell.")

    shell_notes = (DIV(H3('Notes')+DL(DT('[1] - ')+DD('Mean of intensity/Sigma(I) of unique reflections (after merging symmetry-related observations). Where Sigma(I) is the standard deviation of reflection intensity I estimated from sample statistics.')+
                                      DT('[2] - ')+DD('mean anomalous difference in units of its estimated standard deviation (|F(+)-F(-)|/Sigma). F(+), F(-) are structure factor estimates obtained from the merged intensity observations in each parity class.'), Class="note-list"), Class="tablenotes"))   
   
    frame_notes = (DIV(H3('Notes')+
                        P("The above plot was calculated by XDSSTAT. See See Diederichs K. (2006) Acta Cryst D62, 96-101.")+
                        DL(
                        DT('Divergence - ')+DD('Estimated Standard Deviation of Beam divergence')+
                        DT('R'+SUB('d')+' - ')+DD('R-factors as a function of frame difference. An increase in R-d with frame difference is suggestive of radiation damage.'), Class="note-list"), Class="tablenotes"))   

    strategy_notes = (DIV(H3('Notes')+DL(DT('[a] - ')+DD('Recommended exposure time does not take into account overloads at low resolution!')+
                                         DT('[b] - ')+DD('Values in parenthesis represent the high resolution shell.')+
                                         DT('[c] - ')+DD('Resolution limit is set by the initial image resolution.'), Class="note-list"), Class="tablenotes floatright size40"))   

    plot_shell = plot_shell_stats(results, os.path.join(directory, '%sshell.png' % prefix))
    shell_img = DIV(IMG(src=plot_shell), Class="image")
    
    shell_report = (shell_title + shell_img + shell_table + shell_notes + spacer)

#    profile_notes = DIV(H3('Notes')+
#                      P("Profiles are determined at 9 region on the detector surface shown on the left-most column.")+
#                      P("Nice slices for the corresponding detector region are shown on the right of each region "),
#                      Class="tablenotes")
#    profile_plot = plot_profiles(results, os.path.join(directory, '%sprofiles.png' % prefix))
#    profile_report = ""
#    if profile_plot != "":
#        profile_report = DIV(H3('Reference Profiles as a function of detector region')+
#                         IMG(src=profile_plot), 
#                         Class="image")+clear+profile_notes
#    else:
#        profile_report = ""
    plot_stderr = plot_error_stats(results, os.path.join(directory, '%sstderr.png' % prefix))
    stderr_notes = DIV(H3('Notes')+DL(
                       DT('I/Sigma    - ')+DD('Mean intensity/Sigma of a reflection in shell')+
                       DT('&chi;&sup2;  - ')+DD('Goodness of fit between sample variances of symmetry-related intensities and their errors (&chi;&sup2; = 1 for perfect agreement).')+
                       DT('R-observed - ')+DD('&Sigma;|I(h,i)-I(h)| / &Sigma;[I(h,i)]')+
                       DT('R-expected - ')+DD('Expected R-FACTOR derived from Sigma(I)'), Class="note-list"), 
                       Class="tablenotes")   
    stderr_report = DIV(H3('Standard errors of reflection intensities by resolution')+
                         IMG(src=plot_stderr), 
                         Class="image")+clear+ stderr_notes
    if results['kind'] == 0:
        kind = "Crystal Screening Report - &ldquo;%s&rdquo;" % results['name']
        strategy_title = H3('Data Collection Strategy')+P('Recommended Strategy for Native Data Collection')
        if strategy is not None:
            strategy_data = strategy
            strategy_table_body = TBODY(TR(TD('Attenuation (%)')+TD(strategy_data['attenuation']))+
                                        TR(TD('Distance (mm)')+TD(strategy_data['distance']))+
                                        TR(TD('Start Angle')+TD(strategy_data['start_angle']))+
                                        TR(TD('Delta (deg)')+TD(strategy_data['delta_angle']))+
                                        TR(TD('No. Frames')+TD(strategy_data['total_angle']/strategy_data['delta_angle']))+
                                        TR(TD('Total Angle (deg)')+TD(strategy_data['total_angle']))+
                                        TR(TD('Exposure Time (s) [a]')+TD(strategy_data['exposure_time']))+
                                        TR(TD(B('Expected Quality:')+TD(''))+
                                        TR(TD('Resolution [c]')+TD(strategy_data['exp_resolution']))+
                                        TR(TD('Completeness (%)')+TD(strategy_data['exp_completeness']))+
                                        TR(TD('Multiplicity')+TD(strategy_data['exp_multiplicity']))+
                                        TR(TD('I/sigma (I) [b]')+TD(strategy_data['exp_i_sigma']))+
                                        TR(TD('R-factor (%) [b]')+TD(strategy_data.get('exp_r_factor',''))))) 
            strategy = strategy_title + TABLE(strategy_table_body, id="strategy-table", Class="floatleft") + strategy_notes
            dp_report = (strategy + clear + stderr_report + pagebreak + shell_report + clear)
    elif results['kind'] == 1:
        kind = "Data Processing Report - &ldquo;%s&rdquo;" % results['name']
        plot_frame = plot_frame_stats(results, os.path.join(directory, '%sframe.png' % prefix))
        plot_diff = plot_diff_stats(results, os.path.join(directory, '%sdiff.png' % prefix))
        plot_wilson = plot_wilson_stats(results, os.path.join(directory, '%swilson.png' % prefix))
        plot_twinning = plot_twinning_stats(results, os.path.join(directory, '%stwinning.png' % prefix))
        
        wilson_notes = DIV(H3('Notes')+
                          P("The above clipper-style wilson plot was calculated by CTRUNCATE which is part of the CCP4 Package.")+
                          P("See S. French and K. Wilson, Acta Cryst. A34, 517-525 (1978)."),
                          Class="tablenotes")
        
        twinning_notes = DIV(H3('Notes')+
                          P("The above plot was calculated by CTRUNCATE which is part of the CCP4 Package.")+
                          P("All data regardless of I/sigma(I) has been included in the L test. Anisotropy correction has been applied before calculating L.")+
                          P("See J. E. Padilla and T. O. Yeates, Acta Cryst. D59, 1124-1130 (2003)"),
                          Class="tablenotes")



        dp_report = (stderr_report +
                     pagebreak + shell_report+ pagebreak +
                      DIV(H3('Statistics of final reflections (by frame and frame difference)')+
                          IMG(src=plot_frame), Class="image")+clear+
                     DIV(IMG(src=plot_diff), Class="image")+clear+
                     frame_notes+
                     DIV(H3('Wilson Plot')+
                         IMG(src=plot_wilson), Class="image")+clear+
                     wilson_notes+
                     DIV(H3('L Test for twinning')+
                         IMG(src=plot_twinning), Class="image")+clear+
                     twinning_notes
                     )
        

    report_title = (DIV(H2(kind), id="result-title"))
    base_report = (report_title + clear + summary + notes + spacer  +
                   lattice_title + lattice_table + spacer + 
                   pointless_table + notes_spacegroup + spacer +
                   #profile_report + 
                   pagebreak + dp_report)

    report = DIV(base_report, id="result-page", style="width: %dpx;" % IMG_WIDTH)
    htmldoc = HTML_TEMPLATE + str(report) + "</body></html>"
    html.write(htmldoc)
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
            out = create_full_report(report, report_directory)
            report_files.append(out)
                