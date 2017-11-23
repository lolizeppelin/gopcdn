from gopcdn.cmd.db.utils import init_gopcdn

dst = {'host': '172.20.0.3',
       'port': 3304,
       'schema': 'gopcdn',
       'user': 'root',
       'passwd': '111111'}

init_gopcdn(dst)