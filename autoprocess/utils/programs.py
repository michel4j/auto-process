import os
import subprocess
import time

import autoprocess.errors

if "check_output" not in dir(subprocess):  # duck punch it in!
    def f(*popenargs, **kwargs):
        r"""Run command with arguments and return its output as a byte string.

        Backported from Python 2.7 as it's implemented as pure python on stdlib.

        >>> check_output(['/usr/bin/python', '--version'])
        Python 2.6.2
        """
        process = subprocess.Popen(stdout=subprocess.PIPE, *popenargs, **kwargs)
        output, unused_err = process.communicate()
        retcode = process.poll()
        if retcode:
            cmd = kwargs.get("args")
            if cmd is None:
                cmd = popenargs[0]
            error = subprocess.CalledProcessError(retcode, cmd)
            error.output = output
            raise error
        return output


    subprocess.check_output = f


def _execute_command(args, out_file=None):
    if out_file is None:
        std_out = open('commands.log', 'a')
    else:
        std_out = open(out_file, 'a')
    try:
        output = subprocess.check_output(args, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        raise autoprocess.errors.ProcessError(e.output.strip())

    std_out.write(output)
    std_out.close()


def xds():
    _execute_command('xds')


def xds_par():
    _execute_command('xds_par')


def xscale():
    _execute_command('xscale')


def xscale_par():
    _execute_command('xscale_par')


def xdsconv():
    _execute_command('xdsconv')


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
    _execute_command(["sh", "f2mtz.com"])


def xdsstat(filename):
    file_text = "#!/bin/csh \n"
    file_text += "xdsstat 100 3 <<EOF > XDSSTAT.LP\n"
    file_text += "%s\n" % filename
    file_text += "EOF\n"
    try:
        outfile = open('xdsstat.com', 'w')
        outfile.write(file_text)
    except IOError:
        raise autoprocess.errors.ProcessError('Could not create command file')
    outfile.close()
    try:
        _execute_command(["sh", "xdsstat.com"])
    except:
        pass


def pointless(retry=False, chiral=True, filename="INTEGRATE.HKL"):
    chiral_setting = {True: "", False: "chirality nonchiral"}
    f = open('pointless.com', 'w')
    txt = """pointless << eof
%s
xdsin %s
xmlout pointless.xml
choose solution 1
eof
""" % (chiral_setting[chiral], filename)
    try:
        f.write(txt)
        f.close()
    except IOError:
        raise autoprocess.errors.ProcessError('Could not create command file')
    _execute_command(["sh", "pointless.com"], out_file="pointless.log")


def best(data_info, options={}):
    anom_flag = ''
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
    _execute_command(["sh", "best.com"], out_file="best.log")


def xtriage(filename, options={}):
    command = "#!/bin/csh \n"
    command += "pointless -c xdsin %s hklout UNMERGED.mtz > unmerged.log \n" % (filename)
    command += "phenix.xtriage UNMERGED.mtz log=xtriage.log loggraphs=True\n"
    try:
        f = open('xtriage.com', 'w')
        f.write(command)
        f.close()
    except IOError:
        raise autoprocess.errors.ProcessError('Could not create command file')
    _execute_command(["sh", "xtriage.com"])


def distl(filename):
    _execute_command(["labelit.distl", filename], out_file="distl.log")


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
    _execute_command(["sh", "ccp4check.com"])


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
    _execute_command(["sh", "shelx-sm.com"])


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
