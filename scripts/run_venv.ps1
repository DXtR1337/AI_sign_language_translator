$ScriptsDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepositoryRoot = Split-Path -Parent $ScriptsDirectory

# Activate the virtual environment
& "$RepositoryRoot\venv\Scripts\Activate.ps1"

# Run the Python script
python "$RepositoryRoot\src\main.py"
