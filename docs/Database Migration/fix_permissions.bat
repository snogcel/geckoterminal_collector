@echo off
echo Fixing PostgreSQL permissions...
echo.

echo Running permission fix script...
psql -U postgres -h localhost -f fix_postgresql_permissions.sql

echo.
echo Permissions should now be fixed!
echo Testing connection as gecko_collector user...
psql -U gecko_collector -h localhost -d gecko_terminal_collector -c "SELECT current_user, current_database();"

echo.
pause