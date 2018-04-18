from crontab import CronTab
from configparser import ConfigParser
import os

def main():
    config = ConfigParser()
    config.read('garf.ini')

    # definir variavel de ambiente para raiz do projeto
    if not config['app']['garf_home']:
        print('It is necessary to set the garf_home variable at the garf.ini file')

    # criar cron job para executar o garf
    script_path = '{}/script/execute_garf.sh'.format(config['app']['garf_home'])

    try:
        root_cron = CronTab(user='root')
    except OSError:
        print('ROOT privileges are needed to execute this script. Use sudo or log as root')
        return

    print('Searching for job.')
    garf_job = None
    for job in root_cron:
        if job.comment == 'garf':
            print('Job founded!')
            garf_job = job

    if not garf_job:
        print('Job not founded. Creating a new one!')
        garf_job = root_cron.new(command='python {}'.format(script_path), comment='garf')

    print('Setting job execution period')
    garf_job.minute.every(int(config['app']['execution_interval']))
    root_cron.write()


if __name__ == "__main__":
    main()