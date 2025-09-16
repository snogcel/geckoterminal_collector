@echo off
echo Setting up PostgreSQL database for Gecko Terminal Collector...
echo.

echo Creating database and user...
psql -U postgres -h localhost -f setup_postgresql_database.sql

echo.
echo Database setup completed!
echo.
echo Connection details:
echo   Host: localhost
echo   Port: 5432
echo   Database: gecko_terminal_collector
echo   Username: gecko_collector
echo   Password: 12345678!
echo.
pause