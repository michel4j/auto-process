import re
import string
import sys
import os
try: 
    import json
except:
    import simplejson as json
    
import cStringIO

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
            w("<%s" %self.tag)
            # attributes which will produce arg = "val"
            attr1 = [ k for k in self.attrs 
                if not isinstance(self.attrs[k],bool) ]
            w("".join([' %s="%s"' 
                %(k.replace('_','-'),self.attrs[k]) for k in attr1]))
            # attributes with no argument
            # if value is False, don't generate anything
            attr2 = [ k for k in self.attrs if self.attrs[k] is True ]
            w("".join([' %s' %k for k in attr2]))
            w(">")
        if self.tag in ONE_LINE:
            w('\n')
        w(str(self.inner_HTML))
        for child in self.children:
            w(str(child))
        if self.tag in CLOSING_TAGS:
            w("</%s>" %self.tag)
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

NON_CLOSING_TAGS = ['AREA', 'BASE', 'BASEFONT', 'BR', 'COL', 'FRAME',
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
    'TABLE','TR','TD','TH','SELECT','OPTION',
    'FORM',
    'H1', 'H2', 'H3', 'H4', 'H5', 'H6',
    ]
# tags whose opening tag should be alone in its line
ONE_LINE = ['HTML','HEAD','BODY',
    'FRAMESET'
    'SCRIPT',
    'TABLE','TR','TD','TH','SELECT','OPTION',
    'FORM',
    ]

if __name__ == '__main__':
    head = HEAD(TITLE('Test document'))
    body = BODY()
    body <= H1('This is a test document')
    body <= 'First line' + BR() + 'Second line'
    #print HTML(head + body)

def plot_shell_stats(results, directory):
    from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
    from matplotlib.ticker import FormatStrFormatter, MultipleLocator, MaxNLocator
    from matplotlib.figure import Figure
    from matplotlib import rcParams
    
    # Adjust Legend parameters
    rcParams['legend.loc'] = 'best'
    rcParams['legend.fontsize'] = 10
    rcParams['legend.isaxes'] = False
    rcParams['figure.facecolor'] = 'white'
    rcParams['figure.edgecolor'] = 'white'
    
    #try:
    #    project = request.user.get_profile()
    #    result = project.result_set.get(pk=id)
    #except:
    #    raise Http404
    # extract shell statistics to plot
    data = results['details']['shell_statistics']
    fig = Figure(figsize=(7.5,6.5), dpi=72)
    ax1 = fig.add_subplot(211)
    ax1.plot(data['shell'], data['completeness'], 'r-+')
    ax1.set_ylabel('completeness (%)', color='r')
    ax11 = ax1.twinx()
    ax11.plot(data['shell'], data['r_meas'], 'g-', label='R-meas')
    ax11.plot(data['shell'], data['r_mrgdf'], 'g:+', label='R-mrgd-F')
    ax11.legend(loc='best')
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
    ax2.plot(data['shell'], data['i_sigma'], 'm-x')
    ax2.set_xlabel('Resolution Shell')
    ax2.set_ylabel('I/SigmaI', color='m')
    ax21 = ax2.twinx()
    ax21.plot(data['shell'], data['sig_ano'], 'b-+')
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

    canvas = FigureCanvas(fig)
    #response = HttpResponse(content_type='image/png')
    #canvas.print_png(response)
    filename = directory + '/report/plot_shell.png'
    canvas.print_png(filename)
    return filename
    
def plot_diff_stats(results, directory):
    from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
    from matplotlib.ticker import FormatStrFormatter, MultipleLocator, MaxNLocator
    from matplotlib.figure import Figure
    from matplotlib import rcParams
    
    # Adjust Legend parameters
    rcParams['legend.loc'] = 'best'
    rcParams['legend.fontsize'] = 10
    rcParams['legend.isaxes'] = False
    rcParams['figure.facecolor'] = 'white'
    rcParams['figure.edgecolor'] = 'white'
    
    #try:
    #    project = request.user.get_profile()
    #    result = project.result_set.get(pk=id)
    #except:
    #    raise Http404
    # extract shell statistics to plot
    data = results['details']['diff_statistics']
    fig = Figure(figsize=(7.5,6.5), dpi=72)
    ax1 = fig.add_subplot(311)
    ax1.plot(data['frame_diff'], data['rd'], 'r-')
    ax1.set_ylabel('R-d', color='r')
    ax11 = ax1.twinx()
    ax11.plot(data['frame_diff'], data['n_refl'], 'g-')
    ax1.grid(True)
    ax11.set_ylabel('# Reflections', color='g')
    for tl in ax11.get_yticklabels():
        tl.set_color('g')
    for tl in ax1.get_yticklabels():
        tl.set_color('r')
    ax1.yaxis.set_major_formatter(FormatStrFormatter('%0.2f'))
    ax11.yaxis.set_major_formatter(FormatStrFormatter('%0.0f'))
    #ax1.set_ylim((0, 105))
    #ax11.set_ylim((0, max(data['n_refl'])+5))

    ax2 = fig.add_subplot(312, sharex=ax1)
    ax2.plot(data['frame_diff'], data['rd_friedel'], 'm-')
    ax2.set_ylabel('R-d Friedel', color='m')
    ax21 = ax2.twinx()
    ax21.plot(data['frame_diff'], data['n_friedel'], 'b-')
    ax2.grid(True)
    ax21.set_ylabel('# Reflections', color='b')
    for tl in ax21.get_yticklabels():
        tl.set_color('b')
    for tl in ax2.get_yticklabels():
        tl.set_color('m')
    ax2.yaxis.set_major_formatter(FormatStrFormatter('%0.2f'))
    ax21.yaxis.set_major_formatter(FormatStrFormatter('%0.0f'))

    ax3 = fig.add_subplot(313, sharex=ax1)
    ax3.plot(data['frame_diff'], data['rd_non_friedel'], 'k-')
    ax3.set_xlabel('Frame Difference')
    ax3.set_ylabel('R-d Non-friedel', color='k')
    ax31 = ax3.twinx()
    ax31.plot(data['frame_diff'], data['n_non_friedel'], 'c-')
    ax3.grid(True)
    ax31.set_ylabel('# Reflections', color='c')
    for tl in ax31.get_yticklabels():
        tl.set_color('c')
    for tl in ax3.get_yticklabels():
        tl.set_color('k')
    ax3.yaxis.set_major_formatter(FormatStrFormatter('%0.2f'))
    ax31.yaxis.set_major_formatter(FormatStrFormatter('%0.0f'))

    canvas = FigureCanvas(fig)
    #response = HttpResponse(content_type='image/png')
    #canvas.print_png(response)
    filename = directory + '/report/plot_diff.png'
    canvas.print_png(filename)
    return filename

def plot_frame_stats(results, directory):
    from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
    from matplotlib.ticker import FormatStrFormatter, MultipleLocator, MaxNLocator
    from matplotlib.figure import Figure
    from matplotlib import rcParams
    
    # Adjust Legend parameters
    rcParams['legend.loc'] = 'best'
    rcParams['legend.fontsize'] = 10
    rcParams['legend.isaxes'] = False
    
    #try:
    #    project = request.user.get_profile()
    #    result = project.result_set.get(pk=id)
    #except:
    #    raise Http404
    # extract shell statistics to plot
    data = results['details']['frame_statistics']
    fig = Figure(figsize=(5.6,5), dpi=72)
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
    ax21 = ax2.twinx()
    ax21.plot(data['frame'], data['i_sigma'], 'b-')
    ax2.grid(True)
    ax21.set_ylabel('I/Sigma(I)', color='b')
    for tl in ax21.get_yticklabels():
        tl.set_color('b')
    for tl in ax2.get_yticklabels():
        tl.set_color('m')
    ax2.yaxis.set_major_formatter(FormatStrFormatter('%0.3f'))
    ax21.yaxis.set_major_formatter(FormatStrFormatter('%0.1f'))
    ax2.set_ylim((min(data['divergence'])-0.02, max(data['divergence'])+0.02))

    ax3 = fig.add_subplot(313, sharex=ax1)
    ax3.plot(data['frame'], data['r_meas'], 'k-')
    ax3.set_xlabel('Frame Number')
    ax3.set_ylabel('R-meas', color='k')
    ax31 = ax3.twinx()
    ax31.plot(data['frame'], data['unique'], 'c-')
    ax3.grid(True)
    ax31.set_ylabel('Unique Reflections', color='c')
    for tl in ax31.get_yticklabels():
        tl.set_color('c')
    for tl in ax3.get_yticklabels():
        tl.set_color('k')
    ax3.yaxis.set_major_formatter(FormatStrFormatter('%0.3f'))
    ax31.yaxis.set_major_formatter(FormatStrFormatter('%0.0f'))

    canvas = FigureCanvas(fig)
    #response = HttpResponse(content_type='image/png')
    #canvas.print_png(response)
    filename = directory + '/report/plot_frame.png'
    canvas.print_png(filename)
    return filename


def report_style(css):
    css.write('body { font-size: 83%; margin: 2px; border: 1px solid #ccc;}')
    css.write('#result-page { margin-top: 1em; text-align:left; padding:1.5em 1.5em 1em;}')
    css.write('#result-table { font-size: 88%; border-collapse:collapse; text-align:left; width: 100%;}')
    css.write('#result-table th { color:#003399; font-size: 1.2em; font-weight:normal; padding:8px 8px;}')
    css.write('#result-table td { border-top:1px solid #eee; color:#666699; padding:5px 8px;}')
    css.write('#strategy-table { font-size: 88%; border-collapse:collapse; text-align:left; width: 45%;}')
    css.write('#strategy-table td { border-top:1px solid #eee; color:#666699; padding:5px 8px;}')
    css.write('.result-labels { -moz-background-clip:border; -moz-background-inline-policy:continuous; -moz-background-origin:padding; background:#EFF6FF none repeat scroll 0 0; border-left:10px solid transparent; border-right:10px solid transparent;}')
    css.write('#result-table tr:hover td { -moz-background-clip:border; -moz-background-inline-policy:continuous; -moz-background-origin:padding; background:#EFF6FF none repeat scroll 0 0; color:#333399;}')
    css.write('#strategy-table tr:hover td { -moz-background-clip:border; -moz-background-inline-policy:continuous; -moz-background-origin:padding; background:#EFF6FF none repeat scroll 0 0; color:#333399;}')
    css.write('#result-summary { border-collapse:collapse; border:1px solid #c3d9ff; float: left; width: 45%; margin-right:2%; text-align:left;}')
    css.write('.size30 { width: 30%;}') 
    css.write('.size40 { width: 40%;}') 
    css.write('.size60 { width: 60%;}') 
    css.write('.size45 { width: 45%;}')         
    css.write('.tablenotes { font-size: 90%; background:#EFF6FF none repeat scroll 0 0; padding:0.3em 2em 1em; margin-bottom: 10px;}')
    css.write('dl.note-list dt { float: left; clear: left; text-align: right; font-weight: bold; color: #666;}')
    css.write('dl.note-list dd { margin: 0 0 0 2em; padding: 0 0 0.5em 0;}')
    css.write('h1, h2, h3, h4 { font-weight:normal; margin-top:1.4em;}')
    css.write('#result-title h2{ font-size:190%; line-height:1.2em; margin-bottom:0.8em; margin-top: 1em; border-bottom: 1px dashed #666666; color: #666666;}')
    css.write('div.spacer { padding: 0.3em 0;}')
    css.write('.clear {clear: both !important;}')
    css.write('#result-page h3 { font-size: 140%; border-bottom: 1px dotted #ccc;}')
    css.write('.rtable { border-collapse:collapse; text-align:left; border: solid 1px #ccc;}')
    css.write('.rtable th { color:#003399; font-weight:normal; padding:8px 8px; text-align: right;}')
    css.write('.rtable td { text-align: right; font-family: Monaco, Consolas, monospace; border-top:1px solid #eee; color:#666699; padding:5px 8px;}')
    css.write('.half { width: 49%;}')
    css.write('.full { width: 100% !important;}')
    css.write('.floatleft { float: left;}')
    css.write('.floatright { float: right;}')
    css.write('img.image  { display: block; margin-left: auto; margin-right: auto;}')

    return css

class Results(object):
    directory = sys.argv[1]
    if os.path.exists(directory):
        json_data=open(directory + '/process.json').read()
        if not os.path.exists(directory + '/report'):
            os.mkdir(directory + '/report')
        html=open(directory + '/report/index.html', 'w')
        css =open(directory + '/report/report.css', 'w')    

    data = json.loads(json_data)
    try:
        results = data[data.keys()[0]]['results']
    except KeyError:
        base = data[data.keys()[0]]
        results = base[base.keys()[0]]['results']

    clear = (DIV('', Class="clear"))    
    spacer = (DIV('', Class="clear spacer"))

    result_table_head = (COLGROUP(COL('', Class='result-labels'))+
                         THEAD(TR(TH("Dataset", scope="col")+(TH('"'+results['name']+'"')))))
    result_table_body = (TBODY(TR(TD('Score'+(SUP('[1]', Class="footnote")))+TD("%0.2f" % results['score']))+
                               TR(TD('Wavelength (A)')+TD(results['wavelength']))+    
                               TR(TD('Space Group'+(SUP('[2]', Class="footnote")))+TD(results['space_group']))+  
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
    result_table = (TABLE(result_table_head+result_table_body, id="result-table"))                    

    summary = H3('Summary')+DIV(result_table, id="result-summary")

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
    lattice_table = TABLE(lattice_table_head+lattice_table_body, Class="rtable full")

    notes = (DIV(H3('Notes')+DL(DT('[1] - ')+DD('Data Quality Score for comparing similar data sets. Typically, values > 0.8 are excellent, > 0.6 are good, > 0.5 are acceptable, > 0.4 marginal, and &lt; 0.4 are Barely usable')+
                                DT('[2] - ')+DD('This space group was automatically assigned using POINTLESS (see P.R.Evans, Acta Cryst. D62, 72-82, 2005). This procedure is unreliable for incomplete datasets such as those used for screening. Please Inspect the detailed results below.')+
                                DT('[3] - ')+DD('Resolution selected based on a cut-off of I/sigma(I) > 1.0. Statistics presented reflect this resolution.')+
                                DT('[4] - ')+DD('Redundancy independent R-factor. (see Diederichs & Karplus, 1997, Nature Struct. Biol. 4, 269-275.)')+
                                DT('[5] - ')+DD('Quality of amplitudes. (see Diederichs & Karplus, 1997, Nature Struct. Biol. 4, 269-275.)'), Class="note-list"), Class="tablenotes floatright size40"))   
   
    notes_spacegroup = (DIV(H3('Notes')+
                            P('The above table contains result from POINTLESS (see Evans, Acta Cryst. D62, 72-82, 2005).')+
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
    pointless_table = H3('Automatic Space-Group Selection')+TABLE(pointless_table_head+pointless_table_body, Class="rtable full") 

    shell_title = H3('Integration and Scaling Statistics (by shell)')
    shell_table_head = THEAD(TR(TH('Shell', scope="col")+
                              TH('Complete', scope="col")+
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
    shell_table = TABLE(shell_table_head + shell_table_body, Class="rtable full")

    shell_notes = (DIV(H3('Notes')+DL(DT('[1] - ')+DD('Mean of intensity/Sigma(I) of unique reflections (after merging symmetry-related observations). Where Sigma(I) is the standard deviation of reflection intensity I estimated from sample statistics.')+
                                      DT('[2] - ')+DD('mean anomalous difference in units of its estimated standard deviation (|F(+)-F(-)|/Sigma). F(+), F(-) are structure factor estimates obtained from the merged intensity observations in each parity class.'), Class="note-list"), Class="tablenotes"))   
   
    frame_notes = (DIV(H3('Notes')+DL(DT('Divergence - ')+DD('Estimated Standard Deviation of Beam divergence')+
                                      DT('R'+SUB('d')+' - ')+DD('R-factors as a function of frame difference. See Diederichs K. (2006) Acta Cryst D62, 96-101.'), Class="note-list"), Class="tablenotes"))   

    strategy_notes = (DIV(H3('Notes')+DL(DT('[a] - ')+DD('Recommended exposure time does not take into account overloads at low resolution!')+
                                         DT('[b] - ')+DD('Values in parenthesis represent the high resolution shell.')+
                                         DT('[c] - ')+DD('Resolution limit is set by the initial image resolution.'), Class="note-list"), Class="tablenotes floatright size40"))   

    plot_shell = plot_shell_stats(results, directory)
    shell_img = IMG(src='plot_shell.png', Class="image")
    if results['kind'] == 0:
        kind = "Crystal Screening Report"
        strategy_title = H3('Data Collection Strategy')+P('Recommended Strategy for Native Data Collection')
        if 'strategy' in results:
            strategy_data = results['strategy']
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
                                        TR(TD('R-factor (%) [b]')+TD(strategy_data['exp_r_factor'])))) 
            strategy = strategy_title + TABLE(strategy_table_body, id="strategy-table", Class="floatleft") + strategy_notes
    elif results['kind'] == 1:
        kind = "Data Processing Report"
        plot_frame = plot_frame_stats(results, directory)
        plot_diff = plot_diff_stats(results, directory)
        dp_report = (H3('Integration and Scaling Statistics (by frame/frame difference)')+
                     IMG(src='plot_frame.png', Class="image")+
                     IMG(src='plot_diff.png', Class="image")+clear+
                     frame_notes)

    report_title = (DIV(H2(kind), id="result-title"))
    style = report_style(css)
    
    report_head = HEAD(LINK(rel="stylesheet", href='report.css', type="text/css"))
    base_report = (report_title + clear + summary + notes + spacer + 
                   lattice_title + lattice_table + spacer +  
                   pointless_table + notes_spacegroup + spacer + 
                   shell_title + shell_img + shell_table + shell_notes + spacer)

    if results['kind'] == 0:
        report = report_head + DIV(base_report+strategy+spacer, id="result-page")
    elif results['kind'] == 1:
        report = report_head + DIV(base_report+dp_report, id="result-page")
          
    html.write(str(report))