# Cluster Client

A production-ready Python client for managing distributed group resources across cluster nodes with automatic rollback on failures.

## Overview

This client library provides reliable create and delete operations for group objects across a cluster of nodes. When creating a group, the operation is applied atomically across all nodes. If any node fails during creation, all successful operations are automatically rolled back to maintain cluster consistency.

The library handles transient failures through automatic retry with exponential backoff and provides detailed operation results for monitoring and debugging.

## Key Features

- **Atomic Operations**: Create operations are all-or-nothing across the cluster
- **Automatic Rollback**: Failed creates trigger automatic cleanup on successful nodes
- **Retry Logic**: Transient failures (timeouts, 5xx errors) are automatically retried
- **Structured Logging**: JSON-formatted logs with correlation IDs for operation tracking
- **Type Safety**: Full type hints and mypy validation
- **Comprehensive Testing**: 100% coverage of critical paths including rollback scenarios

## Architecture

### High-Level Architecture

![High-Level Architecture](\assets\image.png)

### Component Architecture

![Component Architecture](\assets\image2.jpg)

### Create Operation Flow

![Create Operation Flow](\assets\image3.jpg)

### Retry Logic Flow

![Retry Logic Flow](\assets\image4.jpg)

## Installation

### Prerequisites

- Python 3.12 or higher
- pip or poetry for package management

### From Source

```bash
git clone <repository-url>
cd cluster-client
pip install -e .
```

### For Development

```bash
pip install -e ".[dev]"
```

This installs the package with development dependencies including pytest, mypy, and ruff.

## Configuration

The client is configured entirely through environment variables:

| Variable                           | Description                                    | Default | Required |
| ---------------------------------- | ---------------------------------------------- | ------- | -------- |
| `HOSTS`                            | Comma-separated node hostnames or JSON array   | -       | Yes      |
| `CONNECT_TIMEOUT`                  | Connection timeout in seconds                  | 5.0     | No       |
| `READ_TIMEOUT`                     | Read timeout in seconds                        | 30.0    | No       |
| `MAX_RETRY_ATTEMPTS`               | Maximum retry attempts for transient failures  | 3       | No       |
| `BASE_BACKOFF_DELAY`               | Base delay in seconds for exponential backoff  | 1.0     | No       |
| `TREAT_CREATE_CONFLICT_AS_SUCCESS` | Treat 400 on create as success if group exists | false   | No       |

### Configuration Examples

**Comma-separated hosts:**

```bash
export HOSTS="node1.example.com,node2.example.com,node3.example.com"
```

**JSON array hosts:**

```bash
export HOSTS='["node1.example.com","node2.example.com","node3.example.com"]'
```

**Full configuration:**

```bash
export HOSTS="node1.example.com,node2.example.com,node3.example.com"
export CONNECT_TIMEOUT="10.0"
export READ_TIMEOUT="60.0"
export MAX_RETRY_ATTEMPTS="5"
export BASE_BACKOFF_DELAY="2.0"
export TREAT_CREATE_CONFLICT_AS_SUCCESS="true"
```

## Usage

### Command Line Interface

The simplest way to use the client is through the command-line interface:

```bash
python -m cluster_client.cli create --group-id my-group
python -m cluster_client.cli delete --group-id my-group
```

With custom log level:

```bash
python -m cluster_client.cli create --group-id my-group --log-level DEBUG
```

### Python API

For programmatic use, import and use the `ClusterClient` directly:

```python
from cluster_client import ClusterClient
from cluster_client.config import Config

config = Config.from_env()

async with ClusterClient(config) as client:
    result = await client.create_group("my-group")

    if result.success:
        print(f"Group created on all {len(result.node_results)} nodes")
    else:
        print(f"Operation failed")
        if result.rolled_back:
            print("Rollback completed successfully")
```

### Error Handling

The client provides detailed error information through exceptions and result objects:

```python
from cluster_client import ClusterClient, RollbackIncompleteError
from cluster_client.config import Config

config = Config.from_env()

try:
    async with ClusterClient(config) as client:
        result = await client.create_group("my-group")

        if not result.success:
            for node_result in result.node_results:
                if not node_result.success:
                    print(f"Failed on {node_result.host}: {node_result.error}")

except RollbackIncompleteError as e:
    print(f"CRITICAL: Rollback failed for group {e.group_id}")
    print(f"Orphaned nodes: {', '.join(e.orphaned_nodes)}")
    for node in e.rollback_results:
        if not node.success:
            print(f"  {node.host}: {node.error}")
```

## Local Development

### Running Tests

Run the full test suite:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=cluster_client --cov-report=html
```

Run specific test file:

```bash
pytest tests/test_cluster_client_create.py
```

### Type Checking

```bash
mypy src/cluster_client
```

### Linting and Formatting

Format code:

```bash
ruff format src/ tests/
```

Run linter:

```bash
ruff check src/ tests/
```

Fix auto-fixable issues:

```bash
ruff check --fix src/ tests/
```

### Setting Up a Development Environment

1. Clone the repository:

```bash
git clone <repository-url>
cd cluster-client
```

2. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install development dependencies:

```bash
pip install -e ".[dev]"
```

4. Run tests to verify setup:

```bash
pytest
```

## Docker Deployment

### Building the Image

```bash
docker build -t cluster-client:latest .
```

### Running with Docker

Create operation:

```bash
docker run --rm \
  -e HOSTS="node1.example.com,node2.example.com,node3.example.com" \
  cluster-client:latest \
  create --group-id my-group
```

Delete operation:

```bash
docker run --rm \
  -e HOSTS="node1.example.com,node2.example.com,node3.example.com" \
  cluster-client:latest \
  delete --group-id my-group
```

With all configuration options:

```bash
docker run --rm \
  -e HOSTS="node1.example.com,node2.example.com,node3.example.com" \
  -e CONNECT_TIMEOUT="10.0" \
  -e READ_TIMEOUT="60.0" \
  -e MAX_RETRY_ATTEMPTS="5" \
  cluster-client:latest \
  create --group-id my-group --log-level DEBUG
```

## Kubernetes Deployment

### Prerequisites

- Kubernetes cluster (1.19+)
- kubectl configured to access your cluster
- Docker image pushed to a registry accessible by your cluster

### Deployment Steps

1. Update the ConfigMap with your cluster nodes:

```bash
kubectl apply -f manifests/configmap.yaml
```

2. Create a Kubernetes Job to create a group:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: create-group-example
spec:
  template:
    spec:
      containers:
        - name: cluster-client
          image: cluster-client:latest
          args: ["create", "--group-id", "example-group"]
          envFrom:
            - configMapRef:
                name: cluster-client-config
      restartPolicy: Never
  backoffLimit: 2
```

3. Apply the Job:

```bash
kubectl apply -f job.yaml
```

4. Check Job status:

```bash
kubectl get jobs
kubectl logs job/create-group-example
```

5. Clean up completed Jobs:

```bash
kubectl delete job create-group-example
```

### ConfigMap Customization

Edit `manifests/configmap.yaml` to match your environment:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: cluster-client-config
data:
  HOSTS: '["node1.prod.example.com","node2.prod.example.com","node3.prod.example.com"]'
  CONNECT_TIMEOUT: "10.0"
  READ_TIMEOUT: "60.0"
  MAX_RETRY_ATTEMPTS: "5"
  BASE_BACKOFF_DELAY: "2.0"
  TREAT_CREATE_CONFLICT_AS_SUCCESS: "false"
```

## Design Decisions

### Concurrency Over Sequential Operations

Operations are executed concurrently across all nodes using `asyncio.gather()`. This provides:

- Faster completion times (parallel execution)
- Consistent cluster state snapshots
- Simpler rollback logic (all succeeded nodes are known upfront)

### Best-Effort Delete Operations

Delete operations do not trigger rollbacks for these reasons:

- Deleting a non-existent resource is idempotent
- There is no "undo" for a delete operation
- Partial deletes can be safely retried
- Operators can inspect the result and retry failed nodes

### Rollback Incomplete Error

When rollback itself fails, the client raises `RollbackIncompleteError` with complete details rather than silently returning a failure. This ensures:

- Operators are immediately aware of inconsistent cluster state
- All diagnostic information is preserved
- Manual intervention can be properly coordinated
- The error cannot be accidentally ignored

### Configuration Through Environment Variables

Using environment variables for configuration provides:

- Standard 12-factor app compliance
- Easy integration with container orchestration
- Separation of code and configuration
- No sensitive data in source control

### Structured JSON Logging

All logs are output as JSON with correlation IDs:

- Easy integration with log aggregation systems
- Traceable request flows across async operations
- Machine-readable for automated alerting
- Human-readable with proper tools

## Troubleshooting

### All Create Operations Fail

If all nodes fail during create:

- Check network connectivity to cluster nodes
- Verify HOSTS configuration is correct
- Check node API health with curl/httpx
- Review logs for specific error messages

### Rollback Incomplete Error

If you encounter a `RollbackIncompleteError`:

1. Note the orphaned nodes from the error message
2. Manually verify group status on orphaned nodes with GET requests
3. Manually delete from orphaned nodes if necessary
4. Investigate why the rollback failed (check logs)
5. Consider increasing retry attempts or timeouts

### Timeout Errors

If operations consistently timeout:

- Increase `CONNECT_TIMEOUT` or `READ_TIMEOUT`
- Check network latency to cluster nodes
- Verify nodes are responding within configured timeouts
- Consider increasing `MAX_RETRY_ATTEMPTS`

### 400 Errors on Create

If create operations return 400:

- Verify the group doesn't already exist
- Consider setting `TREAT_CREATE_CONFLICT_AS_SUCCESS=true` for idempotency
- Check the API documentation for valid group ID format
- Review the full error message in logs

## API Specification

The client communicates with cluster nodes using this REST API:

### Create Group

```
POST /v1/group/
Content-Type: application/json

{
  "groupId": "string"
}
```

Success: `201 Created`
Error: `400 Bad Request` (group exists)

### Delete Group

```
DELETE /v1/group/
Content-Type: application/json

{
  "groupId": "string"
}
```

Success: `200 OK`

### Get Group

```
GET /v1/group/{groupId}/
```

Success: `200 OK` with `{"groupId": "string"}`
Error: `404 Not Found`
