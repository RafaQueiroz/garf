#!/bin/sh

echo 'Setting the root path to the garf application'
export GARF_HOME=/home/rafael/garf

echo 'Installing Python dependencies'
apt-get install python-pip
pip install virtualenv

echo 'Checking if Elasticsearch is installed'
if [[ $(dpkg -l | grep elasticsearch 2> /dev/null) != "" ]]; then 
    echo 'Elasticsearch is already installed'
else
    echo 'Elasticsearch is not installed'
    echo 'Installing Elasticsearch version 6.2.2'
    wget https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-6.2.2.deb
    dpkg -i elasticsearch-6.2.2.deb
    rm elasticsearch-6.2.2.deb
fi

echo 'Checking if Logstash is installed'
if [[ $(dpkg -l | grep logstash 2> /dev/null) != "" ]]; then 
    echo 'Logstash is already installed'
else
    echo 'Logstash is not installed'
    echo 'Installing Logstash version 6.2.2'
    wget https://artifacts.elastic.co/downloads/logstash/logstash-6.2.2.deb
    dpkg -i logstash-6.2.2.deb
    rm logstash-6.2.2.deb
fi

echo 'setting config file to logstash'
cp $GARF_HOME/conf/logstash.conf /etc/logstash/conf.d/

if [[ $(service elasticsearch status | grep Active | grep inactive) = "" ]]; then
    echo 'Starting elasticsearch'
    service elasticsearch start
else 
    echo 'Restarting elasticsearch'
    service elasticsearch stop
    service elasticsearch start
fi

if [[ $(service logstash status | grep Active | grep inactive) = "" ]]; then
    echo 'Starting Filebeat'
    service logstash start
else 
    echo 'Restarting Filebeat'
    service logstash stop
    service logstash start
fi

echo 'add index template to elasticsearch'
curl -XPUT 'http://localhost:9200/_template/honeyd' -H 'Content-Type: application/json' -d @$GARF_HOME/conf/log-template.json
curl -XPUT 'http://localhost:9200/_template/history' -H 'Content-Type: application/json' -d @$GARF_HOME/conf/history-template.json

echo 'creating garf cronjob'

if [ ! -d "$GARF_HOME/venv" ]; then
    virtualenv -p python3 $GARF_HOME/venv
fi

source $GARF_HOME/venv/bin/activate

pip install -r $GARF_HOME/requirements.txt

cd $GARF_HOME/src

python setup.py
deactivate
