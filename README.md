# Blackfox website API

### Description
This is API for [Blackfox website](https://fayustovna.github.io/blackfox-nutrition-app/)

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
5. To create the database use command
```bash
python3 manage.py migrate
```
6. To create the superuser use command
```bash
python3 manage.py createsuperuser
```
7. To run the application use command
```bash
python3 manage.py runserver
```

### API Documentation
http://127.0.0.1:8000/redoc/

### Technology
[Python](https://www.python.org), [Django REST framework](https://www.django-rest-framework.org), [PostgreSQL](https://www.postgresql.org/), [Selenium](https://selenium-python.readthedocs.io/), [Docker](https://www.docker.com/), GitHub Actions

### Authors
[Evgeniy Golodnykh](https://github.com/Evgeniy-Golodnykh)  
[Constantine Nazarov](https://github.com/K1N88)

### CI/CD pipeline status
![Blackfox workflow](https://github.com/Evgeniy-Golodnykh/blackfox_backend/actions/workflows/blackfox_workflow.yml/badge.svg)
