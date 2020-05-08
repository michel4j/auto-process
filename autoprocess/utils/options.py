import argparse
from argparse import RawDescriptionHelpFormatter

PROCESS_EXAMPLES = """
Data sets:

    Each data set can be represented by any frame from that set.
    If multiple frames are provided but no MAD modifier options (-m, --mad) is provided, 
    each set will be processed, and at the end all the datasets will be scaled together 
    and merge into a single output reflection file.

Examples:

    auto.process --mad /path/to/dataset_{peak,infl,remo}_001.img
        process a 3-dataset MAD  

    auto.process /path/to/dataset_{hires,lores}_001.img
        process and merge low-resolution and hi-resolution datasets

    auto.process /path/to/dataset_hires_001.img /path/to/dataset_lores_001.img
        process and merge low-resolution and hi-resolution datasets. Same as above.

    auto.process --screen /foo/bar/test_001.img --dir /foo/screen_output
        Screen dataset and place the output in the given directory

"""


def process_parser():
    parser = argparse.ArgumentParser(
        description='Automatically Process a dataset',
        epilog=PROCESS_EXAMPLES,
        formatter_class=RawDescriptionHelpFormatter
    )
    parser.add_argument(
        'images', nargs='*',
        help=(
            'Data sets to process. Each data set can be represented '
            'by any frame from that set. If no datasets are provided, attempt '
            'to resume from a previous checkpoint file'
        )
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-m', '--mad', help='Process each set, scale together and generate separate outputs.',
                       action="store_true")
    group.add_argument('-s', '--screen', help='Process a few frames to characterize crystal', action="store_true")
    parser.add_argument('-a', '--anom', help="Process with Friedel's law False", action="store_true")
    parser.add_argument('-b', '--backup', help="Backup existing directory", action="store_true")
    parser.add_argument('-p', '--prefix', help="comma separated list of prefixes to use for output files", type=str)
    parser.add_argument('-d', '--dir', help="Directory to store output files. If not provided a new one is created",
                        type=str)

    parser.add_argument('-z', '--zap', help="Abandon saved state and start all over. Must be in a results directory.",
                        action="store_true")
    parser.add_argument('-l', '--load', help="Load manually processed dataset", action="store_true")
    parser.add_argument('-x', '--nonchiral', help="Non-chiral spacegroups. Default assumes only chiral molecules",
                        action="store_true")
    group.add_argument('--formula', help="Solve small molecule with provided formula. Eg Mg1O6H12", type=str)

    return parser


def analyse_parser():
    parser = argparse.ArgumentParser(description='Analyse a diffraction frame')
    parser.add_argument('image', nargs=1, help='Diffraction image to analyse')
    parser.add_argument('-r', '--raster', help="Tweak for rastering", action="store_true")
    return parser


def inputs_parser():
    parser = argparse.ArgumentParser(description='Generate XDS.INP for dataset')
    parser.add_argument('image', nargs=1, help='Representative diffraction image for dataset')
    return parser


INTEGRATE_EXAMPLES = """
Examples:

    auto.integrate -r 2.2 -f 5-180 -o
        Optimize the integration, restring to resolution 2.2, and only process
        frames 5 to 180

    auto.integrate --frames 20-120 --exclude 1-2,310-220 --anom
        Repeat the integration considering only frames 20 to 120 with Friedel's 
        law False for all remainig steps. Also skip frames 1-2 and 310-220

"""


def integrate_parser():
    parser = argparse.ArgumentParser(
        description='Resume/repeat/optimize a previous processing from the integration step',
        epilog=INTEGRATE_EXAMPLES,
        formatter_class=RawDescriptionHelpFormatter
    )
    parser.add_argument('-a', '--anom', help="Process with Friedel's law False", action="store_true")
    parser.add_argument('-b', '--backup', help="Backup existing directory", action="store_true")
    parser.add_argument('-f', '--frames', help="Data range e.g. <start>-<end>", type=str)
    parser.add_argument('-x', '--exclude', help="Exclude frame ranges e.g. <start>-<end>,<start>-<end>,...",
                        type=str)
    parser.add_argument('-d', '--dir',
                        help="Directory containing previous processing. Default is current directory.", type=str)
    parser.add_argument('-o', '--opt', help="Optimize integration using refined parameters from previous run.",
                        action="store_true")
    parser.add_argument('-r', '--res', help="Force high resolution limit", type=float)
    return parser


def powder_parser():
    parser = argparse.ArgumentParser(description='Perform azimuthal integration of powder pattern')
    parser.add_argument('files', nargs='+', help='Files to integrate or calibrate')
    parser.add_argument('-c', '--calib', help='Perform calibrationi using clear rings reference', action="store_true")
    return parser


def report_parser():
    parser = argparse.ArgumentParser(description='Regenerate reports.')
    parser.add_argument('-d', '--dir', help="Directory containing previous processing. Default is current directory.",
                        type=str)
    return parser


SCALE_EXAMPLES = """
Examples:

    auto.scale -r 2.0
        scale with high-resolution limit of 2.0 A

    auto.scale --anom
        scale with Friedel's law False

"""


def scale_parser():
    parser = argparse.ArgumentParser(
        description='Resume/repeat/optimize a previous processing from the scaling step',
        epilog=SCALE_EXAMPLES,
        formatter_class=RawDescriptionHelpFormatter
    )
    parser.add_argument('-a', '--anom', help="Process with Friedel's law False", action="store_true")
    parser.add_argument('-b', '--backup', help="Backup existing directory", action="store_true")
    parser.add_argument(
        '-d', '--dir', help="Directory containing previous processing. Default is current directory.", type=str
    )
    parser.add_argument('-r', '--res', help="Force high resolution limit", type=float)
    return parser


def strategy_parser():
    parser = argparse.ArgumentParser(description='Resume/repeat a previous screening from the strategy step')
    parser.add_argument('-a', '--anom', help="Process with Friedel's law False", action="store_true")
    parser.add_argument('-b', '--backup', help="Backup existing directory", action="store_true")
    parser.add_argument('-d', '--dir', help="Directory containing previous processing. Default is current directory.",
                        type=str)
    parser.add_argument('-r', '--res', help="Force high resolution limit", type=float)
    return parser


def symmetry_parser():
    from autoprocess.utils import xtal
    sg_info = xtal.get_sg_table(True)

    parser = argparse.ArgumentParser(
        description='Resume/repeat/optimize a previous processing from the scaling step',
        epilog=sg_info,
        formatter_class=RawDescriptionHelpFormatter
    )
    parser.add_argument('-a', '--anom', help="Process with Friedel's law False", action="store_true")
    parser.add_argument('-b', '--backup', help="Backup existing directory", action="store_true")
    parser.add_argument('-d', '--dir', help="Directory containing previous processing. Default is current directory.",
                        type=str)
    parser.add_argument('-r', '--res', help="Force high resolution limit", type=float)
    parser.add_argument('-g', '--spacegroup', help="Manually set space group by number", type=int)
    parser.add_argument('-x', '--nonchiral', help="Non-chiral spacegroups. Default assumes only chiral molecules",
                        action="store_true")
    return parser


def server_parser():
    parser = argparse.ArgumentParser("AutoProcess Server")
    parser.add_argument('-p', '--pidfile', help="Name of the pidfile [default: twistd.pid]",  type=str)
    parser.add_argument('-l', '--logfile', help="log to a specified file, - for stdout",  type=str)
    parser.add_argument('-n', '--nodaemon', help="don't daemonize",  action="store_true")
    return parser