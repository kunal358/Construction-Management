import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Initialize the Flask application
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///construction.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'

UPLOAD_FOLDER = os.path.join(os.getcwd(), './static/uploaded_files')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)

# Database Models
class Category(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  name = db.Column(db.String(50), nullable=False, unique=True)
  type = db.Column(db.String(10), nullable=False)  # inflow or outflow

class Subcategory(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  name = db.Column(db.String(50), nullable=False)
  category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
  # Add this relationship
  category = db.relationship('Category', backref=db.backref('subcategories', lazy=True))

# Add this class to models.py (or equivalent)
class CustomerFile(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
  file_name = db.Column(db.String(255), nullable=False)  # Original name of the file
  file_path = db.Column(db.String(255), nullable=False)  # Path to the file in the local filesystem
  uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

  # Relationship back to the Customer
  customer = db.relationship('Customer', back_populates='files')

class Customer(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  full_name = db.Column(db.String(100), nullable=False)
  mobile_no = db.Column(db.String(20), nullable=False)
  occupation = db.Column(db.String(50))
  email_id = db.Column(db.String(50))
  address = db.Column(db.Text)
  files = db.relationship('CustomerFile', back_populates='customer', cascade='all, delete-orphan')

class WorkDetail(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
  date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
  category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
  subcategory_id = db.Column(db.Integer, db.ForeignKey('subcategory.id'), nullable=False)
  amount = db.Column(db.Float, nullable=False)
  method = db.Column(db.Text)
  description = db.Column(db.Text)

  category = db.relationship('Category', backref='work_details', lazy=True)
  subcategory = db.relationship('Subcategory', backref='work_details', lazy=True)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(50), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    method = db.Column(db.String(10), nullable=True)

__all__ = ['app', 'db', 'Customer', 'Category', 'Subcategory', 'CustomerFile', 'Customer', 'WorkDetail', 'Expense']
