#!/usr/bin/bash
echo "Checking Migrations....."
python3 manage.py makemigrations

echo "Applying Migratgions....."
python3 manage.py migrate

echo "Running Server...."
python3 manage.py runserver 0.0.0.0:8000 
