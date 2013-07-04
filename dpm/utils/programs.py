
import subprocess
import dpm.errors

def _execute_command(args, out_file=None):
    if out_file is None:
        std_out = open('commands.log', 'a')
    else:
        std_out = open(out_file, 'a')
    try:    
        output = subprocess.check_output(args, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError, e:
        raise dpm.errors.ProcessError(e.output.strip())
    
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
        outfile = open('f2mtz.com','w')
        outfile.write(file_text)
    except IOError:
        raise dpm.errors.ProcessError('Could not create command file')
    outfile.close()
    _execute_command(["sh", "f2mtz.com"])

def xdsstat(filename):
    file_text = "#!/bin/csh \n"
    file_text += "xdsstat 100 3 <<EOF > XDSSTAT.LP\n" 
    file_text += "%s\n" % filename 
    file_text += "EOF\n"
    try:
        outfile = open('xdsstat.com','w')
        outfile.write(file_text)
    except IOError:
        raise dpm.errors.ProcessError('Could not create command file')
    outfile.close()
    try:
        _execute_command(["sh", "xdsstat.com"])
    except:
        pass

       
def pointless(retry=False, filename="INTEGRATE.HKL"):
    f = open('pointless.com', 'w')
    txt = """pointless << eof
xdsin %s
xmlout pointless.xml
choose solution 1
eof
"""  % filename
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

    command  = "best %s -t %f -i2s 1.0 -q" % (det_flag, data_info['exposure_time'])
    command += " -e none -M 0.2 -w 0.2 %s -o best.plot -dna best.xml" % (anom_flag)
    command += " -xds CORRECT.LP BKGPIX.cbf XDS_ASCII.HKL"
    
    try:
        f = open('best.com', 'w')
        f.write(command)
        f.close()
    except IOError:
        raise dpm.errors.ProcessError('Could not create command file')
    _execute_command(["sh", "best.com"], out_file="best.log")

def xtriage(filename, options={}):
    command  = "#!/bin/csh \n"
    command += "pointless -c xdsin %s hklout UNMERGED.mtz > unmerged.log \n" % (filename)
    command += "phenix.xtriage UNMERGED.mtz log=xtriage.log \n"
    try:
        f = open('xtriage.com', 'w')
        f.write(command)
        f.close()
    except IOError:
        raise dpm.errors.ProcessError('Could not create command file')  
    _execute_command(["sh", "xtriage.com"])
    

def distl(filename):
    _execute_command(["labelit.distl", filename], out_file="distl.log")

def ccp4check(filename):
    command  = "#!/bin/csh \n"
    command += "pointless -c xdsin %s hklout UNMERGED.mtz > unmerged.log \n" % (filename)
    command += "ctruncate -hklin UNMERGED.mtz -colin '/*/*/[I,SIGI]' > ctruncate.log \n"
    command += "sfcheck -f UNMERGED.mtz > sfcheck.log \n"
    
    try:
        f = open('ccp4check.com', 'w')
        f.write(command)
        f.close()
    except IOError:
        raise dpm.errors.ProcessError('Could not create command file')  
    _execute_command(["sh", "ccp4check.com"])


