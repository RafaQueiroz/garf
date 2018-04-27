from flask import Flask, render_template, request, redirect
from configparser import ConfigParser
from garf import get_logs, get_rules_history
from garf import delete_rule
from elasticsearch import Elasticsearch
import os

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
    regras_ativas = get_logs(es, index='active_logs')

    context= {
        'title' : 'Regras Ativas',
        'regras' : regras_ativas
    }

    return render_template('regras-ativas.html', context=context)
    

@app.route("/historico")
def historico():

    rules = get_rules_history()
    context= {
        'title' : 'Historico',
        'rules' : rules
    }

    return render_template('historico.html', context=context)

@app.route("/remove-rule", methods=['POST'])
def remove_rule():

    if request.method == 'POST':
        rule = request.form['rule']
        app.logger.info('rule: {}'.format(rule))
        delete_rule(rule)

    return redirect('/regras-ativas', code=302)


if __name__ == "__main__":
    app.run()