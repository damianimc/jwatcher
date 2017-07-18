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
                        result['%s(%d)' % (process.name(), process.pid)] = process_dict
                        
                        for key in env_keys:
                            if copy_env_key(key) and key not in jenkins_variables:
                                jenkins_variables[key] = env_keys[key]
                        
                        break
                    
    return jenkins_variables, result


@app.route('/python_dump')
def python_process_dump():
    jenkins_variables, processes = get_processes('python')
    result = {}
    for name, info in processes.items():
        data = {}
        dump_filename = '%s_%d' % (name, info['pid'])
        data['procdump'] = subprocess.call(['procdump', '-mm', str(info['pid']), '-o', dump_filename])
        assert os.path.exists(r"C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\cdb.exe")
        try:
            data['stack_trace'] = subprocess.check_output(
                [
                    r'C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\cdb.exe', '-z', dump_filename + '.dmp', '-c', 'k;Q'
                ]
            ).decode('utf-8').split('\n')
        except subprocess.CalledProcessError as e:
            data['stack_trace'] = e.output.decode('utf-8')
        
        result[name] = data
        
    return jsonify(result)


@app.route('/python')
def python_process():
    return jsonify(get_processes('python'))


@app.route('/')
def index():
    return jsonify(get_processes(None))


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)