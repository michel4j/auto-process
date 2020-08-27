import asyncio
import os
import subprocess
import time

from progress.spinner import Spinner



class BlankSpinner(object):
    """A spinner which does nothing"""

    def __init__(self, *args, **kwargs):
        pass

    def next(self):
        pass

    def finish(self):
        pass

    def write(self, *args):
        pass


class Command(object):
    def __init__(self, *args, outfile="commands.log", label="Processing", spinner=True, final='done'):
        self.show_spinner = spinner
        self.outfile = outfile
        self.args = " ".join(args)
        self.final = final
        self.label = label
        self.proc = None
        if spinner:
            self.spinner = Spinner(f' - {self.label} ... ')
        else:
            self.spinner = BlankSpinner()

    async def run(self):
        with open(self.outfile, 'a') as stdout:
            proc = await asyncio.create_subprocess_shell(self.args, stdout=stdout, stderr=stdout)
            while proc.returncode is None:
                self.spinner.next()
                await asyncio.sleep(.1)
            self.spinner.write(self.final)
            self.spinner.finish()

    def start(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.run())


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


def xdsconv(label='Converting', final='done'):
    command = Command('xdsconv', label=label, final=final)
    command.start()


def f2mtz(filename):
    file_text = "#!/bin/csh \n"
    file_text += "f2mtz HKLOUT temp.mtz < F2MTZ.INP\n"
    file_text += "cad HKLIN1 temp.mtz HKLOUT %s <<EOF\n" % filename
    file_text += "LABIN FILE 1 ALL\n"
    file_text += "END\n"
    file_text += "EOF\n"
    file_text += "/bin/rm temp.mtz\n"
    with open('f2mtz.com', 'w') as outfile:
        outfile.write(file_text)
    subprocess.check_output(['sh', 'f2mtz.com'])


def xdsstat(filename):
    file_text = "#!/bin/csh \n"
    file_text += "xdsstat <<EOF > XDSSTAT.LP\n"
    file_text += "%s\n" % filename
    file_text += "EOF\n"
    with open('xdsstat.com', 'w') as outfile:
        outfile.write(file_text)
    command = Command('sh', 'xdsstat.com', spinner=False, label='Calculating extra statistics')
    command.start()


def pointless(retry=False, chiral=True, filename="INTEGRATE.HKL"):
    chiral_setting = {True: "", False: "chirality nonchiral"}
    txt = (
        "pointless << eof\n"
        "{}\n"
        "xdsin {}\n"
        "xmlout pointless.xml\n"
        "choose solution 1\n"
        "eof\n"
    ).format(chiral_setting[chiral], filename)
    with open('pointless.com', 'w') as fobj:
        fobj.write(txt)
    label = "Automatically determining Symmetry of {}".format(filename)
    command = Command('sh', 'pointless.com', label=label, spinner=False)
    command.start()


def best(data_info, options=None):
    options = options or {}
    option_flags = {}
    flags = {
        '-f': data_info['detector_type'],
        '-t': '{:0.2f}'.format(data_info['exposure_time']),
    }

    if options.get('anomalous'):
        option_flags['-a'] = ''
    if options.get('resolution'):
        option_flags['-r'] = '{0.1f}'.format(options['resolution'])

    option_flags.update({
        '-i2s': '1.0',
        '-q': '',
        '-e': 'none',
        '-M': 0.1,
        '-w': 0.05,
        '-o': 'best.plot',
        '-dna': 'best.xml',
        '-xds': 'CORRECT.LP BKGPIX.cbf XDS_ASCII.HKL'
    })

    flags.update(option_flags)

    command = "best {}".format(' '.join([f'{key} {value}' for key, value in flags.items()]))

    with open('best.com', 'w') as fobj:
        fobj.write(command)

    command = Command('sh', 'best.com', outfile="best.log", spinner=False)
    command.start()


def xtriage(filename, label="Checking quality of dataset", options=None):
    options = options or {}
    command = "#!/bin/csh \n"
    command += "pointless -c xdsin %s hklout UNMERGED.mtz > unmerged.log \n" % (filename)
    command += "phenix.xtriage UNMERGED.mtz log=xtriage.log loggraphs=True\n"
    with open('xtriage.com', 'w') as fobj:
        fobj.write(command)
    command = Command('sh', 'xtriage.com', outfile='xtriage.log', label=label)
    command.start()


def distl(filename):
    command = Command('labelit.distl', outfile="distl.log", spinner=False)
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

    with open('shelx-sm.com', 'w') as fobj:
        fobj.write(command)

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
