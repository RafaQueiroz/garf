#!/bin/sh

echo 'Setting the root path to the garf application'
echo GARF_HOME=/home/rafael/garf > /home/rafael/.bashrc
source /home/rafael/.bashrc

echo 'Installing Python dependencies'
sudo apt-get install python-pip
sudo pip install virtualenv

echo 'Installing Elasticsearch version 6.2.2'
sudo apt-get install elasticsearch=6.2.2

echo 'Installing Logstash version 6.2.2'
sudo apt-get install logstash=1:6.2.2-1

echo 'setting config file to logstash'
cp $GARF_HOME/conf/logstash.conf /etc/logstash/conf.d/

echo 'starting Logstash'
sudo service logstash start

echo 'starting Elasticsearch'
sudo service elasticsearch start

echo 'add index template to elasticsearch'
curl -XPUT 'http://localhost:9200/_template/honeyd' -H 'Content-Type: application/json' -d @$GARF_HOME/conf/log-template.json

echo 'creating garf cronjob'
virtualenv -p python3 $GARF_HOME/venv
source $GARF_HOME/venv/bin/activate
pip install -r $GARF_HOME/conf/requirements.txt
cd $GARF_HOME/src
python setup.py
deactivate
