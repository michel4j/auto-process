#!/usr/bin/env python

# enables  multi-tasking by splitting the INTEGRATE step of
# xds into independent jobs. Each job is carried out by the
# Fortran program mintegrate or mintegrate_par started by
# this script as a background process with a different set
# of input parameters.

import sys
import os
import random
import numpy
import subprocess
import shlex
import time


HOST_NAMES = os.environ['DPM_HOSTS'].split()

def num_chunks(N, n):
    """ Yield n approximately equal chunks from l.
    if l is not direcly divisible by n some of the chunks will have 
    will be larger
    """
    base_size, extras = divmod(N,n) 
    for i in range(n):
        if i < extras:
            yield base_size+1
        else:
            yield base_size


def main():
    # Get parameters
    jobs = int(sys.argv[1])
    max_cpu = int(sys.argv[2])
    cur_dir = os.getcwd()
    # Print parameters
    print " INITIALIZING JOBS: %3s %3s" % tuple(sys.argv[1:])
    # Prepare jobs
    NODES = len(HOST_NAMES)
    task_list = []
    active_jobs = []     
    host_list = HOST_NAMES
    random.shuffle(host_list)
    
    ## Setup jobs
    for i in range(jobs):   
        _job = {
            'hostname': host_list[i%len(host_list)],
            'args': i + 1}
        task_list.append(_job)
        
    # submit jobs
    for job in task_list:
        cmd = "ssh -x %s 'cd %s ; source ~/.login; mcolspot_par'" % (job['hostname'], cur_dir)
        args = shlex.split(cmd)
        p = subprocess.Popen(args, stdin=subprocess.PIPE)
        job_args = "%3d " % job['args']
        p.job_params = (job['hostname'], job_args)
        print " STARTING JOB: %s [%s]" % p.job_params
        p.stdin.write('%s\n' % job_args)           
        active_jobs.append(p)

    # check periodically if all jobs are finished
    try:
        while len(active_jobs) > 0:
            time.sleep(0.5)
            for p in active_jobs:
                p.poll()
                if p.returncode is None: continue
                
                if p.returncode != 0:
                    print " JOB FAILED: %s [%s]" % p.job_params
                    active_jobs.remove(p)
                else:
                    print " JOB FINISHED: %s [%s]" % p.job_params
                    active_jobs.remove(p)
    except:
        for p in active_jobs:
            if p.returncode is not None:
                p.terminate()
    os.remove('mcolspot.tmp')
    
if __name__ == '__main__':
    if len(sys.argv) != 6:
        print 'usage: \n\tforkcolspot ntask maxcpu'
    else:
        main()
