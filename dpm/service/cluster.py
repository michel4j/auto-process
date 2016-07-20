import Queue
import multiprocessing
import os
import random
import shlex
import socket
import subprocess
import time
import uuid
import getpass
from collections import defaultdict
from multiprocessing.managers import SyncManager

import numpy

ENVIRON_SCRIPT = os.environ.get('DPM_ENVIRONMENT', '~/.login')


class Timer(object):
    def __init__(self, name=None):
        self.name = name

    def __enter__(self):
        self.tstart = time.time()

    def __exit__(self, type, value, traceback):
        if self.name:
            print('Elapsed: %s' % (time.time() - self.tstart))


def num_chunks(N, n):
    """ Yield n approximately equal chunks from N.
    if N is not direcly divisible by n some of the chunks will have 
    to be larger
    """
    base_size, extras = divmod(N, n)
    for i in range(n):
        if i < extras:
            yield base_size + 1
        else:
            yield base_size



def get_available_cores():
    load = file("/proc/loadavg").readline().split()[0]
    return multiprocessing.cpu_count() - int(float(load))


class IntegrateServer(object):
    def __init__(self, first, total, jobs, min_batch, max_cpu, folder):
        self.first_frame = first
        self.frames = total
        self.jobs = jobs
        self.min_batch_size = min_batch
        self.max_cpu = max_cpu
        self.cur_dir = folder
        self.retries = defaultdict(int)
        self.remote_user = os.environ.get('DPM_REMOTE_USER', getpass.getuser())
        self.create_manager()
        self.command = "ssh -x %s@%%s 'cd %s ; source %s; integrateclient %s %d %s %%d'" % (
            self.remote_user, self.cur_dir, ENVIRON_SCRIPT, self.server_address,
            self.server_port, self.auth_key)
        self.local_command = "cd %s ; source %s; integrateclient %s %d %s %%d" % (
            self.cur_dir, ENVIRON_SCRIPT, self.server_address,
            self.server_port, self.auth_key)

    def get_tasks(self):
        task_list = []
        start_frame = self.first_frame

        ## Split the frames between the jobs
        for i, job_frames in enumerate(num_chunks(self.frames, self.jobs)):
            # then determine number of jobs per node and split frames per job
            job_batches = job_frames // self.min_batch_size
            _job = (start_frame, job_frames, i + 1, job_batches)
            start_frame += job_frames
            task_list.append(_job)
        return task_list

    def create_manager(self):
        # Read client setups
        self.task_list = self.get_tasks()
        self.total_cores = 0
        self.clients = {}
        hosts = os.environ['DPM_HOSTS'].split()
        random.shuffle(hosts)
        for cl_info in hosts:
            cl_parts = cl_info.split(':')
            if len(cl_parts) > 1:
                self.clients[cl_parts[0]] = int(cl_parts[1])
            else:
                self.clients[cl_parts[0]] = 2
            self.total_cores += self.clients[cl_parts[0]]

        self.auth_key = str(uuid.uuid4())
        self.server_address = socket.gethostbyname(socket.gethostname())
        job_q = Queue.Queue()
        result_q = Queue.Queue()

        class JobQueueManager(SyncManager):
            pass

        JobQueueManager.register('get_job_q', callable=lambda: job_q)
        JobQueueManager.register('get_result_q', callable=lambda: result_q)

        self.manager = JobQueueManager(address=('', 0), authkey=self.auth_key)
        self.manager.start()
        _, self.server_port = self.manager.address
        print 'Server Started at %s:%d with %s tasks to do' % (self.server_address, self.server_port, len(self.task_list))

    def run(self):
        # add tasks to queue
        self.num_tasks = len(self.task_list)
        shared_job_q = self.manager.get_job_q()
        for task in self.task_list:
            shared_job_q.put(task)

        # launch remote clients  
        active_clients = {}
        client_tasks = defaultdict(int)
        for client, ccores in self.clients.items():
            if client.lower() == 'localhost' or client.lower() == socket.gethostname().lower():
                cmd = self.local_command % (self.min_batch_size)
            else:
                cmd = self.command % (client, self.min_batch_size)
            args = shlex.split(cmd)
            p = subprocess.Popen(args, stdin=subprocess.PIPE)
            print "Starting Worker Client: '%s'" % (client)
            active_clients[client] = p

        # monitor results and exit when done.
        num_results = 0
        shared_job_q = self.manager.get_job_q()
        shared_result_q = self.manager.get_result_q()
        while num_results < len(self.task_list):
            output, client = shared_result_q.get()
            if output != '':
                print "Tasks %s failed" % output,
                if self.retries[output] > 1:
                    print "already retried %s time(s), can't proceed." % self.retries[output]
                    num_results += 1
                else:
                    print "will retry at most 2 times."
                    shared_job_q.put(output)
                    self.retries[output] += 1
            else:
                client_tasks[client] += 1
                num_results += 1
            time.sleep(1)

        # Wait for clients to complete
        _out = [p.wait() for p in active_clients.values()]
        for client_name in active_clients.values():
            print "Client '%s' completed %d task(s)" % (client_name, client_tasks[client_name])

        self.manager.shutdown()


class ColspotServer(IntegrateServer):
    def __init__(self, total, max_cpu, folder):
        self.jobs = total
        self.max_cpu = max_cpu
        self.min_batch_size = max_cpu
        self.cur_dir = folder
        self.remote_user = os.environ.get('DPM_REMOTE_USER', getpass.getuser())
        self.create_manager()
        self.command = "ssh -x %s@%%s 'cd %s ; source %s; colspotclient %s %d %s %%d'" % (
            self.remote_user, self.cur_dir, ENVIRON_SCRIPT, self.server_address,
            self.server_port, self.auth_key)
        self.local_command = "cd %s ; source %s; colspotclient %s %d %s %%d" % (
            self.cur_dir, ENVIRON_SCRIPT, self.server_address,
            self.server_port, self.auth_key)

    def get_tasks(self):
        task_list = []

        ## Setup jobs
        for i in range(self.jobs):
            _job = (i + 1,)
            task_list.append(_job)

        return task_list


class JobClient(object):
    def __init__(self, address, port, authkey, task_effort, command='mintegrate_par'):
        self.server_address = address
        self.client_name = socket.gethostname().lower()
        self.command = command
        self.authkey = authkey
        self.server_port = port
        self.task_effort = task_effort
        self.create_manager()

    def create_manager(self):
        class ServerQueueManager(SyncManager):
            pass

        ServerQueueManager.register('get_job_q')
        ServerQueueManager.register('get_result_q')

        self.manager = ServerQueueManager(address=(self.server_address, self.server_port), authkey=self.authkey)
        self.manager.connect()
        print 'Client connected to %s:%d' % (self.server_address, self.server_port)

    def worker(self, job_q, result_q):
        try:
            job = job_q.get_nowait()
            job_args = " ".join(["%s" % v for v in job])
            p = subprocess.Popen([self.command], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            p.stdin.write('%s\n' % job_args)
            out, err = p.communicate()
            p.wait()
            if p.returncode == 0:
                result_q.put('')
                print "Client '%s': task (%s) done" % (self.client_name, job_args)
            else:
                print "Client '%s': task (%s) failed! Returning task to Queue." % (self.client_name, job_args)
                result_q.put(job)
        except Queue.Empty:
            return

    def run(self):
        procs = []
        shared_job_q = self.manager.get_job_q()
        shared_result_q = self.manager.get_result_q()
        can_do_more = get_available_cores() >= self.task_effort
        while can_do_more and not shared_job_q.empty():
            p = multiprocessing.Process(
                target=self.worker,
                args=(shared_job_q, shared_result_q))
            procs.append(p)
            p.start()
            time.sleep(1) # don't be greedy, let others have a chance too!
            can_do_more = get_available_cores() >= self.task_effort

        for p in procs:
            p.join()
