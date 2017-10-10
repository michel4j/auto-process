import Queue
import multiprocessing
import os
import re
import random
import shlex
import socket
import subprocess
import time
import uuid
import getpass
from collections import defaultdict
from multiprocessing.managers import SyncManager
import logging

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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
    load1, load5, load15, running, queued, pid = re.split(r'[\s/]', file("/proc/loadavg").readline().strip())
    return int(multiprocessing.cpu_count() - round(float(load1)))


class IntegrateServer(object):
    def __init__(self, first, total, jobs, min_batch, max_cpu, folder):
        self.first_frame = first
        self.frames = total
        self.jobs = jobs
        self.progress = 0.0

        self.min_batch_size = min_batch
        self.max_cpu = max_cpu
        self.cur_dir = folder
        self.retries = defaultdict(int)
        self.remote_user = os.environ.get('DPM_REMOTE_USER', getpass.getuser())

        self.create_manager()
        self.logger = logging.getLogger('IntegrateServer')
        self.logger.setLevel(logging.DEBUG)
        self.log_handler = logging.FileHandler(
            os.path.join(self.cur_dir, 'integrate-{}.log'.format(self.server_address)))
        self.log_handler.setFormatter(formatter)
        self.logger.addHandler(self.log_handler)

        self.command = "ssh -x %s@%%s 'cd %s ; source %s; integrateclient %s %d %s %%d'" % (
            self.remote_user, self.cur_dir, ENVIRON_SCRIPT, self.server_address,
            self.server_port, self.auth_key)
        self.local_command = "cd %s ; source %s; integrateclient %s %d %s %%d" % (
            self.cur_dir, ENVIRON_SCRIPT, self.server_address,
            self.server_port, self.auth_key)
        self.logger.info('Server Started at %s:%d with %s tasks to do' % (
        self.server_address, self.server_port, len(self.task_list)))
        self.update_progress()

    def update_progress(self):
        with open(os.path.join(self.cur_dir, 'PROGRESS'), 'w') as pfile:
            pfile.write("{}\n".format(self.progress))

    def clear_progress(self):
        progress_file = os.path.join(self.cur_dir, 'PROGRESS')
        if os.path.exists(progress_file):
            os.remove(progress_file)

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
            self.logger.info("Starting Worker Client: '%s'" % (client))
            active_clients[client] = p

        # monitor results and exit when done.
        num_results = 0
        shared_job_q = self.manager.get_job_q()
        shared_result_q = self.manager.get_result_q()
        while num_results < len(self.task_list):
            try:
                output, client = shared_result_q.get_nowait()
                if output != '':
                    msg = "Tasks %s failed " % output
                    if self.retries[output] > 1:
                        msg += "already retried %s time(s), can't proceed." % self.retries[output]
                        num_results += 1
                    else:
                        msg += "will retry at most 2 times."
                        shared_job_q.put(output)
                        self.retries[output] += 1
                    self.logger.error(msg)
                else:
                    client_tasks[client] += 1
                    num_results += 1
                self.logger.info("{}/{} Total Results obtained. {} Tasks left in queue.".format(
                    num_results, len(self.task_list), shared_job_q.qsize()
                ))
                self.progress = float(num_results)/len(self.task_list)
                self.update_progress()
                time.sleep(.01)
            except Queue.Empty:
                self.logger.info("Waiting for results ...")
                time.sleep(5)

        # Wait for clients to complete
        _out = [p.wait() for p in active_clients.values()]
        for client_name, num_tasks in client_tasks.items():
            self.logger.info("Client '%s' completed %d task(s)" % (client_name, num_tasks))
        self.manager.shutdown()
        self.clear_progress()


class ColspotServer(IntegrateServer):
    def __init__(self, total, max_cpu, folder):
        self.jobs = total
        self.max_cpu = max_cpu
        self.min_batch_size = max_cpu
        self.cur_dir = folder
        self.progress = 0.0
        self.remote_user = os.environ.get('DPM_REMOTE_USER', getpass.getuser())
        self.create_manager()
        self.logger = logging.getLogger('ColspotServer')
        self.logger.setLevel(logging.DEBUG)
        self.log_handler = logging.FileHandler(os.path.join(self.cur_dir, 'colspot-{}.log'.format(self.server_address)))
        self.log_handler.setFormatter(formatter)
        self.logger.addHandler(self.log_handler)

        self.command = "ssh -x %s@%%s 'cd %s ; source %s; colspotclient %s %d %s %%d'" % (
            self.remote_user, self.cur_dir, ENVIRON_SCRIPT, self.server_address,
            self.server_port, self.auth_key)
        self.local_command = "cd %s ; source %s; colspotclient %s %d %s %%d" % (
            self.cur_dir, ENVIRON_SCRIPT, self.server_address,
            self.server_port, self.auth_key)
        self.logger.info('Server Started at {}:{} with {} tasks to do'.format(self.server_address, self.server_port,
                                                                              len(self.task_list)))
        self.update_progress()

    def get_tasks(self):
        task_list = []

        ## Setup jobs
        for i in range(self.jobs):
            _job = (i + 1,)
            task_list.append(_job)

        return task_list


class JobClient(object):
    def __init__(self, address, port, authkey, task_effort, max_cores=None, command='mintegrate_par'):
        self.server_address = address
        self.client_name = socket.gethostname().lower()
        self.command = command
        self.max_cores = max_cores
        self.authkey = authkey
        self.server_port = port
        self.task_effort = task_effort
        self.create_manager()
        self.logger = logging.getLogger(self.client_name)
        self.logger.setLevel(logging.DEBUG)
        self.log_handler = logging.FileHandler(
            os.path.join(os.getcwdu(), 'client-{}.log'.format(self.client_name)))
        self.log_handler.setFormatter(formatter)
        self.logger.addHandler(self.log_handler)
        self.logger.info(
            "Client {} ready.".format(self.client_name)
        )

    def create_manager(self):
        class ServerQueueManager(SyncManager):
            pass

        ServerQueueManager.register('get_job_q')
        ServerQueueManager.register('get_result_q')

        self.manager = ServerQueueManager(address=(self.server_address, self.server_port), authkey=self.authkey)
        self.manager.connect()

    def worker(self, job_q, result_q):
        while not job_q.empty():
            try:
                job = job_q.get()
                self.logger.info("Grabbed task {} from queue.".format(job))
                job_args = " ".join(["%s" % v for v in job])
                p = subprocess.Popen([self.command], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
                p.stdin.write('%s\n' % job_args)
                out, err = p.communicate()
                p.wait()
                if p.returncode == 0:
                    result_q.put(('', self.client_name))
                    self.logger.info("Task {} done".format(job))
                    job_q.task_done()
                else:
                    self.logger.error("Task {} failed! Returning task to Queue.".format(job))
                    result_q.put((job, self.client_name))
            except Queue.Empty:
                self.logger.info("No tasks in queue.")


    def run(self):
        procs = []
        shared_job_q = self.manager.get_job_q()
        shared_result_q = self.manager.get_result_q()
        available_cores = get_available_cores()
        can_do_more = True  # make sure at least one worker is created for each node
        self.logger.info(
            "Jobs in {}. Capacity {}, Load {}".format(
                os.getcwdu(),
                self.task_effort,
                available_cores
            )
        )
        while can_do_more and not shared_job_q.empty():
            p = multiprocessing.Process(
                target=self.worker,
                args=(shared_job_q, shared_result_q))
            procs.append(p)
            p.start()
            time.sleep(2)  # don't be greedy, let others have a chance too!
            available_cores = get_available_cores()
            can_do_more = available_cores >= 0.75*self.task_effort
            self.logger.info(
                "Starting Worker {}, load: {}".format(p, available_cores)
            )

        if not can_do_more:
            self.logger.info(
                "Too busy for more workers. Load: {}, Workload: {}".format(
                    available_cores, len(procs)
                )
            )
        else:
            self.logger.info(
                "No more tasks available. Load: {}, Workload: {}".format(
                    available_cores, len(procs)
                )
            )
        self.logger.info("Waiting for workers to complete ...")
        for p in procs:
            p.join()
            self.logger.info("Worker {} done !".format(p))
        self.logger.info("All workers are now done. Terminating client.")
