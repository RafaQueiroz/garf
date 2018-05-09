#!/home/rafael/garf/venv/bin/python

import logging
import os
from crontab import CronTab
import iptc

from elasticsearch import Elasticsearch, NotFoundError
from configparser import ConfigParser
from datetime import datetime, timedelta


## Handling Iptables
def insert_rules(logs=[]):                                   
    chain = iptc.Chain(iptc.Table(iptc.Table.FILTER), 'INPUT') 
    rules = []

    if not logs:
        logging.info('Nenhuma regra para ser adicionada')
        return rules

    for log in logs:
        input_rule = find_rule(log)
        if input_rule:
            logging.info('Ja Existe uma regra ativa: {}'.format(log))
            continue

        rule = format_rule(log)
        chain.insert_rule(rule)                
        rules.append(rule_to_dict(rule))
        
    return rules


def format_rule(log):

    if not log:
        return iptc.Rule()

    rule_duration = int(config['app']['rule_dureation'])
    expires_in = datetime.now() + timedelta(seconds=rule_duration)

    rule = iptc.Rule()                                     
    rule.src = log['source_ip']

    if 'protocol' in log.keys():
        rule.protocol = log['protocol']
        
        if 'destination_port' in log.keys():                
            protocol_match = iptc.Match(rule, log['protocol'])   
            protocol_match.dport = log['destination_port']
            rule.add_match(protocol_match)                      
        
    comment_match = iptc.Match(rule, 'comment')            
    comment_match.comment= datetime.strftime(expires_in, '%Y-%m-%d %H:%M')
    rule.add_match(comment_match) 
    target = iptc.Target(rule, 'DROP')
    rule.target = target

    return rule

def get_input_rules():
    filter_chain = iptc.Chain(iptc.Table(iptc.Table.FILTER), 'INPUT')
    filter_rules = []
    for rule in filter_chain.rules:
        filter_rules.append(rule_to_dict(rule))
                             
    return filter_rules 

def rule_to_dict(rule):

    if not rule:
        return {}

    dport = ''
    raw_date = ''
    protocol = rule.protocol if rule.protocol else ''                     
    for match in rule.matches:
        if rule.protocol and match.name == rule.protocol:
            dport = match.dport
        elif match.name == 'comment':
            raw_date = match.comment  

    date = datetime.strptime(raw_date, '%Y-%m-%d %H:%M')

    rule = {
        'source_ip' : rule.src,
        'destination_port' : dport,
        'protocol' : protocol,
        'expires_in' : date.strftime('%d/%m/%Y %H:%M')
    }

    return rule
 
def find_rule(log):
    rules = get_input_rules()

    if not log:
        return None

    for rule in rules:
        if log['source_ip'] in rule['source_ip'] :
            if config['app']['only_ip'] == 'True':
                return rule
            elif log['destination_port'] == rule['destination_port'] and\
                log['protocol'] == rule['protocol']:
                return rule
        
    return None

def delete_rule(log):

    filter_chain = iptc.Chain(iptc.Table(iptc.Table.FILTER), "INPUT")

    for r in filter_chain.rules:
        rule = rule_to_dict(r)
        if log['source_ip'] in rule['source_ip']:
            if log['source_ip'] in rule['source_ip'] :
                filter_chain.delete_rule(r)
                return True
            elif log['destination_port'] == rule['destination_port'] and\
             log['protocol'] == rule['protocol']:
                try:
                    filter_chain.delete_rule(rule)
                    return True
                except iptc.ip4tc.IPTCError:
                    logging.error('Nao foi possivel remover a regra: {}'.format(rule_to_dict(rule)))
            
    return False

def add_to_history(elastic, rules=[]):
    if not rules:
        logging.info("nenhum log a ser inserido")
        return

    for rule in rules:
        document = {
            'created_in' : datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
            'created_in_key' : datetime.now().strftime('%Y-%m-%d'),
            'source_ip': rule['source_ip'],
            'destination_port': rule['destination_port'],
            'protocol': rule['protocol']
        }
        elastic.index(index='history', doc_type='doc', body=document)


def remove_expire_rules():
    filter_chain = iptc.Chain(iptc.Table(iptc.Table.FILTER), "INPUT")

    counter = 0
    
    while True:
        rule = get_expired_rule(filter_chain)

        if not rule:
            break
            
        try:
            filter_chain.delete_rule(rule)
            counter += 1
        except iptc.ip4tc.IPTCError:
            logging.error('Nao foi possivel remover a regra: {}'.format(rule_to_dict(rule)))

    logging.info('{} regra(s) foram removidas'.format(str(counter)))

def get_expired_rule(filter):
    
    for rule in filter.rules:
        expires_in = None
        for match in rule.matches:
            if match.name == 'comment':
                expires_in = datetime.strptime(match.comment, '%Y-%m-%d %H:%M')

        if expires_in < datetime.now():
            return rule

    return None

def get_logs(elastic, index='', body='', fields=['_id', 'source_ip', 'destination_port', 'protocol', 'access_date', 'expires_in', 'created_in']):
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


def group_by(elastic, idx, fields, include_missing, body={}):
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
    
    response = elastic.search(index=idx, body=body)
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

def format_dict(raw_log={}, fields=[]):

    log = {}

    for field in fields:
        if field in raw_log.keys():
            log[field] = raw_log[field]

    if 'created_in' in log.keys():
        date = datetime.strptime(log['created_in'], '%Y-%m-%dT%H:%M:%S')
        log['created_in'] = date.strftime('%d/%m/%Y %H:%M')

    return log


def get_by_date_body(inicio, fim):
    body={
        'query': {
            'range': {
                'created_in': {
                    'gte': inicio,
                    'lte': fim
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


def get_history(elastic, inicio, fim):
    if not elastic.indices.exists(index='history'):
        return []

    return get_logs(elastic, index='history', body=get_by_date_body(inicio, fim))

def get_graph_data(elastic, begin, end):
    logs = group_by(elastic, 'history', ['created_in_key'], False,
                    body=get_by_date_body(begin, end))
    
    return logs

def get_top_ips(elastic, begin, end):
    logs = group_by(elastic, 'history', ['source_ip'], False,
                    body=get_by_date_body(begin, end))
    
    return logs

def get_top_ports(elastic, begin, end):
    logs = group_by(elastic, 'history', ['destination_port'], False,
                    body=get_by_date_body(begin, end))
    
    return logs

def main():
    elastic = Elasticsearch(verify_certs=True)
    logging.info('----COMEÇANDO A EXECUTAR')
    logging.info('REMOVENDO REGRAS EXPIRADAS') 
    remove_expire_rules()

    logging.info('BUSCANDO E AGRUPANDO LOGS') 

    if config['app']['only_ip'] == 'True':
        group_list = ['source_ip']
    else:
        group_list = ['source_ip', 'destination_port', 'protocol']


    logs = group_by(elastic, 'honeyd', group_list, False,
                    body=get_group_by_body(datetime.now()))

    logging.info('FILTRANDO LOGS PARA GERAR AS REGRAS') 
    filtered_logs = []
    if logs :
        logging.info('filtrando {} logs'.format(str(len(logs))))
        filtered_logs = [log for log in logs if log['doc_count'] > int(config['app']['max_occurrence'])]

    logging.info('INSERINDO {} NOVA(S) REGRA(S)'.format(str(len(filtered_logs))))
    rules = insert_rules(filtered_logs)

    logging.info('ADICIONANDO {} NOVA(S) REGRA(S) PARA O HISTORICO'.format(str(len(rules))))
    add_to_history(elastic, rules)


if __name__ == "__main__":
    
    config = ConfigParser()
    config.read('/home/rafael/garf/src/garf.ini')
        
    if not os.path.isdir(config['app']['log']):
        os.mkdir(config['app']['log'])

    logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p',
                        filename='{}/garf-{:%Y-%m-%d}.log'.format(config['app']['log'],
                                                                      datetime.now()), level=logging.INFO)
    main()
