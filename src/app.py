from flask import Flask, render_template, request, redirect, jsonify
from configparser import ConfigParser
from garf import get_history, get_input_rules, delete_rule
from elasticsearch import Elasticsearch
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

    config = ConfigParser()
    config.read('garf.ini')
    if request.method == 'POST':

        config.set('app', 'execution_interval', request.form['execution_interval'])
        config.set('app', 'rule_dureation', request.form['rule_dureation'])
        config.set('app', 'max_occurrence', request.form['max_occurrence'])

        with open('garf.ini', 'wb') as configfile:
            config.write(configfile)

        os.system('python3 setup.py')
            
    context= {
        'title' : 'Configuracoes',
        'config' : {
            'execution_interval' : config['app']['execution_interval'],
            'rule_dureation' : config['app']['rule_dureation'],
            'max_occurrence' : config['app']['max_occurrence']
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
        data_inicio = request.form['inicio']
        data_fim = request.form['fim']
        rules = get_history(es, data_inicio, data_fim)

        return jsonify(rules)
   
    context= {
        'title' : 'Historico'
    }

    return render_template('historico.html', context=context)

@app.route("/remove-rule", methods=['POST'])
def remove_rule():

    raw_rule = request.form['rule']
    rule = json.loads(raw_rule)
    delete_rule(rule)

    return jsonify('Regra removida com sucesso') 


if __name__ == "__main__":
    app.run()