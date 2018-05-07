from flask import Flask, render_template, request, redirect, jsonify
from configparser import ConfigParser
from garf import get_history, get_input_rules, delete_rule, get_graph_data
from elasticsearch import Elasticsearch
from datetime import datetime
import os
import json


app = Flask(__name__)
es = Elasticsearch(verify_certs=True)

@app.route("/")
def index():
    context= {
        'title' : 'Home'
    }

    return render_template('index.html', context=context)

@app.route("/configuracoes", methods=['GET', 'POST'])
def configuracoes():
    print('entrou')
    config = ConfigParser()
    config.read('/home/rafael/garf/src/garf.ini')
    if request.method == 'POST':

        config.set('app', 'execution_interval', request.form['execution_interval'])
        config.set('app', 'rule_dureation', request.form['rule_dureation'])
        config.set('app', 'max_occurrence', request.form['max_occurrence'])
        print('Chegou antes do checkbox')

        config.set('app', 'only_ip', 'True' if request.form.get('only_ip') else 'False')

        with open('/home/rafael/garf/src/garf.ini', 'w') as configfile:
            config.write(configfile)

        os.system('python3 setup.py')
            
    context= {
        'title' : 'Configuracoes',
        'config' : {
            'execution_interval' : config['app']['execution_interval'],
            'rule_dureation' : config['app']['rule_dureation'],
            'max_occurrence' : config['app']['max_occurrence'],
            'only_ip' : config['app']['only_ip']
        }
    }

    return render_template('configuracoes.html', context=context)


@app.route("/regras-ativas")
def regras_ativas():
    regras_ativas = get_input_rules()

    context= {
        'title' : 'Regras Ativas',
        'regras' : regras_ativas
    }

    return render_template('regras-ativas.html', context=context)
    

@app.route("/historico", methods=['POST', 'GET'])
def historico():

    rules = []
    if request.method == 'POST':
        data_inicio = request.form['inicio']+' 00:00'
        data_fim = request.form['fim']+' 23:59'

        inicio = datetime.strptime(data_inicio, '%d/%m/%Y %H:%M')
        fim = datetime.strptime(data_fim, '%d/%m/%Y %H:%M')
        rules = get_history(es, inicio, fim)

        return jsonify(rules)
   
    context= {
        'title' : 'Historico'
    }

    return render_template('historico.html', context=context)


@app.route("/grafico", methods=['POST'])
def graph():
    rules = {}
    if request.method == 'POST':
        inicio = datetime.strptime(request.form['inicio'], '%d/%m/%Y')
        fim = datetime.strptime(request.form['fim'], '%d/%m/%Y')
        
        grouped_rules = get_graph_data(es, inicio, fim)

        for rule in grouped_rules:
            rules[rule['created_in_key']] = rule['doc_count']
            
    print(rules)
    return jsonify(rules)


@app.route("/remove-rule", methods=['POST'])
def remove_rule():

    raw_rule = request.form['rule']
    rule = json.loads(raw_rule)
    delete_rule(rule)

    return jsonify('Regra removida com sucesso') 


if __name__ == "__main__":
    app.run()