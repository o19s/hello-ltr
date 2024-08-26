#!/bin/bash
TESTS="tests/run_most_nbs.py"
REBUILD_CONTAINERS=false
DOCKER_COMPOSE_CMD="docker compose"

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

    if [ "$KEY" == "--engines" ]; then
        ENGINE_ARG=$(echo "$ARGUMENT" | cut -d '=' -f 2)
    fi

done

echo $ENGINE_ARG
if [ -z "${ENGINE_ARG}" ]; then
  ENGINE_ARG="solr,elasticsearch,opensearch"
  echo $ENGINE_ARG
fi
ENGINES=$(awk -F',' '{ for( i=1; i<=NF; i++ ) print $i }' <<< "$ENGINE_ARG")

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
COMMANDS=( 'docker' 'python3' 'pip3')

for COMMAND in "${COMMANDS[@]}"
do
    echo "Checking for command $COMMAND"
    if [[ `command -v $COMMAND` ]]; then
        echo "$COMMAND Present"
        
        if [[ "$COMMAND" == "docker" ]]; then
            DOCKER_VERSION=$(docker version --format '{{.Client.Version}}' | cut -d '.' -f1-2)
            MINIMUM_VERSION="20.10"
            if [[ $(echo -e "$DOCKER_VERSION\n$MINIMUM_VERSION" | sort -V | head -n1) == "$MINIMUM_VERSION" ]]; then
                echo "Docker version $DOCKER_VERSION supports 'docker compose'."
            else
                echo "Docker version $DOCKER_VERSION does not support 'docker compose'. Checking for 'docker-compose'."
                if [[ `command -v docker-compose` ]]; then
                    echo "docker-compose Present"
                    DOCKER_COMPOSE_CMD="docker-compose"
                else
                    echo "================================================"
                    echo "> POOP!   Fix Yer Environment ⚙️  For:"
                    echo "> docker-compose Missing - Please Install!"
                    exit 1
                fi
            fi
        fi

    else
        echo "================================================"
        echo "> POOP!   Fix Yer Environment ⚙️  For:"
        echo "> $COMMAND Missing - Please Install!"
        exit 1
    fi
done

function launch_containers() {

  engine="$1"
  rebuild="$2"
  echo "Launch $engine"
  cd notebooks/$engine
  if "$rebuild" = true; then
      echo "Rebuild $engine Containers, as requested"
      $DOCKER_COMPOSE_CMD down -v
      $DOCKER_COMPOSE_CMD build
  else
      echo "Skip $engine Container Rebuild"
  fi
  $DOCKER_COMPOSE_CMD up -d
  cd ../..
}

function down_containers() {

  engine="$1"
  rebuild="$2"
  echo "Launch $engine"

  cd notebooks/$engine
  if "$rebuild" = true; then
      echo "Rebuild $engine Containers, as requested"
      $DOCKER_COMPOSE_CMD down -v
      $DOCKER_COMPOSE_CMD build
  else
      echo "Skip $engine Container Rebuild"
  fi
  $DOCKER_COMPOSE_CMD up -d
  cd ../..
}

for ENGINE in ${ENGINES}
do
  launch_containers "${ENGINE}" ${REBUILD_CONTAINERS}
done



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
            for ENGINE in $ENGINES
              do
                cd notebooks/$ENGINE
                $DOCKER_COMPOSE_CMD down -v
                cd ../..
              done
            exit 1
        fi
        ((i++))
    done
    echo "$2 Started"
}

test_http_service 9201 OpenSearch
test_http_service 5602 OSD
test_http_service 9200 Elastic
test_http_service 5601 Kibana
test_http_service 8983 Solr

# Rebuild venv
python3 -m venv tests_venv
source tests_venv/bin/activate
python -m pip install -U pip wheel setuptools
pip install -r requirements.txt

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
