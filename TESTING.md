# Testing Guide for Cluster Client

This guide explains how to test the cluster client against real or simulated cluster nodes.

## Testing Approaches

### 1. Unit Tests (Already Implemented)

The project includes comprehensive unit tests that mock HTTP responses. These tests verify:
- Retry logic and transient error handling
- Rollback mechanisms on partial failures
- Node-level operations and error handling
- Cluster-wide coordination logic

Run unit tests:
```bash
pytest
pytest --cov=cluster_client --cov-report=html
```

### 2. Integration Testing with Mock Server

For testing against a simulated cluster, create a mock server that implements the API specification.

#### Option A: Python Mock Server (Recommended for Development)

Create a file `mock_server.py`:

```python
from flask import Flask, request, jsonify
import random

app = Flask(__name__)

# In-memory storage for groups
groups = {}

# Configuration: simulate failures
FAILURE_RATE = 0.0  # 0.0 = no failures, 0.3 = 30% failure rate
DELAY_MS = 0  # Simulated latency in milliseconds

@app.route('/v1/group/', methods=['POST'])
def create_group():
    # Simulate random failures
    if random.random() < FAILURE_RATE:
        return jsonify({"error": "Simulated server error"}), 500
    
    data = request.get_json()
    group_id = data.get('groupId')
    
    if not group_id:
        return jsonify({"error": "groupId is required"}), 400
    
    if group_id in groups:
        return jsonify({"error": "Group already exists"}), 400
    
    groups[group_id] = {"groupId": group_id}
    return jsonify({"groupId": group_id}), 201

@app.route('/v1/group/', methods=['DELETE'])
def delete_group():
    # Simulate random failures
    if random.random() < FAILURE_RATE:
        return jsonify({"error": "Simulated server error"}), 500
    
    data = request.get_json()
    group_id = data.get('groupId')
    
    if group_id in groups:
        del groups[group_id]
    
    return '', 200

@app.route('/v1/group/<group_id>/', methods=['GET'])
def get_group(group_id):
    if group_id in groups:
        return jsonify(groups[group_id]), 200
    return jsonify({"error": "Not found"}), 404

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "groups": len(groups)}), 200

if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    print(f"Starting mock server on port {port}")
    print(f"Failure rate: {FAILURE_RATE * 100}%")
    app.run(host='0.0.0.0', port=port, debug=True)
```

Start multiple mock servers (simulating cluster nodes):

```bash
# Terminal 1 - Node 1
python mock_server.py 5001

# Terminal 2 - Node 2
python mock_server.py 5002

# Terminal 3 - Node 3
python mock_server.py 5003
```

Configure the cluster client:

```bash
export HOSTS="localhost:5001,localhost:5002,localhost:5003"
export CONNECT_TIMEOUT="5.0"
export READ_TIMEOUT="30.0"
export MAX_RETRY_ATTEMPTS="3"
```

Run the client:

```bash
python -m cluster_client.cli create --group-id test-group-1
python -m cluster_client.cli delete --group-id test-group-1
```

#### Option B: Docker Compose Mock Cluster

Create `docker-compose.mock.yml`:

```yaml
version: '3.8'

services:
  mock-node-1:
    build:
      context: .
      dockerfile: Dockerfile.mock
    ports:
      - "5001:5000"
    environment:
      - NODE_NAME=node1
      - FAILURE_RATE=0.0

  mock-node-2:
    build:
      context: .
      dockerfile: Dockerfile.mock
    ports:
      - "5002:5000"
    environment:
      - NODE_NAME=node2
      - FAILURE_RATE=0.0

  mock-node-3:
    build:
      context: .
      dockerfile: Dockerfile.mock
    ports:
      - "5003:5000"
    environment:
      - NODE_NAME=node3
      - FAILURE_RATE=0.0
```

Create `Dockerfile.mock`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN pip install flask

COPY mock_server.py .

EXPOSE 5000

CMD ["python", "mock_server.py"]
```

Start the mock cluster:

```bash
docker-compose -f docker-compose.mock.yml up
```

Test against the cluster:

```bash
export HOSTS="localhost:5001,localhost:5002,localhost:5003"
python -m cluster_client.cli create --group-id test-group
```

### 3. Testing Failure Scenarios

#### Scenario 1: Test Transient Failures and Retry

Modify mock server to introduce temporary failures:

```python
# In mock_server.py, add a counter
failure_countdown = 2  # Fail the first 2 requests

@app.route('/v1/group/', methods=['POST'])
def create_group():
    global failure_countdown
    if failure_countdown > 0:
        failure_countdown -= 1
        return jsonify({"error": "Temporary failure"}), 500
    
    # Rest of the implementation...
```

Run the client and observe retry behavior in logs:

```bash
python -m cluster_client.cli create --group-id test-retry --log-level DEBUG
```

You should see retry attempts in the JSON logs.

#### Scenario 2: Test Partial Failure and Rollback

Stop one of the mock nodes:

```bash
# In one terminal, stop node 3
# Ctrl+C in the terminal running mock_server.py on port 5003
```

Test create operation:

```bash
export HOSTS="localhost:5001,localhost:5002,localhost:5003"
python -m cluster_client.cli create --group-id test-rollback --log-level INFO
```

Expected behavior:
- Nodes 1 and 2 succeed
- Node 3 fails (connection refused)
- Client triggers rollback on nodes 1 and 2
- Operation reports failure with rollback completed

Verify rollback by checking the mock servers:

```bash
curl http://localhost:5001/health
curl http://localhost:5002/health
```

Both should show 0 groups (rollback successful).

#### Scenario 3: Test Rollback Failure (Critical Scenario)

Create a special mock server that fails delete operations:

```python
# Add to mock_server.py
FAIL_DELETES = False  # Set to True to simulate rollback failures

@app.route('/v1/group/', methods=['DELETE'])
def delete_group():
    if FAIL_DELETES:
        return jsonify({"error": "Delete operation failed"}), 500
    # Rest of implementation...
```

Test workflow:
1. Start 3 mock nodes normally
2. Set node 2 to fail delete operations (FAIL_DELETES = True)
3. Set node 3 to fail create operations
4. Run create operation

```bash
python -m cluster_client.cli create --group-id test-rollback-fail --log-level INFO
```

Expected behavior:
- Nodes 1 and 2 create successfully
- Node 3 fails create
- Rollback initiated
- Node 1 rollback succeeds
- Node 2 rollback fails
- Client raises RollbackIncompleteError
- Exit code 2

Verify inconsistent state:

```bash
curl http://localhost:5002/health  # Should show 1 group (orphaned)
```

#### Scenario 4: Test Idempotent Create (400 Conflict Handling)

```bash
# Create a group
python -m cluster_client.cli create --group-id existing-group

# Try to create it again with default config (should fail and rollback)
python -m cluster_client.cli create --group-id existing-group

# Try with conflict handling enabled
export TREAT_CREATE_CONFLICT_AS_SUCCESS="true"
python -m cluster_client.cli create --group-id existing-group
```

Expected behavior with flag enabled:
- All nodes return 400 (group exists)
- Client verifies with GET that groups exist
- Operation succeeds (idempotent behavior)

### 4. Load and Stress Testing

Create a test script `load_test.py`:

```python
import asyncio
import time
from cluster_client import ClusterClient
from cluster_client.config import Config

async def create_and_delete(group_id: str) -> tuple[float, bool]:
    start_time = time.time()
    config = Config.from_env()
    
    try:
        async with ClusterClient(config) as client:
            # Create
            create_result = await client.create_group(group_id)
            if not create_result.success:
                return time.time() - start_time, False
            
            # Delete
            delete_result = await client.delete_group(group_id)
            return time.time() - start_time, delete_result.success
    except Exception as e:
        print(f"Error for {group_id}: {e}")
        return time.time() - start_time, False

async def run_load_test(num_operations: int):
    print(f"Starting load test with {num_operations} operations...")
    
    tasks = [
        create_and_delete(f"load-test-group-{i}")
        for i in range(num_operations)
    ]
    
    start_time = time.time()
    results = await asyncio.gather(*tasks)
    total_time = time.time() - start_time
    
    successful = sum(1 for _, success in results if success)
    avg_duration = sum(duration for duration, _ in results) / len(results)
    
    print(f"\nLoad Test Results:")
    print(f"Total time: {total_time:.2f}s")
    print(f"Operations: {num_operations}")
    print(f"Successful: {successful}")
    print(f"Failed: {num_operations - successful}")
    print(f"Average operation time: {avg_duration:.3f}s")
    print(f"Operations per second: {num_operations / total_time:.2f}")

if __name__ == "__main__":
    asyncio.run(run_load_test(100))
```

Run the load test:

```bash
export HOSTS="localhost:5001,localhost:5002,localhost:5003"
python load_test.py
```

### 5. Testing with Real Cluster Nodes

If you have access to real cluster nodes:

#### Step 1: Verify Node Connectivity

```bash
curl -X POST https://node1.example.com/v1/group/ \
  -H "Content-Type: application/json" \
  -d '{"groupId": "test-connectivity"}'

curl -X GET https://node1.example.com/v1/group/test-connectivity/

curl -X DELETE https://node1.example.com/v1/group/ \
  -H "Content-Type: application/json" \
  -d '{"groupId": "test-connectivity"}'
```

#### Step 2: Configure the Client

```bash
export HOSTS="node1.example.com,node2.example.com,node3.example.com"
export CONNECT_TIMEOUT="10.0"
export READ_TIMEOUT="60.0"
export MAX_RETRY_ATTEMPTS="5"
export TREAT_CREATE_CONFLICT_AS_SUCCESS="false"
```

#### Step 3: Run Test Operations

```bash
# Test create
python -m cluster_client.cli create --group-id production-test-1 --log-level INFO

# Verify on all nodes
curl https://node1.example.com/v1/group/production-test-1/
curl https://node2.example.com/v1/group/production-test-1/
curl https://node3.example.com/v1/group/production-test-1/

# Test delete
python -m cluster_client.cli delete --group-id production-test-1 --log-level INFO

# Verify deletion
curl https://node1.example.com/v1/group/production-test-1/  # Should return 404
```

### 6. Monitoring and Observability

#### Parse JSON Logs

Create `parse_logs.py`:

```python
import json
import sys

def parse_logs(log_file):
    operations = {}
    
    with open(log_file, 'r') as f:
        for line in f:
            try:
                log = json.loads(line)
                correlation_id = log.get('correlation_id')
                
                if correlation_id:
                    if correlation_id not in operations:
                        operations[correlation_id] = []
                    operations[correlation_id].append(log)
            except json.JSONDecodeError:
                continue
    
    for corr_id, logs in operations.items():
        print(f"\nOperation: {corr_id}")
        for log in logs:
            print(f"  [{log['level']}] {log['message']}")
            if 'host' in log:
                print(f"    Host: {log['host']}")
            if 'attempt' in log:
                print(f"    Attempt: {log['attempt']}")

if __name__ == "__main__":
    parse_logs(sys.argv[1])
```

Use it:

```bash
python -m cluster_client.cli create --group-id test > operation.log 2>&1
python parse_logs.py operation.log
```

#### Monitor Metrics

Create a monitoring script `monitor.py`:

```python
import asyncio
import time
from cluster_client import ClusterClient
from cluster_client.config import Config

async def monitor_cluster_health():
    config = Config.from_env()
    
    while True:
        print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Cluster Health Check")
        
        async with ClusterClient(config) as client:
            # Create test group
            test_id = f"health-check-{int(time.time())}"
            create_result = await client.create_group(test_id)
            
            print(f"Create: {'✓' if create_result.success else '✗'}")
            
            if create_result.success:
                # Clean up
                delete_result = await client.delete_group(test_id)
                print(f"Delete: {'✓' if delete_result.success else '✗'}")
            
            # Print node status
            for node in create_result.node_results:
                status = "UP" if node.success else "DOWN"
                print(f"  {node.host}: {status} (attempts: {node.attempts})")
        
        await asyncio.sleep(60)  # Check every minute

if __name__ == "__main__":
    asyncio.run(monitor_cluster_health())
```

### 7. Kubernetes Testing

#### Deploy to Test Namespace

```bash
kubectl create namespace cluster-client-test

kubectl apply -f manifests/configmap.yaml -n cluster-client-test

# Create a test job
cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: test-create-group
  namespace: cluster-client-test
spec:
  template:
    spec:
      containers:
      - name: cluster-client
        image: cluster-client:latest
        args: ["create", "--group-id", "k8s-test-group", "--log-level", "DEBUG"]
        envFrom:
        - configMapRef:
            name: cluster-client-config
      restartPolicy: Never
  backoffLimit: 2
EOF

# Check job status
kubectl get jobs -n cluster-client-test
kubectl logs job/test-create-group -n cluster-client-test

# Cleanup
kubectl delete job test-create-group -n cluster-client-test
```