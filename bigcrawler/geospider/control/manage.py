# -*- encoding: utf-8 -*-

from geospider.control.message_analyze import Analyze
from geospider.control.message_listener import MessageListener
from geospider.control.process_controller import ProcessController
from geospider.utils.mongodb_helper import connect_mongodb, TaskDao, ProcessDao
from geospider.utils.settings_helper import get_attr

'''
    执行相应命令
    starttask:创建任务
    suspendtask：暂停任务
    resumetask：唤醒暂停的任务
    terminatetask：停止任务
'''


def execute(command, process, taskdao):
    params = Analyze(command)
    localhost = get_attr('LOCAL_HOST')
    op = params.get('op')
    taskid = params.get('taskid')
    task = taskdao.find_by_id(taskid)
    slave = task['slave']
    print(slave)
    if localhost in slave:
        print(op)
        if op == 'starttask':
            status = taskdao.find_by_id(taskid)['status']
            # status = params.get('status')
            if status == 'running':
                process.start(taskid, False)
            elif status == 'waitting':
                process.wait(taskid, False)
        elif op == 'suspendtask':
            process.suspend(taskid)
        elif op == 'resumetask':
            process.resume(taskid)
        elif op == 'terminatetask':
            process.terminate(taskid)


'''
    初始化
'''


def init():
    redis_host = get_attr('REDIS_HOST')
    sub = get_attr('SUBSCRIBE')
    localhost = get_attr('LOCAL_HOST')
    listener = MessageListener(redis_host)
    listener.subscribe(sub)
    db = connect_mongodb()
    taskdao = TaskDao(db)
    processdao = ProcessDao(db)
    process = ProcessController(localhost)
    return localhost, listener, taskdao, processdao, process


'''
    监听信息做出相应响应
'''


def run(process, listener, taskdao):
    process.scan()
    while (True):
        msg = listener.listen()
        execute(msg, process, taskdao)


'''
    入口，开始任务管理
    异常处理：查询出故障的主机的进程，获得该主机正在执行的任务id，删除该主机的进程数据，重新创建该主机的任务进程，run
'''


def start():
    localhost, listener, taskdao, processdao, process = init()
    try:
        run(process, listener, taskdao)
    except:
        print('---------------------------异常------------------------')
        process_list = processdao.find_by_localhost(localhost)
        command_list = []
        for p in process_list:
            if p['taskid'] == '':
                processdao.delete_by_localhost_and_taskid(localhost, '')
                continue
            if p['taskid'] == 'pausing':
                temp_task = taskdao.find_by_id(p['taskid'])
                temp_task['status'] = 'running'
                taskdao.save(temp_task)
            command_list.append('op=starttask&taskid=' + p['taskid'])
            processdao.delete_by_localhost_and_taskid(localhost, p['taskid'])
        for command in command_list:
            params = Analyze(command)
            op = params.get('op')
            taskid = params.get('taskid')
            if op == 'starttask':
                status = taskdao.find_by_id(taskid)['status']
                if status == 'running':
                    process.start(taskid, True)
                elif status == 'waitting':
                    process.wait(taskid, True)
        start()


if __name__ == '__main__':
    start()
