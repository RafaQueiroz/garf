#!/bin/sh

echo 'Setting the root path to the garf application'
GARF_HOME='/home/rafael/tcc'

echo 'Installing Elasticsearch version 6.2.2'
sudo apt-get install elasticsearch=6.2.2

echo 'Installing Logstash version 6.2.2'
sudo apt-get install logstash=1:6.2.2-1

echo 'setting config file to logstash'
"path.config: $GARF_HOME/config/logstash.conf" >> /etc/logstash/logstash.yml

echo 'starting Logstash'
sudo service logstash start

echo 'starting Elasticsearch'
sudo service elasticsearch start

echo 'add index template to elasticsearch'
curl -XPUT 'http://localhost:9200/_template/honeyd' -H 'Content-Type: application/json' -d @$GARF_HOME/conf/log-template.json

echo 'creating garf cronjob'
source $GARF_HOME/venv/bin/activate
cd $GARF_HOME/src
python setup.py
deactivate
cd -