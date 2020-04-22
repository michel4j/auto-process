import os
import subprocess
import time
import asyncio
from contextlib import closing
from progress.spinner import Spinner
import autoprocess.errors


def _execute_command(args, out_file=None):
    if out_file is None:
        std_out = open('commands.log', 'a')
    else:
        std_out = open(out_file, 'a')
    try:
        output = subprocess.check_output(args, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        raise autoprocess.errors.ProcessError(e.output.strip())

    std_out.write(output.decode('utf-8'))
    std_out.close()


class Command(object):
    def __init__(self, *args, outfile="commands.log", label="Processing", spinner=True):
        self.spinner = Spinner(f'{label} ... ')
        self.show_spinner = spinner
        self.outfile = outfile
        self.args = " ".join(args)
        self.proc = None

    async def run(self):
        with open(self.outfile, 'a') as stdout:
            proc = await asyncio.create_subprocess_shell(self.args, stdout=stdout, stderr=stdout)
            while proc.returncode is None:
                if self.show_spinner:
                    self.spinner.next()
                await asyncio.sleep(.1)
            self.spinner.write('done')
            print()

    def start(self):
        asyncio.run(self.run())


def xds(label='Processing'):
    command = Command('xds', label=label)
    command.start()


def xds_par(label='Processing'):
    command = Command('xds_par', label=label)
    command.start()


def xscale(label='Scaling'):
    command = Command('xscale', label=label)
    command.start()

def xscale_par(label='Scaling'):
    command = Command('xscale_par', label=label)
    command.start()


def xdsconv(label='Converting'):
    command = Command('xdsconv', label=label)
    command.start()


def f2mtz(filename):
    file_text = "#!/bin/csh \n"
    file_text += "f2mtz HKLOUT temp.mtz < F2MTZ.INP\n"
    file_text += "cad HKLIN1 temp.mtz HKLOUT %s <<EOF\n" % filename
    file_text += "LABIN FILE 1 ALL\n"
    file_text += "END\n"
    file_text += "EOF\n"
    file_text += "/bin/rm temp.mtz\n"
    try:
        outfile = open('f2mtz.com', 'w')
        outfile.write(file_text)
    except IOError:
        raise autoprocess.errors.ProcessError('Could not create command file')
    outfile.close()
    command = Command('sh', 'f2mtz.com', spinner=False)
    command.start()


def xdsstat(filename):
    file_text = "#!/bin/csh \n"
    file_text += "xdsstat <<EOF > XDSSTAT.LP\n"
    file_text += "%s\n" % filename
    file_text += "EOF\n"
    try:
        outfile = open('xdsstat.com', 'w')
        outfile.write(file_text)
    except IOError:
        raise autoprocess.errors.ProcessError('Could not create command file')
    outfile.close()
    command = Command('sh', 'xdsstat.com', spinner=False, label='Calculating extra statistics')
    command.start()


def pointless(retry=False, chiral=True, filename="INTEGRATE.HKL"):
    chiral_setting = {True: "", False: "chirality nonchiral"}
    f = open('pointless.com', 'w')
    txt = (
        "pointless << eof\n"
        "{}\n"
        "xdsin {}\n"
        "xmlout pointless.xml\n"
        "choose solution 1\n"
        "eof\n"
    ).format(chiral_setting[chiral], filename)
    try:
        f.write(txt)
        f.close()
    except IOError:
        raise autoprocess.errors.ProcessError('Could not create command file')
    command = Command('sh', 'pointless.com', spinner=False)
    command.start()


def best(data_info, options=None):
    options = options or {}

    if options.get('anomalous', False):
        anom_flag = '-a'
    else:
        anom_flag = ''
    if data_info.get('detector_type') is not None:
        det_flag = '-f %s' % data_info['detector_type']
    else:
        det_flag = ''

    command = "best %s -t %f -i2s 1.0 -q" % (det_flag, data_info['exposure_time'])
    command += " -e none -M 0.2 -w 0.2 %s -o best.plot -dna best.xml" % (anom_flag)
    command += " -xds CORRECT.LP BKGPIX.cbf XDS_ASCII.HKL"

    try:
        f = open('best.com', 'w')
        f.write(command)
        f.close()
    except IOError:
        raise autoprocess.errors.ProcessError('Could not create command file')

    command = Command('sh', 'best.com', outfile="best.log", spinner=False)
    command.start()


def xtriage(filename, options=None):
    options = options or {}
    command = "#!/bin/csh \n"
    command += "pointless -c xdsin %s hklout UNMERGED.mtz > unmerged.log \n" % (filename)
    command += "phenix.xtriage UNMERGED.mtz log=xtriage.log loggraphs=True\n"
    try:
        f = open('xtriage.com', 'w')
        f.write(command)
        f.close()
    except IOError:
        raise autoprocess.errors.ProcessError('Could not create command file')

    command = Command('sh', 'xtriage.com', spinner=False)
    command.start()


def distl(filename):
    command = Command('labelit.distl', outfile="distl.log", spinner=False)
    command.start()


def ccp4check(filename):
    command = "#!/bin/csh \n"
    command += "pointless -c xdsin %s hklout UNMERGED.mtz > unmerged.log \n" % (filename)
    command += "ctruncate -hklin UNMERGED.mtz -colin '/*/*/[I,SIGI]' > ctruncate.log \n"
    command += "sfcheck -f UNMERGED.mtz > sfcheck.log \n"

    try:
        f = open('ccp4check.com', 'w')
        f.write(command)
        f.close()
    except IOError:
        raise autoprocess.errors.ProcessError('Could not create command file')

    command = Command('sh', 'ccp4check.com', spinner=False)
    command.start()


def shelx_sm(name, unit_cell, formula):
    if not os.path.exists("shelx-sm"):
        os.mkdir("shelx-sm")
    os.chdir("shelx-sm")
    xprep(name, unit_cell, formula)
    command = "#!/bin/csh \n"
    command += "shelxd %s \n" % (name)
    command += "/bin/cp -f %s.res %s.ins\n" % (name, name)
    command += "shelxl %s \n" % (name,)

    try:
        f = open('shelx-sm.com', 'w')
        f.write(command)
        f.close()
    except IOError:
        raise autoprocess.errors.ProcessError('Could not create command file')

    command = Command('sh', 'shelx-sm.com', spinner=False)
    command.start()


def xprep(name, unit_cell, formula):
    import pexpect
    filename = os.path.join('..', '%s-shelx.hkl' % name)
    client = pexpect.spawn('xprep %s' % filename)
    log = ""
    commands = [
        ('Enter cell .+:\r\n\s', ' '.join(["%s" % v for v in unit_cell])),
        ('Lattice type \[.+Select option\s\[.+\]:\s', ''),
        ('Select option\s\[.+\]:\s', ''),
        ('Determination of reduced .+Select option\s\[.+\]:\s', ''),
        ('Select option\s\[.+\]:\s', ''),
        ('Select option\s\[.+\]:\s', ''),
        ('Select option\s\[.+\]:\s', ''),
        ('Select option\s\[.+\]:\s', ''),
        ('Select option\s\[.+\]:\s', ''),
        ('Select option\s\[.+\]:\s', 'C'),
        ('Enter formula; .+:\r\n\r\n', formula),
        ('Tentative Z .+Select option\s\[.+\]:\s', ''),
        ('Select option\s\[.+\]:\s', 'F'),
        ('Output file name .+:\s', name),
        ('format\s\[.+\]:\s', 'M'),
        ('Do you wish to .+\s\[.+\]:\s', ''),
        ('Select option\s\[.+\]:\s', 'Q')
    ]
    for exp, cmd in commands:
        log += client.read_nonblocking(size=2000)
        client.sendline(cmd)
        if exp is None:
            time.sleep(.1)
    if client.isalive():
        client.wait()
