import sys
from autoprocess.engine.process import DataSet
from autoprocess.utils import log, xdsio

logger = log.get_module_logger('auto.process')


def main(args):
    dataset = DataSet(filename=args.image)
    logger.info('Creating XDS.INP ...')
    xdsio.write_xds_input('ALL !XYCORR INIT COLSPOT IDXREF DEFPIX INTEGRATE CORRECT', dataset.parameters)


def run(args):
    try:
        log.log_to_console()
        main(args)
    except KeyboardInterrupt:
        sys.exit(1)
