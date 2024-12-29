# BlackFox Nutrition API

### Description
This is API for [BlackFox Nutrition](https://www.blackfoxnutrition.ru) website

### Quick Start
1. Clone repo
```bash
git clone git@github.com:Evgeniy-Golodnykh/blackfox_backend.git
```
2. Creates the virtual environment
```bash
python3 -m venv venv
```
3. Activates the virtual environment
```bash
source venv/bin/activate
```
4. Upgrade PIP and install the requirements packages into the virtual environment
```bash
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```
5. Configure the .env file like this
```bash
ALLOWED_HOSTS=localhost
DJANGO_SECRET_KEY=django_secret_key
DB_ENGINE=django.db.backends.postgresql
DB_HOST=db
DB_PORT=5432
POSTGRES_DB=postgres_db
POSTGRES_USER=postgres_user
POSTGRES_PASSWORD=postgres_password
FATSECRET_CONSUMER_KEY=fatsecret_consumer_key
FATSECRET_CONSUMER_SECRET=fatsecret_consumer_secret
FATSECRET_CALLBACK_URL=https://fatsecret.callback.url
```
6. To create the database use command
```bash
python3 manage.py migrate
```
7. To create the superuser use command
```bash
python3 manage.py createsuperuser
```
8. To run the application use command
```bash
python3 manage.py runserver
```

### API Documentation
http://localhost:8000/api/swagger/  
http://localhost:8000/api/redoc/

### Technology
[Python](https://www.python.org), [Django REST framework](https://www.django-rest-framework.org), [FatSecret API](https://platform.fatsecret.com), [Django Crontab](https://pypi.org/project/django-crontab), [PostgreSQL](https://www.postgresql.org), [Docker](https://www.docker.com), [GitHub Actions](https://github.com/features/actions)

### Author
[Evgeniy Golodnykh](https://github.com/Evgeniy-Golodnykh)  

### CI/CD pipeline status
![Blackfox workflow](https://github.com/Evgeniy-Golodnykh/blackfox_backend/actions/workflows/blackfox_workflow.yml/badge.svg)
