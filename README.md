# Project Tracker

A lightweight task tracker inspired by Jira and Yandex Tracker.  
It allows you to create projects, manage tasks, assign users, and visualize progress with a Kanban board.  

[![Python](https://img.shields.io/badge/python-3.11-blue?logo=python)](https://www.python.org/)  
[![Django](https://img.shields.io/badge/Django-4.2-green?logo=django)](https://www.djangoproject.com/)  
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue?logo=postgresql)](https://www.postgresql.org/)  
[![Docker](https://img.shields.io/badge/Docker-✔-blue?logo=docker)](https://www.docker.com/)    

---

## Features
- Create and manage projects  
- Task creation with statuses and priorities  
- Kanban board for visual workflow management  
- User roles (admin, manager, contributor)  
- Search and filtering  
- Authentication & user profiles  
- REST API for integrations  

---

## Tech Stack
- **Backend:** Django, Django REST Framework  
- **Frontend:** Bootstrap, JavaScript, JQuery, AJAX
- **Database:** PostgreSQL  
- **Web server:** Nginx
- **Cache:** Redis
- **Containerization:** Docker, Docker Compose 
- **CI/CD:** GitHub Actions  
- **Testing:** pytest  

---

## Installation & Run

### Requirements
- Docker & Docker Compose  
- Git  

### Run with Docker
```bash
git clone https://github.com/username/project-tracker.git
cd project-tracker
docker-compose up --build -d
```
App will be available at:  
 http://localhost
 don't add :8000, this port is reserved  

### Local run (without Docker)
```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

---

## Project Structure
```
accounts/       
    templates/  
    static/     
taskboard/      
tracker/        
    templates/  
    static/     
requirements.txt
manage.py
docker/         
```

---

## API Example
```http
POST /api/tasks/
{
  "title": "Fix login bug",
  "project": 1,
  "assignee": 2,
  "status": "In Progress"
}
```

---

## TODO
- [ ] Replace id with uuid
- [ ] Add backlog 
- [ ] Handling Ajax errors with toast-notifications
- [ ] Make loading indicators 
- [ ] Decompose tracker module
- [ ] Make 'secrets' service