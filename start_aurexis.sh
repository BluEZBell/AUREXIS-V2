#!/bin/bash
echo "===================================================="
echo "AUREXIS Institutional Launch - Production Freeze Phase"
echo "===================================================="

# Check for Python installation
if ! command -v python3 &> /dev/null; then
    echo "[FATAL] python3 is not installed or not in PATH."
    read -p "Press enter to continue..."
    exit 1
fi

# Check for Virtual Environment
if [ ! -d ".venv" ]; then
    echo "[INFO] Virtual environment not found. Initializing..."
    python3 -m venv .venv
    if [ $? -ne 0 ]; then
        echo "[FATAL] Failed to create virtual environment."
        read -p "Press enter to continue..."
        exit 1
    fi
    echo "[INFO] Virtual environment created."
    
    # Activate and install dependencies
    source .venv/bin/activate
    echo "[INFO] Installing frozen dependencies..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "[FATAL] Failed to install dependencies."
        read -p "Press enter to continue..."
        exit 1
    fi
    echo "[INFO] Dependencies installed successfully."
else
    echo "[INFO] Virtual environment found. Activating..."
    source .venv/bin/activate
fi

echo "[INFO] Launching AUREXIS Supervisor..."
python3 aurexis_supervisor.py

if [ $? -ne 0 ]; then
    echo "[FATAL ERROR] Supervisor crashed at the OS level!"
    read -p "Press enter to continue..."
else
    echo "[INFO] AUREXIS Supervisor exited gracefully."
    read -p "Press enter to continue..."
fi
