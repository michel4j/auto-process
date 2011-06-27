
import subprocess
import os
import dpm.errors


def _execute_command(args, out_file=None):
    if out_file is None:
        std_out = open('auto.log', 'a')
        std_err = std_out
    else:
        std_out = open(out_file, 'a')
        std_err = open('auto.log', 'a')
    try:    
        try:
            p = subprocess.Popen(args, shell=False, stdout=std_out, stderr=std_err)
            sts = os.waitpid(p.pid, 0)
            assert sts[1] == 0
        except OSError:
            raise dpm.errors.ProcessError('Program not found `%s`' % (args,))
        except ValueError:
            raise dpm.errors.ProcessError('Invalid arguments `%s`' % (args,))
        except AssertionError:
            #FIXME: temporary hack to avoid harmless Fortran run-time error with BEST
            if args[1] == 'best.com' and sts[1] != 512: 
                raise dpm.errors.ProcessError('Program died prematurely')
    finally:
        std_out.close()
        std_err.close()
        

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
        outfile = open('f2mtz.com','w')
        outfile.write(file_text)
    except IOError:
        raise dpm.errors.ProcessError('Could not create command file')
    outfile.close()
    _execute_command(["sh", "f2mtz.com"])

def xdsstat(filename):
    file_text = "#!/bin/csh \n"
    file_text += "xdsstat <<EOF > XDSSTAT.LP\n" 
    file_text += "%s\n" % filename 
    file_text += "EOF\n"
    try:
        outfile = open('xdsstat.com','w')
        outfile.write(file_text)
    except IOError:
        raise dpm.errors.ProcessError('Could not create command file')
    outfile.close()
    _execute_command(["sh", "xdsstat.com"])

       
def pointless(retry=False):
    f = open('pointless.com', 'w')
    if retry:
        txt = """pointless << eof
xdsin INTEGRATE.HKL
xmlout pointless.xml
resol 4.0
hklout unmerged.mtz
choose solution 1
eof
"""
    else:
        txt = """pointless << eof
xdsin INTEGRATE.HKL
xmlout pointless.xml
resol 3.0
hklout unmerged.mtz
eof
"""
     
    try:
        f.write(txt)
        f.close()
    except IOError:
        raise dpm.errors.ProcessError('Could not create command file')
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

    command  = "best %s -t %f " % (det_flag, data_info['exposure_time'])
    command += " -e none -M 0.5 -w 0.2 %s -o best.plot -dna best.xml" % (anom_flag)
    command += " -xds CORRECT.LP BKGPIX.cbf XDS_ASCII.HKL"
    
    try:
        f = open('best.com', 'w')
        f.write(command)
        f.close()
    except IOError:
        raise dpm.errors.ProcessError('Could not create command file')
    _execute_command(["sh", "best.com"], out_file="best.log")

def distl(filename):
    _execute_command(["labelit.distl", filename], out_file="distl.log")

def ctruncate(filename):
    command = "ctruncate -hklin %s -colin '/*/*/[I,SIGI]'" % (filename)
    try:
        f = open('ctruncate.com', 'w')
        f.write(command)
        f.close()
    except IOError:
        raise dpm.errors.ProcessError('Could not create command file')  
    _execute_command(["sh", "ctruncate.com"], out_file="ctruncate.log")