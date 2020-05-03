#!/bin/sh
TESTS="python tests/run_most_nbs.py"
# To test this script...
#$TESTS=python tests/fail.py
REBUILD_CONTAINERS=false
for ARGUMENT in "$@"
do
    echo $ARGUMENT
    if [ "$ARGUMENT" == "--rebuild_containers" ]; then
        REBUILD_CONTAINERS=true
    fi
done

# Setup docker, Solr
echo "Launch Solr"
cd notebooks/solr
if "$REBUILD_CONTAINERS" = true; then
    echo "Rebuild Solr Containers, as requested"
    docker-compose build
else
    echo "Skip Solr Container Rebuild"
fi
docker-compose up -d

# Setup docker, ES
cd ../elasticsearch
echo "Launch ES"
if "$REBUILD_CONTAINERS" = true; then
    echo "Rebuild ES Containers, as requested"
    docker-compose build
else
    echo "Skip ES Container Rebuild"
fi
docker-compose up -d
cd ../..

# Rebuild venv
pyvenv tests_venv
source tests_venv/bin/activate
pip3 install -r requirements.txt

echo "================================================"
echo "== RUN TESTS: "
echo "== $TESTS "
# Tests & save result...!
$TESTS
TESTS_CODE="$?"
echo "================================================"
echo "== TEARDOWN "

# Clean up venv
deactivate
rm -rf tests_venv

# Teardown Docker
cd notebooks/solr
docker-compose down 
cd ../../notebooks/elasticsearch
docker-compose down

echo "=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*"
if [ "$TESTS_CODE" == "0" ]
then
   echo "================================================"
   echo "> WOOHOO!  Tests Passed 👍 For:"
else
   echo "================================================"
   echo "> POOP!    Tests Failed 💩 For:" 
fi
git log -n 1
echo "================================================"
echo " ==============================================="
echo " HELLO-LTR TEST DETAILS"
echo " Containers Rebuilt? $REBUILD_CONTAINERS"
echo " Test Command: $TESTS"
echo "================================================"
