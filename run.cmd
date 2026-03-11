cd /d DD:\DEVELOPMENT\ROOTECH\ocean_live
call .venv\Scripts\activate
python manage.py makemigrations
python manage.py migrate
python manage.py runserver 0.0.0.0:8005
