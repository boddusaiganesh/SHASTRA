@echo off
echo ===================================================
echo Committing and Pushing SHASTRA Bug Fixes
echo ===================================================
echo Checking git status...
git status
echo.
echo Adding changes...
git add .
echo.
echo Committing changes...
git commit -m "Fix SHASTRA full-stack bugs (database, routers, ML, and frontend services)"
echo.
echo Pushing to GitHub...
git push origin main
echo.
echo Git push completed!
pause
