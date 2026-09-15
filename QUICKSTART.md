# Quick Start Testing Guide

## Step 1: Install Flask (if not already installed)

```bash
pip install flask
```

## Step 2: Start the Mock Cluster

### Option A: Using the Batch Script (Windows)
```bash
start_mock_cluster.bat
```

This will open 3 command windows, each running a mock node on ports 5001, 5002, and 5003.

### Option B: Manual Start (Any OS)

Open 3 separate terminal windows and run:

**Terminal 1:**
```bash
python mock_server.py 5001
```

**Terminal 2:**
```bash
python mock_server.py 5002
```

**Terminal 3:**
```bash
python mock_server.py 5003
```

## Step 3: Configure the Client

In a new terminal (PowerShell or Command Prompt):

```bash
$env:HOSTS="localhost:5001,localhost:5002,localhost:5003"
```

Or for Command Prompt:
```cmd
set HOSTS=localhost:5001,localhost:5002,localhost:5003
```

## Step 4: Test Basic Operations

### Create a Group
```bash
python -m cluster_client.cli create --group-id my-test-group
```

Expected output:
```
Operation: create
Group ID: my-test-group
Success: True

Node results:
  [OK] localhost:5001: status=201, attempts=1
  [OK] localhost:5002: status=201, attempts=1
  [OK] localhost:5003: status=201, attempts=1
```

### Delete a Group
```bash
python -m cluster_client.cli delete --group-id my-test-group
```

Expected output:
```
Operation: delete
Group ID: my-test-group
Success: True

Node results:
  [OK] localhost:5001: status=200, attempts=1
  [OK] localhost:5002: status=200, attempts=1
  [OK] localhost:5003: status=200, attempts=1
```

## Step 5: Test Failure Scenarios

### Scenario 1: Test Rollback (Stop One Node)

1. Stop one of the mock servers (Ctrl+C in that terminal)
2. Try to create a group:

```bash
python -m cluster_client.cli create --group-id rollback-test --log-level INFO
```

Expected: 
- Two nodes succeed
- One node fails (connection refused)
- Rollback is triggered
- Operation reports failure with successful rollback

3. Verify rollback worked:
```bash
curl http://localhost:5001/health
curl http://localhost:5002/health
```

Both should show 0 groups.

### Scenario 2: Test Idempotent Create

1. Create a group:
```bash
python -m cluster_client.cli create --group-id existing-group
```

2. Try to create it again (should fail):
```bash
python -m cluster_client.cli create --group-id existing-group
```

Expected: 400 errors trigger rollback

3. Enable idempotent mode and try again:
```bash
$env:TREAT_CREATE_CONFLICT_AS_SUCCESS="true"
python -m cluster_client.cli create --group-id existing-group
```

Expected: Operation succeeds (idempotent)

## Step 6: Check Cluster Health

```bash
curl http://localhost:5001/health
curl http://localhost:5002/health
curl http://localhost:5003/health
```

You'll see which groups exist on each node.

## Step 7: View Detailed Logs

Run with DEBUG log level:
```bash
python -m cluster_client.cli create --group-id debug-test --log-level DEBUG
```

You'll see:
- Correlation IDs tracking the operation
- Retry attempts on failures
- Detailed per-node results

## Troubleshooting

### "Connection Refused" Errors
- Ensure all mock servers are running
- Check that ports 5001, 5002, 5003 are not blocked
- Verify HOSTS environment variable is set correctly

### "ModuleNotFoundError: No module named 'flask'"
```bash
pip install flask
```

### Servers Won't Start on Specified Ports
Ports might be in use. Change to different ports:
```bash
python mock_server.py 6001
python mock_server.py 6002
python mock_server.py 6003

# Update HOSTS
$env:HOSTS="localhost:6001,localhost:6002,localhost:6003"
```

## Clean Up

To stop all mock servers:
- Press Ctrl+C in each terminal window

## Next Steps

See [TESTING.md](TESTING.md) for:
- Load testing scripts
- Advanced failure scenarios
- Docker Compose setup
- Kubernetes deployment testing
- Production cluster testing
