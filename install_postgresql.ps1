# PostgreSQL Installation Script for Windows
# This script will download and install PostgreSQL

Write-Host "Installing PostgreSQL..." -ForegroundColor Green

# Check if Chocolatey is installed
if (!(Get-Command choco -ErrorAction SilentlyContinue)) {
    Write-Host "Chocolatey not found. Installing Chocolatey first..." -ForegroundColor Yellow
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
    iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
}

# Install PostgreSQL using Chocolatey
Write-Host "Installing PostgreSQL 15..." -ForegroundColor Green
choco install postgresql15 --params '/Password:12345678!' -y

# Add PostgreSQL to PATH
$pgPath = "C:\Program Files\PostgreSQL\15\bin"
$currentPath = [Environment]::GetEnvironmentVariable("PATH", "Machine")
if ($currentPath -notlike "*$pgPath*") {
    [Environment]::SetEnvironmentVariable("PATH", "$currentPath;$pgPath", "Machine")
    Write-Host "Added PostgreSQL to PATH" -ForegroundColor Green
}

Write-Host "PostgreSQL installation completed!" -ForegroundColor Green
Write-Host "Default superuser: postgres" -ForegroundColor Yellow
Write-Host "Default password: 12345678!" -ForegroundColor Yellow
Write-Host "Please restart your terminal to use PostgreSQL commands." -ForegroundColor Yellow