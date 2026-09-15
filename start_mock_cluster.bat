@echo off
echo ============================================================
echo Starting Mock Cluster Nodes
echo ============================================================
echo.
echo This will start 3 mock cluster nodes on ports 5001, 5002, 5003
echo Press Ctrl+C in each window to stop the servers
echo.
echo Starting in 3 seconds...
timeout /t 3 /nobreak > nul

start "Mock Node 1 (Port 5001)" cmd /k "python mock_server.py 5001"
timeout /t 1 /nobreak > nul

start "Mock Node 2 (Port 5002)" cmd /k "python mock_server.py 5002"
timeout /t 1 /nobreak > nul

start "Mock Node 3 (Port 5003)" cmd /k "python mock_server.py 5003"

echo.
echo ============================================================
echo Mock cluster nodes started!
echo ============================================================
echo.
echo Test your client with:
echo   set HOSTS=localhost:5001,localhost:5002,localhost:5003
echo   python -m cluster_client.cli create --group-id test-group
echo.
echo Check cluster health:
echo   curl http://localhost:5001/health
echo   curl http://localhost:5002/health
echo   curl http://localhost:5003/health
echo.
