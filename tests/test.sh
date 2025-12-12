#!/bin/bash
#
# Integration test runner for hello-ltr
#
# Usage:
#   ./tests/test.sh [OPTIONS]
#
# Options:
#   --rebuild-containers      Rebuild Docker containers before testing
#   --engines=ENGINE_LIST     Comma-separated list of engines to test (solr,elasticsearch,opensearch)
#   --test-command=COMMAND    Custom test command to run (default: tests/run_most_nbs.py)
#   --non-interactive         Skip all prompts and auto-cleanup conflicts (useful for CI)
#
# Environment Variables:
#   AUTO_CLEANUP_CONFLICTS    Set to 'true' to auto-cleanup without prompting
#   SOLR_PORT                 Custom Solr test port (default: 18983)
#   ELASTICSEARCH_PORT        Custom Elasticsearch test port (default: 19200)
#   OPENSEARCH_PORT           Custom OpenSearch test port (default: 19201)
#
# Examples:
#   ./tests/test.sh                                    # Run all tests interactively
#   ./tests/test.sh --non-interactive                  # Run in CI mode (no prompts)
#   ./tests/test.sh --engines=solr                     # Test only Solr
#   ./tests/test.sh --rebuild-containers               # Rebuild before testing
#

TESTS="tests/run_most_nbs.py"
REBUILD_CONTAINERS=false
DOCKER_COMPOSE_CMD="docker compose"
NON_INTERACTIVE=false

# Set test ports to avoid conflicts with standard installations
export SOLR_PORT="${SOLR_PORT:-18983}"
export ELASTICSEARCH_PORT="${ELASTICSEARCH_PORT:-19200}"
export KIBANA_PORT="${KIBANA_PORT:-15601}"
export OPENSEARCH_PORT="${OPENSEARCH_PORT:-19201}"
export OPENSEARCH_PA_PORT="${OPENSEARCH_PA_PORT:-19600}"
export OPENSEARCH_DASHBOARDS_PORT="${OPENSEARCH_DASHBOARDS_PORT:-15602}"

# Option to auto-cleanup conflicting containers (useful for CI)
AUTO_CLEANUP_CONFLICTS="${AUTO_CLEANUP_CONFLICTS:-false}"

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
    
    if [ "$KEY" == "--non-interactive" ]; then
        NON_INTERACTIVE=true
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
  echo "[$(date +%H:%M:%S)] Launching $engine containers..."
  cd notebooks/$engine
  if "$rebuild" = true; then
      echo "[$(date +%H:%M:%S)]   Rebuilding $engine containers..."
      $DOCKER_COMPOSE_CMD -f docker-compose.yml -f docker-compose.test.yml down -v
      $DOCKER_COMPOSE_CMD -f docker-compose.yml -f docker-compose.test.yml build
  else
      echo "[$(date +%H:%M:%S)]   Using existing $engine containers (no rebuild)"
  fi
  echo "[$(date +%H:%M:%S)]   Starting $engine containers..."
  $DOCKER_COMPOSE_CMD -f docker-compose.yml -f docker-compose.test.yml up -d
  echo "[$(date +%H:%M:%S)]   $engine containers started"
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

function check_port_conflicts() {
    echo "Checking for containers using test ports..."
    CONFLICTS=()
    
    # Get all running containers with their port mappings
    while IFS= read -r line; do
        if [ -z "$line" ]; then
            continue
        fi
        container_name=$(echo "$line" | awk '{print $1}')
        ports=$(echo "$line" | awk '{print $2}')
        
        # Check if any test port is in the port mapping
        for port in $SOLR_PORT $ELASTICSEARCH_PORT $KIBANA_PORT $OPENSEARCH_PORT $OPENSEARCH_PA_PORT $OPENSEARCH_DASHBOARDS_PORT; do
            if echo "$ports" | grep -q ":$port->"; then
                CONFLICTS+=("$container_name (port $port)")
                break
            fi
        done
    done < <(docker ps --format "{{.Names}} {{.Ports}}" 2>/dev/null)
    
    if [ ${#CONFLICTS[@]} -gt 0 ]; then
        echo "================================================"
        echo "⚠️  WARNING: Containers already running on test ports:"
        for conflict in "${CONFLICTS[@]}"; do
            echo "  - $conflict"
        done
        echo "================================================"
        echo ""
        # Check if auto-cleanup is enabled or running with non-interactive flag
        if [ "$AUTO_CLEANUP_CONFLICTS" = "true" ] || [ "$NON_INTERACTIVE" = "true" ]; then
            echo "Auto-cleanup enabled. Cleaning conflicting containers..."
            should_cleanup="y"
        else
            # Interactive mode - always ask for confirmation unless explicitly disabled
            read -p "Should we stop and remove these containers? (y/N): " -n 1 -r
            echo ""
            should_cleanup=$REPLY
        fi
        
        if [[ $should_cleanup =~ ^[Yy]$ ]]; then
            echo "Stopping and removing conflicting containers..."
            for conflict in "${CONFLICTS[@]}"; do
                container=$(echo "$conflict" | cut -d' ' -f1)
                echo "  Stopping $container..."
                docker stop "$container" 2>/dev/null || true
                docker rm "$container" 2>/dev/null || true
            done
            echo "Cleanup complete."
        else
            echo "Keeping existing containers. Tests may fail if ports are in use."
        fi
        echo ""
    else
        echo "No port conflicts detected."
    fi
}

# Check for port conflicts before launching containers
check_port_conflicts

echo "================================================"
echo "== LAUNCHING CONTAINERS"
echo "================================================"
for ENGINE in ${ENGINES}
do
  echo "[$(date +%H:%M:%S)] Launching $ENGINE containers..."
  launch_containers "${ENGINE}" ${REBUILD_CONTAINERS}
done
echo "[$(date +%H:%M:%S)] All containers launched"
echo ""

# Are all services Running?
# If not, fail...
function test_http_service () {
    local port=$1
    local service_name=$2
    local health_endpoint=${3:-"/"}
    local i=0
    local sleep_for=2
    local wait_up_to=300
    local max_dots=50
    local dots=0
    
    echo "[$(date +%H:%M:%S)] Waiting for $service_name to be ready on port $port..."
    printf "  ["
    
    until $(curl --output /dev/null --silent --fail http://localhost:$port$health_endpoint 2>/dev/null); do     
        ((waited=i*sleep_for))
        
        # Show progress dots
        if (( dots < max_dots )); then
            printf "."
            ((dots++))
        else
            printf "\n  ["
            dots=0
        fi
        
        sleep $sleep_for;
        
        if [[ "$waited" -ge "$wait_up_to" ]]; then
            printf "]\n"
            echo "[$(date +%H:%M:%S)] ERROR - $service_name did not start after $wait_up_to seconds"
            echo "[$(date +%H:%M:%S)] TEARDOWN CONTAINERS"
            for ENGINE in $ENGINES
              do
                cd notebooks/$ENGINE
                $DOCKER_COMPOSE_CMD -f docker-compose.yml -f docker-compose.test.yml down -v
                cd ../..
              done
            exit 1
        fi
        ((i++))
    done
    printf "]\n"
    echo "[$(date +%H:%M:%S)] ✓ $service_name is ready (took ${waited}s)"
}

echo "================================================"
echo "== WAITING FOR SERVICES TO BE READY"
echo "================================================"

# Wait for each service with appropriate health endpoints
test_http_service $OPENSEARCH_PORT "OpenSearch" "/_cluster/health"
test_http_service $OPENSEARCH_DASHBOARDS_PORT "OpenSearch Dashboards" "/api/status"
test_http_service $ELASTICSEARCH_PORT "Elasticsearch" "/_cluster/health"
test_http_service $KIBANA_PORT "Kibana" "/api/status"
test_http_service $SOLR_PORT "Solr" "/solr/admin/info/system"

echo "[$(date +%H:%M:%S)] All services are ready!"
echo ""

# Use existing venv or create if missing
# Get back to project root (script may be run from tests/ directory)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

if [ ! -d ".venv" ]; then
    echo "Creating .venv..."
    python3 -m venv .venv
fi
source .venv/bin/activate

# Ensure dependencies are installed
echo "[$(date +%H:%M:%S)] Syncing dependencies with uv..."
uv sync
echo "[$(date +%H:%M:%S)] ✓ Dependencies synced"

echo "================================================"
echo "== RUN TESTS: "
echo "== $TESTS "
# Tests & save result...!
python3 $TESTS
TESTS_CODE="$?"
echo "================================================"
echo "== TEARDOWN "

for ENGINE in ${ENGINES}
do
  cd notebooks/$ENGINE
  $DOCKER_COMPOSE_CMD -f docker-compose.yml -f docker-compose.test.yml down -v
  cd ../..
done

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
