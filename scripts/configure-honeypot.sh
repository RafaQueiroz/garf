#!/bin/sh
GARF_HOME='/home/rafael/garf'

if [[ $(dpkg -l | grep filebeat 2> /dev/null) != "" ]]; then
    echo 'Filebeat is already installed'
else
    echo 'Filebeat not founded'
    echo 'Installing Filebeat'
    wget https://artifacts.elastic.co/downloads/beats/filebeat/filebeat-6.2.2-amd64.deb
    dpkg -i filebeat-6.2.2-amd64.deb
    rm filebeat-6.2.2-amd64.deb
fi

cp %GARF_HOME/conf/filebeat.yml /etc/filebeat/

if [[ $(service filebeat status | grep Active | grep inactive 2> /dev/null) = "" ]]; then
    echo 'Starting Filebeat'
    service filebeat start
else 
    echo 'Restarting Filebeat'
    service filebeat stop
    service filebeat start
fi