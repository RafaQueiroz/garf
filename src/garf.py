from elasticsearch import Elasticsearch, NotFoundError
import logging
import os
from configparser import ConfigParser
from datetime import datetime, timedelta


def save_active_logs(elastic, logs=[]):

    if not logs:
        logging.info("nenhum log a ser inserido")
        return

    rule_duration = int(config['app']['rule_dureation'])

    for log in logs:

        log_list = get_logs(elastic, index='active_logs', body=check_if_exists(log))

        if log_list:
            logging.info('Regra ja salva')
            continue

        document = {
            'expires_in': datetime.now() + timedelta(seconds=rule_duration),
            'source_ip': log['source_ip'],
            'destination_port': log['destination_port'],
            'protocol': log['protocol']
        }
        elastic.index(index='active_logs', doc_type='doc', body=document)


def remove_expire_logs(elastic, logs=[]):
    if not logs:
        logging.info('Any logs to be removed')
        return

    logging.info('Removing {} logs'.format(str(len(logs))))
    for log in logs:
        elastic.delete(index='active_logs', doc_type='doc', id=log['_id'])


def analyse_logs(elastic):

    #Cria o arquivo para remover as regras espiradas do iptables
    logging.info('### RETRIEVING OLD RULES')
    expire_logs = get_logs(elastic, index='active_logs', body=get_expired_logs_query_body(datetime.now()))
    export_rules_file(expire_logs, False)

    logging.info('### REMOVING OLD RULES')
    remove_expire_logs(elastic, expire_logs)

    logging.info('### FETCHING DATA TO NEW RULES')
    #Cria o arquivo contento as regras novas do iptables
    logs = group_by(elastic, ['source_ip', 'destination_port', 'protocol'], False,
                    body=get_group_by_body(datetime.now()))

    filtered_logs = []
    if logs :
        logging.info('Raw data: {}'.format(str(len(logs))))
        filtered_logs = [log for log in logs if log['doc_count'] > int(config['app']['max_occurrence'])]

    logging.info('### EXPORTING NEW RULES FILE')
    export_rules_file(filtered_logs)

    #Salva as regras novas
    logging.info('### SAVING ACTIVE RULES INTO THE DATABASE')
    save_active_logs(elastic, filtered_logs)

    return True


def get_logs(elastic, index='', body='', fields=['_id', 'source_ip', 'destination_port', 'protocol', 'access_date', 'expires_in']):
    # Fetch data from elasticsearch

    logs = []

    try:
        result = elastic.search(index=index, ignore=[400, 404], body=body)
    except NotFoundError :
        return logs

    if not result:
        logging.info("Nothing was returned from elasticsearch")
        return logs

    logging.info("processing retrived documents")

    if 'error' in result:
        logging.error('Erro ao executar a query. Motivo: {}'.format(result['error']['type']))
        return logs

    for data in result['hits']['hits']:
        raw_log = data['_source']
        raw_log['_id'] = data['_id']

        log = format_dict(raw_log, fields=fields)
        logs.append(log)

    logging.info("{} documents processed!".format(len(logs)))
    return logs


def group_by(elastic, fields, include_missing, body={}):
    current_level_terms = {'terms': {'field': fields[0]}}
    agg_spec = {fields[0]: current_level_terms}

    if include_missing:
        current_level_missing = {'missing': {'field': fields[0]}}
        agg_spec[fields[0] + '_missing'] = current_level_missing

    for index, field in enumerate(fields[1:]):
        next_level_terms = {'terms': {'field': field}}

        current_level_terms['aggs'] = {
            field: next_level_terms,
        }

        if include_missing:
            next_level_missing = {'missing': {'field': field}}
            current_level_terms['aggs'][field + '_missing'] = next_level_missing
            current_level_missing['aggs'] = {
                field: next_level_terms,
                field + '_missing': next_level_missing,
            }
            current_level_missing = next_level_missing

        current_level_terms = next_level_terms

    body['aggs'] = agg_spec

    response = elastic.search(body=body)
    agg_result = response['aggregations'] if response else []
    return get_docs_from_agg_result(agg_result, fields, include_missing)


def get_docs_from_agg_result(agg_result, fields, include_missing):
    current_field = fields[0]
    buckets = agg_result[current_field]['buckets']
    if include_missing:
        buckets.append(agg_result[(current_field + '_missing')])

    if len(fields) == 1:
        return [
            {
                current_field: bucket.get('key'),
                'doc_count': bucket['doc_count'],
            }
            for bucket in buckets if bucket['doc_count'] > 0
        ]

    result = []
    for bucket in buckets:
        records = get_docs_from_agg_result(bucket, fields[1:], include_missing)
        value = bucket.get('key')
        for record in records:
            record[current_field] = value
        result.extend(records)

    return result


def create_comand(log, add=True):

    action = 'A' if add else 'D'
    rule = 'iptables -{action} INPUT -p {protocol} --dport {port} -s {ip} -j DROP'\
         .format(action=action, protocol=log['protocol'], port=log['destination_port'], ip=log['source_ip'])

    check_rule = '-A INPUT -s {ip}/32 -p {protocol} -m {protocol} --dport {port} -j DROP'\
         .format(action=action, protocol=log['protocol'], port=log['destination_port'], ip=log['source_ip'])

    if add:     
        command='if [[ $(iptables-save | grep -- "{check_rule}" 2> /dev/null) = "" ]]; then\n {rule} \nfi\n'.format(check_rule=check_rule, rule=rule)
    else:
        command='if [[ $(iptables-save | grep -- "{check_rule}" 2> /dev/null) != "" ]]; then\n {rule} \nfi\n'.format(check_rule=check_rule, rule=rule)
    return command


def export_rules_file(logs=[], add=True):

    file_path = '{}/scripts/{}'.format(config['app']['garf_home'], ('custom_rules.sh' if add else 'drop_old_rules.sh'))

    logging.info('Exporting files to {}'.format(file_path))
    if os.path.isfile(file_path) and add:
        add_to_history(file_path)
        logging.info('Founded old rules file. Adding it to the history')

    logging.info("Opening or creating file to deploy the rules")
    rules_file = open(file_path, 'w+')
    rules_file.write('#!/bin/bash \n')

    logging.info("Writing rules on the file")
    try:
        for log in logs:
            rules_file.write(create_comand(log, add))
    except Exception:
        logging.error("There was an error during the process of writing in the rules file")
    finally:
        logging.info("Closing files")
        rules_file.close()


def add_to_history(source_file_path=''):
    current_file = open(source_file_path, 'r')

    if not os.path.isdir(config['app']['log']):
        os.mkdir(config['app']['log'])
    
    file_path = '{}/rules_history-{:%Y-%m-%d}.log'.format(config['app']['log'], datetime.now())
    logging.info('saving rules into the history: {}'.format(file_path))
    rules_history = open(file_path, 'a+')

    for line in current_file:
        rules_history.write(' {}'.format(line))

def format_dict(raw_log={}, fields=[]):

    log = {}

    for field in fields:
        if field in raw_log.keys():
            log[field] = raw_log[field]

    if 'expires_in' in log.keys():
        date = datetime.strptime(log['expires_in'], '%Y-%m-%dT%H:%M:%S.%f')
        log['expires_in'] = date.strftime('%d/%m/%Y %H:%M')

    return log


def get_expired_logs_query_body(date):
    body={
        'query': {
            'range': {
                'expires_in': {
                    'lt': date.isoformat()
                }
            }
        }
    }
    return body


def get_group_by_body(date):

    start_date = date - timedelta(minutes=int(config['app']['execution_interval']))
    body = {
        'query': {
            'range': {
                'access_date': {
                    'lt': date.isoformat(),
                    'gt': start_date.isoformat()
                }
            }
        }
    }
    return body


def check_if_exists(log):
    body = {
        "query": {
            "constant_score" : {
                "filter" : {
                    "bool" : {
                        "must" : [
                            { "term" : { "source_ip" : log['source_ip'] } }, 
                            { "term" : { "protocol" : log['protocol'] } },
                            { "term" : { "destination_port" : log['destination_port'] } }
                        ]
                    }
                }
            }
        }
    }

    return body


def get_rules_history():
    rules = []

    if not os.path.isdir(config['app']['log']):
        return rules

    currentDate = datetime.now()
    file_path = '{}/rules_history-{:%Y-%m-%d}.log'.format(config['app']['log'], currentDate)
    try:
        rules_file = open(file_path, 'r')
    except IOError:
        print('File not found')
        return rules

    for line in rules_file:
        if not line or '#!/bin/bash' in line:
            continue
        rules.append(line)

    return rules

config = ConfigParser()
config.read('garf.ini')

def delete_rule(rule):

    if not rule:
        logging.info('An Empty rule was informed')
        return
    
    logging.info('removing {} manually'.format(rule))
    rule = rule.replace('-A', '-D')

    os.system('{}'.format(rule))


def main():
    es = Elasticsearch(verify_certs=True)

    if not es.ping():
        logging.info("Nenhuma estancia do Elasticsearch est ativa")
        return

    analyse_logs(es)

    logging.info('Removendo regras expiradas')
    os.system('bash {}/scripts/drop_old_rules.sh'.format(config['app']['garf_home']))

    logging.info('Adicionando novas regras')
    os.system('bash {}/scripts/custom_rules.sh'.format(config['app']['garf_home']))


if __name__ == "__main__":

    if not os.path.isdir(config['app']['log']):
        os.mkdir(config['app']['log'])

    logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p',
                        filename='{}/garf-{:%Y-%m-%d}.log'.format(config['app']['log'],
                                                                      datetime.now()), level=logging.INFO)
    main()
