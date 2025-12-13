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
#   --non-interactive         Skip all prompts and auto-cleanup conflicts (useful for CI)
#
# Environment Variables:
#   AUTO_CLEANUP_CONFLICTS    Set to 'true' to auto-cleanup without prompting
#   SOLR_PORT                 Custom Solr test port (default: 18983)
#   ELASTICSEARCH_PORT        Custom Elasticsearch test port (default: 19200)
#   OPENSEARCH_PORT           Custom OpenSearch test port (default: 19201)
#   SERVICE_WAIT_TIMEOUT      Seconds to wait for services to be ready (default: 300)
#   NOTEBOOK_TIMEOUT_HOURS    Hours to allow per notebook execution (default: 6)
#
# Pytest Test Options:
#   PYTEST_ARGS               Additional pytest arguments (e.g., "--lf", "-k opensearch", "-n auto")
#
# Pytest Usage Examples:
#   PYTEST_ARGS="--lf" ./tests/test.sh                     # Re-run last failed tests
#   PYTEST_ARGS="-k opensearch" ./tests/test.sh            # Run only opensearch notebooks
#   PYTEST_ARGS="-n auto" ./tests/test.sh                  # Parallel execution (faster)
#   PYTEST_ARGS="--sw" ./tests/test.sh                     # Stepwise: stop at first failure
#
# Features:
#   - Automatic cleanup on exit (success, failure, or interruption via Ctrl+C)
#   - Port conflict detection and resolution with port release verification
#   - Service health checking with detailed progress indicators
#   - Multi-engine parallel testing support
#
# Examples:
#   ./tests/test.sh                                    # Run all tests interactively
#   ./tests/test.sh --non-interactive                  # Run in CI mode (no prompts)
#   ./tests/test.sh --engines=solr                     # Test only Solr
#   ./tests/test.sh --rebuild-containers               # Rebuild before testing
#   PYTEST_ARGS="--lf" ./tests/test.sh                 # Re-run last failed notebooks
#   PYTEST_ARGS="-k elasticsearch" ./tests/test.sh     # Run only elasticsearch notebooks
#   PYTEST_ARGS="-n auto" ./tests/test.sh              # Parallel execution (4x faster)
#

TESTS="pytest tests/test_notebooks.py"
PYTEST_ARGS="${PYTEST_ARGS:-}"  # Additional pytest arguments from environment
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

# Track which engines we've launched so cleanup can handle them
LAUNCHED_ENGINES=()

# Cleanup function to run on exit (success, failure, or interruption)
cleanup_containers() {
    local exit_code=$?
    if [ ${#LAUNCHED_ENGINES[@]} -gt 0 ]; then
        echo ""
        echo "================================================"
        echo "== CLEANUP: Stopping containers"
        echo "================================================"
        for ENGINE in "${LAUNCHED_ENGINES[@]}"; do
            echo "[$(date +%H:%M:%S)] Stopping $ENGINE containers..."
            cd notebooks/$ENGINE 2>/dev/null || continue
            $DOCKER_COMPOSE_CMD -f docker-compose.yml -f docker-compose.test.yml down -v 2>/dev/null || true
            cd ../..
        done
        echo "[$(date +%H:%M:%S)] Cleanup complete"
    fi
    exit $exit_code
}

# Register cleanup to run on script exit (normal, error, or interrupt)
trap cleanup_containers EXIT INT TERM

# Parse any args...
for ARGUMENT in "$@"
do
    KEY=`echo $ARGUMENT | cut -d '=' -f 1`
    if [ "$KEY" == "--rebuild-containers" ]; then
        REBUILD_CONTAINERS=true
    fi

    if [ "$KEY" == "--engines" ]; then
        ENGINE_ARG=$(echo "$ARGUMENT" | cut -d '=' -f 2)
    fi
    
    if [ "$KEY" == "--non-interactive" ]; then
        NON_INTERACTIVE=true
    fi

done

if [ -z "${ENGINE_ARG}" ]; then
  ENGINE_ARG="solr,elasticsearch,opensearch"
fi
ENGINES=$(awk -F',' '{ for( i=1; i<=NF; i++ ) print $i }' <<< "$ENGINE_ARG")

# Validate test command (pytest command expected)
if [[ "$TESTS" == *" "* ]]; then
    # Extract the test file path to validate it exists
    TEST_FILE=$(echo "$TESTS" | awk '{print $NF}')
    if [ ! -f "$TEST_FILE" ]; then
        echo "================================================"
        echo "> ERROR: Test file not found 😾"
        echo "> Path: $TEST_FILE"
        echo "> Command: $TESTS"
        echo "> Current directory: $(pwd)"
        echo "================================================"
        exit 1
    fi
else
    echo "================================================"
    echo "> ERROR: Test command must be a pytest command"
    echo "> Expected format: pytest tests/test_notebooks.py"
    echo "> Got: $TESTS"
    echo "================================================"
    exit 1
fi

echo "✓ Test file found: $TESTS"

# Confirm needed Requirements are present here
# TODO: may need to check version in future
COMMANDS=( 'docker' 'python3')

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
  
  # Track that we launched this engine so cleanup can handle it
  LAUNCHED_ENGINES+=("$engine")
}

function wait_for_port_release() {
    local port=$1
    local max_wait=10
    local waited=0
    
    # Check if netstat or ss is available
    local check_cmd=""
    if command -v ss >/dev/null 2>&1; then
        check_cmd="ss -tuln"
    elif command -v netstat >/dev/null 2>&1; then
        check_cmd="netstat -tuln"
    else
        # If neither is available, just do a simple sleep
        echo "  Warning: netstat/ss not available, waiting 3 seconds for port $port..."
        sleep 3
        return 0
    fi
    
    while $check_cmd 2>/dev/null | grep -q ":$port "; do
        sleep 1
        ((waited++))
        if [ $waited -ge $max_wait ]; then
            echo "  ⚠️  Warning: Port $port still in use after $max_wait seconds"
            return 1
        fi
    done
    
    if [ $waited -gt 0 ]; then
        echo "  ✓ Port $port released (took ${waited}s)"
    fi
    return 0
}

function check_port_conflicts() {
    echo "Checking for containers using test ports..."
    CONFLICTS=()
    CONFLICT_PORTS=()
    
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
                CONFLICT_PORTS+=("$port")
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
            
            # Wait for ports to be released
            echo "Waiting for ports to be released..."
            local all_released=true
            for port in "${CONFLICT_PORTS[@]}"; do
                if ! wait_for_port_release "$port"; then
                    all_released=false
                fi
            done
            
            if [ "$all_released" = false ]; then
                echo ""
                echo "⚠️  WARNING: Some ports may still be in use. Tests may fail."
                echo "   You may need to wait a moment or manually check: sudo ss -tuln | grep -E ':(${CONFLICT_PORTS[*]// /|})'"
            else
                echo "✓ All ports successfully released."
            fi
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
    # Allow configuration of service wait timeout via environment variable (default: 5 minutes)
    local wait_up_to=${SERVICE_WAIT_TIMEOUT:-300}
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
            echo "[$(date +%H:%M:%S)] Service health check failed. Cleanup will be handled automatically."
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

# Check if parallel execution is requested
if echo "$PYTEST_ARGS" | grep -qE '\s-n\s+[0-9]+|\s-n\s+auto|\s--numprocesses'; then
    echo "================================================"
    echo "⚠️  PARALLEL EXECUTION DETECTED"
    echo "================================================"
    echo "Note: Docker containers are started once with base ports."
    echo "Each pytest worker will use worker-specific ports automatically."
    echo ""
    echo "For best results with parallel execution:"
    echo "  - Use --dist loadgroup to group tests by engine"
    echo "  - Or run sequential tests if all engines needed per worker"
    echo "================================================"
    echo ""
fi

echo "================================================"
echo "== RUN TESTS: "
echo "== $TESTS $PYTEST_ARGS"
# Tests & save result...!
$TESTS $PYTEST_ARGS
TESTS_CODE="$?"

# Note: Container teardown will be handled automatically by the EXIT trap

echo "=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*"
if [ "$TESTS_CODE" == "0" ]
then
   echo "================================================"
   echo "> WOOHOO!  Tests Passed 👍 For:"
else
   echo "================================================"
   echo "> POOP!    Tests Failed 💩 For:"
fi
git log -n 1 2>/dev/null || echo "(Not in git repository)"
echo "================================================"
echo " ==============================================="
echo " HELLO-LTR TEST DETAILS"
echo " Containers Rebuilt? $REBUILD_CONTAINERS"
echo " Test Command: $TESTS"
echo "================================================"

# Exit with the test result code (trap will handle cleanup)
exit $TESTS_CODE
