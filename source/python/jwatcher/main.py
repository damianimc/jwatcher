#!flask/bin/python
from flask import Flask, jsonify
from datetime import datetime
import subprocess
import os.path


ENVIRON_KEYWORD = 'JENKINS_'

def copy_env_key(key):
    return key.startswith('BUILD_') or \
        key.startswith('JOB_') or \
        key.startswith('NODE_') or \
        key.startswith(ENVIRON_KEYWORD)

app = Flask(__name__)

def get_processes(process_name):
    import psutil

    jenkins_variables = {}
    result = {}
    configuration_mismatch_processes = []
    for process in psutil.process_iter():
        try:
            env_keys = process.environ()
        except psutil.AccessDenied:
            pass
        else:
            for key in env_keys:
                if key.startswith(ENVIRON_KEYWORD):
                    if process_name is None or process_name in process.name():
                        process_dict = process.as_dict(attrs=['pid', 'username', 'cpu_times', 'cmdline', 'create_time', 'cwd', 'status', 'io_counters', 'memory_info'])
                        process_dict['create_time'] = datetime.fromtimestamp(process_dict['create_time'])
                        process_dict['io_counters'] = str(process_dict['io_counters'])
                        process_dict['cpu_times'] = str(process_dict['cpu_times'])
                        process_dict['memory_info'] = str(process_dict['memory_info'])
                        
                        proc_environ = {}
                        for key in env_keys:
                            if copy_env_key(key):
                                if key not in jenkins_variables:
                                    jenkins_variables[key] = env_keys[key]
                                elif jenkins_variables[key] != env_keys[key]:
                                    configuration_mismatch_processes.append('%s(%d)' % (process.name(), process.pid))
                                if key not in proc_environ:
                                    proc_environ[key] = env_keys[key]
                        
                        process_dict['proc_environ'] = proc_environ
                        result['%s(%d)' % (process.name(), process.pid)] = process_dict
                        break
                    
    return { 'process with different environ' : configuration_mismatch_processes }, \
           { 'process environ' : jenkins_variables }, \
           result


@app.route('/python_dump')
def python_process_dump():
    _, jenkins_variables, processes = get_processes('python')
    result = {}
    dump_files = []
    for name, info in processes.items():
        data = {}
        if 'WORKSPACE' in info:
            dump_filename = os.path.join(info['WORKSPACE'], name)
        else:
            dump_filename = name
        data['procdump'] = subprocess.call(['procdump', '-mm', str(info['pid']), '-o', dump_filename])
        result[name] = data
        
        dump_filename += '.dmp'
        if os.path.exists(dump_filename):
            data['dump_filename'] = dump_filename
            dump_files.append((name, dump_filename))
        else:
            data['dump_filename'] = None

    for name, dump_filename in dump_files:
        print('Generating DUMP:', name, dump_filename)
        data = result[name]
        assert os.path.exists(r"C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\cdb.exe")
        try:
            data['stack_trace'] = subprocess.check_output(
                [
                    r'C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\cdb.exe', '-z', dump_filename, '-c', 'k;Q'
                ]
            ).decode('utf-8').split('\n')
        except subprocess.CalledProcessError as e:
            data['stack_trace'] = e.output.decode('utf-8')
        
    return jsonify(result)


@app.route('/python')
def python_process():
    return jsonify(get_processes('python'))


@app.route('/')
def index():
    return jsonify(get_processes(None))


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)