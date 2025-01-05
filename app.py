from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from models import *  # Ensure this is imported

migrate = Migrate(app, db)

