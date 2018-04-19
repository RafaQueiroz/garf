#!/bin/sh"
GARF_HOME='/home/rafael/garf'
source $GARF_HOME/venv/bin/activate
cd $GARF_HOME/src/
python garf.py
deactivate
