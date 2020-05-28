#!/bin/bash
TESTS="tests/run_most_nbs.py"
REBUILD_CONTAINERS=false

# Parse any args...
for ARGUMENT in "$@"
do
    KEY=`echo $ARGUMENT | cut -d '=' -f 1`
    if [ "$KEY" == "--rebuild-containers" ]; then
        REBUILD_CONTAINERS=true
    fi
    if [ "$KEY" == "--test-command" ]; then
        TESTS=`echo $ARGUMENT | cut -d '=' -f 2`
    fi
done

# 
if test -f $TESTS; then
    echo "Running Tests: $TESTS - FOUND!"
else
    echo "================================================"
    echo "> POOP!   Bad Argument for --test-command 😾:"
    echo "> File $TESTS Missing  "
    exit 1
fi

# Confirm needed Requirements are present here
# TODO: may need to check version in future
COMMANDS=( 'docker-compose' 'pyvenv' 'python3' 'python' 'pip3')

for COMMAND in "${COMMANDS[@]}"
do
    echo "Checking for command $COMMAND"
    if [[ `command -v $COMMAND` ]]; then
        echo "$COMMAND Present"
    else
        echo "================================================"
        echo "> POOP!   Fix Yer Environment ⚙️  For:"
        echo "> $COMMAND Missing - Please Install!"
        exit 1
    fi
done

# Setup docker, Solr
echo "Launch Solr"
cd notebooks/solr
if "$REBUILD_CONTAINERS" = true; then
    echo "Rebuild Solr Containers, as requested"
    docker-compose down -v
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
    docker-compose down -v
    docker-compose build
else
    echo "Skip ES Container Rebuild"
fi
docker-compose up -d
cd ../..

# Are all services Running?
# If not, fail...
function test_http_service () {
    i=0
    sleep_for=5
    wait_up_to=300
    echo "Waiting for $2"
    until $(curl --output /dev/null --silent --head --fail http://localhost:$1); do     
        ((waited=i*sleep_for))
        printf "$waited,";   
        sleep $sleep_for;
        if [[ "$waited" -ge "$wait_up_to" ]]; then
            echo "ERROR - $2 did not start after $wait_up_to seconds"
            echo "TEARDOWN CONTAINERS"
            cd notebooks/elasticsearch
            docker-compose down -v
            cd ../..
            cd notebooks/solr
            docker-compose down -v
            cd ../..
            exit 1
        fi
        ((i++))
    done
    echo "$2 Started"
}
test_http_service 9200 Elastic
test_http_service 5601 Kibana
test_http_service 8983 Solr

# Rebuild venv
pyvenv tests_venv
source tests_venv/bin/activate
pip3 install -r requirements.txt

echo "================================================"
echo "== RUN TESTS: "
echo "== $TESTS "
# Tests & save result...!
python3 $TESTS
TESTS_CODE="$?"
echo "================================================"
echo "== TEARDOWN "

# Clean up venv
deactivate
rm -rf tests_venv

# Teardown Docker
cd notebooks/solr
docker-compose down -v
cd ../../notebooks/elasticsearch
docker-compose down -v

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
