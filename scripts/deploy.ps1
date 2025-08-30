# GeckoTerminal Data Collector Deployment Script (PowerShell)
# This script handles deployment of the collector in various environments on Windows

param(
    [Parameter(Position=0)]
    [string]$Command,
    
    [Parameter(Position=1, ValueFromRemainingArguments=$true)]
    [string[]]$Arguments,
    
    [string]$Environment = "production",
    [string]$Version = "latest",
    [string]$ConfigFile = "config.yaml",
    [switch]$WithPostgres,
    [switch]$WithRedis,
    [switch]$WithMonitoring,
    [switch]$Follow,
    [switch]$Help
)

# Script configuration
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# Colors for output
$Colors = @{
    Red = "Red"
    Green = "Green"
    Yellow = "Yellow"
    Blue = "Blue"
    White = "White"
}

# Logging functions
function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor $Colors.Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor $Colors.Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor $Colors.Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor $Colors.Red
}

# Help function
function Show-Help {
    @"
GeckoTerminal Data Collector Deployment Script (PowerShell)

Usage: .\deploy.ps1 [OPTIONS] COMMAND

Commands:
    build           Build Docker image
    deploy          Deploy the application
    start           Start the services
    stop            Stop the services
    restart         Restart the services
    status          Show service status
    logs            Show service logs
    backup          Create data backup
    restore         Restore from backup
    cleanup         Clean up old resources
    health          Check system health

Options:
    -Environment ENV        Deployment environment (default: production)
    -Version VERSION        Application version (default: latest)
    -ConfigFile FILE        Configuration file (default: config.yaml)
    -WithPostgres          Include PostgreSQL service
    -WithRedis             Include Redis service
    -WithMonitoring        Include monitoring stack
    -Follow                Follow logs in real-time
    -Help                  Show this help message

Environment Variables:
    GECKO_DB_URL            Database connection URL
    GECKO_LOG_LEVEL         Logging level (DEBUG, INFO, WARNING, ERROR)
    POSTGRES_PASSWORD       PostgreSQL password (if using PostgreSQL)
    GRAFANA_PASSWORD        Grafana admin password (if using monitoring)

Examples:
    .\deploy.ps1 build                           # Build Docker image
    .\deploy.ps1 deploy                          # Deploy with default settings
    .\deploy.ps1 -Environment development deploy # Deploy in development mode
    .\deploy.ps1 start -WithMonitoring          # Start with monitoring stack
    .\deploy.ps1 backup C:\backups\gecko        # Create backup
    .\deploy.ps1 logs -Follow                   # Follow logs in real-time

"@
}

# Check prerequisites
function Test-Prerequisites {
    Write-Info "Checking prerequisites..."
    
    # Check if Docker is installed and running
    try {
        $null = docker --version
    }
    catch {
        Write-Error "Docker is not installed. Please install Docker Desktop first."
        exit 1
    }
    
    try {
        $null = docker info 2>$null
    }
    catch {
        Write-Error "Docker is not running. Please start Docker Desktop first."
        exit 1
    }
    
    # Check if Docker Compose is available
    $script:DockerCompose = "docker-compose"
    try {
        $null = docker-compose --version
    }
    catch {
        try {
            $null = docker compose version
            $script:DockerCompose = "docker compose"
        }
        catch {
            Write-Error "Docker Compose is not available. Please install Docker Compose."
            exit 1
        }
    }
    
    Write-Success "Prerequisites check passed"
}

# Load environment configuration
function Import-Environment {
    Write-Info "Loading environment configuration for: $Environment"
    
    # Load environment-specific configuration
    $EnvFile = Join-Path $ProjectRoot ".env.$Environment"
    if (Test-Path $EnvFile) {
        Write-Info "Loading environment file: $EnvFile"
        Get-Content $EnvFile | ForEach-Object {
            if ($_ -match '^([^=]+)=(.*)$') {
                [Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
            }
        }
    }
    else {
        Write-Warning "Environment file not found: $EnvFile"
    }
    
    # Load default .env file
    $DefaultEnvFile = Join-Path $ProjectRoot ".env"
    if (Test-Path $DefaultEnvFile) {
        Write-Info "Loading default environment file: $DefaultEnvFile"
        Get-Content $DefaultEnvFile | ForEach-Object {
            if ($_ -match '^([^=]+)=(.*)$') {
                [Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
            }
        }
    }
    
    # Set build metadata
    $env:BUILD_DATE = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $env:VERSION = $Version
    
    try {
        $env:VCS_REF = (git rev-parse --short HEAD 2>$null)
    }
    catch {
        $env:VCS_REF = "unknown"
    }
}

# Build Docker image
function Build-Image {
    Write-Info "Building Docker image..."
    
    Set-Location $ProjectRoot
    
    $buildArgs = @(
        "--build-arg", "BUILD_DATE=$env:BUILD_DATE",
        "--build-arg", "VERSION=$env:VERSION",
        "--build-arg", "VCS_REF=$env:VCS_REF",
        "-t", "gecko-terminal-collector:$Version",
        "-t", "gecko-terminal-collector:latest",
        "."
    )
    
    & docker build @buildArgs
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Docker build failed"
        exit 1
    }
    
    Write-Success "Docker image built successfully"
}

# Deploy application
function Deploy-Application {
    Write-Info "Deploying GeckoTerminal Data Collector..."
    
    Set-Location $ProjectRoot
    
    # Create necessary directories
    $directories = @("data", "logs", "backups")
    foreach ($dir in $directories) {
        if (!(Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir | Out-Null
        }
    }
    
    # Copy configuration if it doesn't exist
    if (!(Test-Path $ConfigFile)) {
        $exampleConfig = "config.yaml.example"
        if (Test-Path $exampleConfig) {
            Write-Info "Creating configuration file from example"
            Copy-Item $exampleConfig $ConfigFile
        }
        else {
            Write-Warning "No configuration file found. Please create $ConfigFile"
        }
    }
    
    # Determine which services to start
    $profiles = @()
    if ($WithPostgres) { $profiles += "--profile", "postgres" }
    if ($WithRedis) { $profiles += "--profile", "redis" }
    if ($WithMonitoring) { $profiles += "--profile", "monitoring" }
    
    # Deploy with Docker Compose
    $composeArgs = @($profiles) + @("up", "-d")
    & $DockerCompose @composeArgs
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Deployment failed"
        exit 1
    }
    
    Write-Success "Deployment completed"
}

# Start services
function Start-Services {
    Write-Info "Starting services..."
    
    Set-Location $ProjectRoot
    
    # Determine profiles
    $profiles = @()
    if ($WithPostgres) { $profiles += "--profile", "postgres" }
    if ($WithRedis) { $profiles += "--profile", "redis" }
    if ($WithMonitoring) { $profiles += "--profile", "monitoring" }
    
    $composeArgs = @($profiles) + @("up", "-d")
    & $DockerCompose @composeArgs
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to start services"
        exit 1
    }
    
    Write-Success "Services started"
}

# Stop services
function Stop-Services {
    Write-Info "Stopping services..."
    
    Set-Location $ProjectRoot
    & $DockerCompose down
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to stop services"
        exit 1
    }
    
    Write-Success "Services stopped"
}

# Restart services
function Restart-Services {
    Write-Info "Restarting services..."
    
    Stop-Services
    Start-Services
    
    Write-Success "Services restarted"
}

# Show service status
function Show-Status {
    Write-Info "Service status:"
    
    Set-Location $ProjectRoot
    & $DockerCompose ps
    
    # Show health status
    Write-Host ""
    Write-Info "Health status:"
    try {
        & docker exec gecko-collector python -m gecko_terminal_collector.cli health-check 2>$null
    }
    catch {
        Write-Warning "Health check failed"
    }
}

# Show logs
function Show-Logs {
    Set-Location $ProjectRoot
    
    $service = "gecko-collector"
    $logArgs = @()
    
    if ($Follow) {
        $logArgs += "-f"
    }
    
    $logArgs += $service
    
    & $DockerCompose logs @logArgs
}

# Create backup
function New-Backup {
    if ($Arguments.Count -eq 0) {
        Write-Error "Backup path required. Usage: .\deploy.ps1 backup <backup_path>"
        exit 1
    }
    
    $backupPath = $Arguments[0]
    
    Write-Info "Creating backup at: $backupPath"
    
    & docker exec gecko-collector python -m gecko_terminal_collector.cli backup $backupPath --compress
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Backup failed"
        exit 1
    }
    
    Write-Success "Backup created successfully"
}

# Restore from backup
function Restore-Backup {
    if ($Arguments.Count -eq 0) {
        Write-Error "Backup path required. Usage: .\deploy.ps1 restore <backup_path>"
        exit 1
    }
    
    $backupPath = $Arguments[0]
    
    Write-Info "Restoring from backup: $backupPath"
    
    # Confirm restoration
    $confirmation = Read-Host "This will overwrite existing data. Are you sure? (y/N)"
    if ($confirmation -notmatch '^[Yy]$') {
        Write-Info "Restore cancelled"
        exit 0
    }
    
    & docker exec gecko-collector python -m gecko_terminal_collector.cli restore $backupPath --overwrite --verify
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Restore failed"
        exit 1
    }
    
    Write-Success "Restore completed successfully"
}

# Clean up old resources
function Remove-OldResources {
    Write-Info "Cleaning up old resources..."
    
    # Remove old containers
    & docker container prune -f
    
    # Remove old images
    & docker image prune -f
    
    # Remove old volumes (with confirmation)
    $confirmation = Read-Host "Remove unused volumes? This may delete data. (y/N)"
    if ($confirmation -match '^[Yy]$') {
        & docker volume prune -f
    }
    
    Write-Success "Cleanup completed"
}

# Check system health
function Test-Health {
    Write-Info "Checking system health..."
    
    # Check if container is running
    $runningContainers = & docker ps --format "table {{.Names}}" | Select-String "gecko-collector"
    if (!$runningContainers) {
        Write-Error "Collector container is not running"
        exit 1
    }
    
    # Run health check
    & docker exec gecko-collector python -m gecko_terminal_collector.cli health-check --json
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "System health check passed"
    }
    else {
        Write-Error "System health check failed"
        exit 1
    }
}

# Main execution
function Main {
    # Show help if requested
    if ($Help -or !$Command) {
        Show-Help
        exit 0
    }
    
    # Check prerequisites
    Test-Prerequisites
    
    # Load environment
    Import-Environment
    
    # Execute command
    switch ($Command.ToLower()) {
        "build" { Build-Image }
        "deploy" { 
            Build-Image
            Deploy-Application 
        }
        "start" { Start-Services }
        "stop" { Stop-Services }
        "restart" { Restart-Services }
        "status" { Show-Status }
        "logs" { Show-Logs }
        "backup" { New-Backup }
        "restore" { Restore-Backup }
        "cleanup" { Remove-OldResources }
        "health" { Test-Health }
        default {
            Write-Error "Unknown command: $Command"
            Show-Help
            exit 1
        }
    }
}

# Run main function
Main