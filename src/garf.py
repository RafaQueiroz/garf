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
        document = {
            'expires_in': datetime.now() + timedelta(seconds=rule_duration),
            'source_ip': log['source_ip'],
            'destination_port': log['destination_port'],
            'protocol': log['protocol']
        }
        elastic.index(index='active_logs', doc_type='doc', body=document)


def remove_expire_logs(elastic, logs=[]):
    if not logs:
        return

    for log in logs:
        print('{}\n'.format(log))
        elastic.delete(index='active_logs', id=log['_id'])


def analyse_logs(elastic):

    #Cria o arquivo para remover as regras espiradas do iptables
    expire_logs = get_logs(elastic, index='active_logs', body=get_expired_logs_query_body(datetime.now()))
    export_rules_file(expire_logs, False)

    remove_expire_logs(elastic, expire_logs)

    #Cria o arquivo contento as regras novas do iptables
    logs = group_by(elastic, ['source_ip', 'destination_port', 'protocol'], False,
                    body=get_group_by_body(datetime.now()))

    filtered_logs = []
    if logs :
        filtered_logs = [log for log in logs if log['doc_count'] > int(config['app']['max_occurrence'])]

    export_rules_file(filtered_logs)

    #Salva as regras novas
    save_active_logs(elastic, filtered_logs)

    return True


def get_logs(elastic, index='', body=''):
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
        print('{}\n'.format(raw_log))
        log = format_dict(raw_log, fields=['_id', 'source_ip', 'destination_port', 'protocol', 'access_date'])
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
    return 'iptables -{action} INPUT -p {protocol} --dport {port} -s {ip} -j DROP'\
         .format(action=action, protocol=log['protocol'], port=log['destination_port'], ip=log['source_ip'])


def export_rules_file(logs=[], add=True):

    file_path = '{}/scripts/{}'.format(config['app']['garf_home'], ('custom_rules.sh' if add else 'drop_old_rules.sh'))

    if os.path.isfile(file_path) and add:
        logging.info('Founded old rules file. Adding it to the history')
        add_to_history(file_path)

    logging.info("Opening or creating file to deploy the rules")
    rules_file = open(file_path, 'w+')
    rules_file.write('#!/bin/bash \n')

    logging.info("Writing rules on the file")
    try:
        for log in logs:
            rules_file.write(create_comand(log, add))
            rules_file.write("\n    ")
    except Exception:
        logging.error("There was an error during the process of writing in the rules file")
    finally:
        logging.info("Closing files")
        rules_file.close()


def add_to_history(source_file_path=''):
    current_file = open(source_file_path, 'r')

    if not os.path.isdir(config['app']['log']):
        os.mkdir(config['app']['log'])

    rules_history = open('{}/rules_history-{:%Y-%m-%d}.log'.format(config['app']['log'], datetime.now()), 'a')

    rules_history.write('# logging date: {:%Y-%m-%d %H:%M} \n'.format(datetime.now()))

    for line in current_file:
        rules_history.write('# {}'.format(line))

    rules_history.write('\n\n\n')


def format_dict(raw_log={}, fields=[]):

    log = {}

    for field in fields:
        if field in raw_log.keys():
            log[field] = raw_log[field]

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


config = ConfigParser()
config.read('garf.ini')


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
