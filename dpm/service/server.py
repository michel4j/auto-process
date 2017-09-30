import json
import os
import pwd
import subprocess
import zerorpc


def demote(user_name):
    """Pass the function 'set_user' to preexec_fn, rather than just calling
    setuid and setgid. This will change the ids for that subprocess only"""

    def set_user():
        pwdb = pwd.getpwnam(user_name)
        os.setgid(pwdb.pw_gid)
        os.setuid(pwdb.pw_uid)

    return set_user


def get_user(user_name):
    try:
        pwdb = pwd.getpwnam(user_name)
        uid = pwdb.pw_uid
        gid = pwdb.pw_gid
    except:
        raise ValueError('Invalid User "{}"'.format(user_name))
    return uid, gid


class AutoProcessRPC(object):
    def screen(self, info, directory, user_name):
        args = [
            'auto.process',
            '--screen',
            '--dir={}'.format(directory)
        ]
        args += ['--anom'] if info.get('anomalous') else []
        args += info['file_names']
        subprocess.check_call(args, preexec_fn=demote(user_name))

        with open('process.json', 'r') as handle:
            result = json.load(handle)
        return result

    def analyse(self, frame_path, user_name):
        args = [
            'auto.analyse',
            frame_path,
        ]
        out = subprocess.check_output(args, preexec_fn=demote(user_name))
        result = json.loads(out)
        return result

    def process(self, info, directory, user_name):
        args = [
            'auto.process',
            '--screen',
            '--dir={}'.format(directory)
        ]
        args += ['--anom'] if info.get('anomalous') else []
        args += ['--mad'] if info.get('mad') else []
        args += info['file_names']
        subprocess.check_call(args, preexec_fn=demote(user_name))

        with open('process.json', 'r') as handle:
            result = json.load(handle)
        return result


if __name__ == '__main__':
    s = zerorpc.Server(AutoProcessRPC())
    s.bind('tcp://0.0.0.0:8881')
    s.run()