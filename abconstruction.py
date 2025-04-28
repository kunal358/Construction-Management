import os
import sys
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from models import *
from sqlalchemy import desc, func
from datetime import datetime, timezone, timedelta
import pytz
from werkzeug.utils import secure_filename
from fpdf import FPDF

# Initialize Database
def setup_database():
  if not os.path.exists('./instance/construction.db'):
    with app.app_context():
      db.create_all()
      # Add MoneyFlow category as inflow
      new_category = Category(name="MoneyFlow", type="INFLOW")
      db.session.add(new_category)
      db.session.commit()
      # Get the category id for MoneyFlow
      tmpCat = Category.query.filter(func.lower(Category.name) == "moneyflow").first()
      if tmpCat:
        # New sub-category
        new_subcategory = Subcategory(name="Cash", category_id=tmpCat.id)
        db.session.add(new_subcategory)
        db.session.commit()
        new_subcategory = Subcategory(name="Bank", category_id=tmpCat.id)
        db.session.add(new_subcategory)
        db.session.commit()
      else:
        print("Category MoneyFlow not found")

@app.route('/customer/<int:customer_id>/work_details/<int:work_id>/edit', methods=['GET', 'POST'])
def edit_work_detail(customer_id, work_id):
  work = WorkDetail.query.get_or_404(work_id)
  categories = Category.query.all()
  subcategories = Subcategory.query.all()

  if request.method == 'POST':
    data = request.form.to_dict()
    work.date = datetime.strptime(data['date'], '%Y-%m-%d')
    work.category_id = int(data['category_id'])
    work.subcategory_id = int(data['subcategory_id'])
    work.amount = float(data['amount'])
    work.method = data.get('method')
    work.description = data.get('description')
    db.session.commit()
    flash('Work detail updated successfully!', 'success')
    return redirect(url_for('customer_work_details', id=customer_id))

  return render_template('edit_work_detail.html',
                         customer_id=customer_id,
                         work=work,
                         categories=categories,
                         subcategories=subcategories)

@app.route('/customer/<int:customer_id>/work_details/<int:work_id>/delete', methods=['POST'])
def delete_work_detail(customer_id, work_id):
  work = WorkDetail.query.get_or_404(work_id)
  db.session.delete(work)
  db.session.commit()
  flash('Work detail deleted successfully!', 'success')
  return redirect(url_for('customer_work_details', id=customer_id))

# Routes
@app.route('/')
def dashboard():
  try:
    total_outflow = (
        db.session.query(db.func.sum(WorkDetail.amount))
        .join(Category, WorkDetail.category_id == Category.id)  # Join with Category table
        .filter(Category.type.ilike('outflow'))                # Filter based on Category type
        .scalar() or 0
    )
    total_inflow = (
        db.session.query(db.func.sum(WorkDetail.amount))
        .join(Category, WorkDetail.category_id == Category.id)  # Join with Category table
        .filter(Category.type.ilike('inflow'))                # Filter based on Category type
        .scalar() or 0
    )
    total_inflow_cash = (
        db.session.query(db.func.sum(WorkDetail.amount))
        .join(Category, WorkDetail.category_id == Category.id)
        .join(Subcategory, WorkDetail.subcategory_id == Subcategory.id)
        .filter(Category.type.ilike('inflow'),
                Subcategory.name.ilike('cash'))
        .scalar() or 0
    )
    total_inflow_bank = (
        db.session.query(db.func.sum(WorkDetail.amount))
        .join(Category, WorkDetail.category_id == Category.id)
        .join(Subcategory, WorkDetail.subcategory_id == Subcategory.id)
        .filter(Category.type.ilike('inflow'),
                Subcategory.name.ilike('bank'))
        .scalar() or 0
    )
    total_outflow_cash = (
        db.session.query(db.func.sum(WorkDetail.amount))
        .join(Category, WorkDetail.category_id == Category.id)
        .filter(Category.type.ilike('outflow'),
                WorkDetail.method.ilike('cash'))
        .scalar() or 0
    )
    total_outflow_bank = (
        db.session.query(db.func.sum(WorkDetail.amount))
        .join(Category, WorkDetail.category_id == Category.id)
        .filter(Category.type.ilike('outflow'),
                WorkDetail.method.ilike('bank'))
        .scalar() or 0
    )

    total_internal_exp = (db.session.query(db.func.sum(Expense.amount))
                     .filter(~Expense.method.ilike('None'))
                     .scalar() or 0
                    )
    total_internal_exp_cash = (db.session.query(db.func.sum(Expense.amount))
                     .filter(Expense.method.ilike('cash'))
                     .scalar() or 0
                    )
    total_internal_exp_bank = (db.session.query(db.func.sum(Expense.amount))
                     .filter(Expense.method.ilike('bank'))
                     .scalar() or 0
                    )

    total_withdraw_cash = (db.session.query(db.func.sum(Expense.amount))
                     .filter(Expense.category.ilike('Withdraw_Cash'))
                     .scalar() or 0
                    )
    total_deposit_cash = (db.session.query(db.func.sum(Expense.amount))
                     .filter(Expense.category.ilike('Deposit_Cash'))
                     .scalar() or 0
                    )

    #Cash in hand
    cash_in_hand = total_inflow_cash + total_withdraw_cash - total_outflow_cash - total_internal_exp_cash - total_deposit_cash
    bank_balance = total_inflow_bank + total_deposit_cash - total_outflow_bank - total_internal_exp_bank - total_withdraw_cash

    profit = total_inflow - total_outflow - total_internal_exp

    if total_inflow != (total_inflow_cash + total_inflow_bank):
      raise ValueError(f"Total money recieved does not match")

    if total_outflow != (total_outflow_cash + total_outflow_bank):
      raise ValueError(f"Total money spent does not match")

    if total_internal_exp != (total_internal_exp_cash + total_internal_exp_bank):
      raise ValueError(f"Total internal expense does not match")

    if profit != (cash_in_hand + bank_balance):
      raise ValueError(f"Total profit does not match")

  except Exception as e:
    print(f"Error calculating total: {e}")
    sys.exit(1)

  # Handle customer search
  search_query = request.args.get('search', '').strip()
  search_results = []
  if search_query:
    search_results = Customer.query.filter(Customer.full_name.ilike(f"%{search_query}%")).all()

  return render_template(
      'dashboard.html',
      total_inflow=total_inflow,
      total_outflow=total_outflow,
      total_inflow_cash=total_inflow_cash,
      total_inflow_bank=total_inflow_bank,
      total_outflow_cash=total_outflow_cash,
      total_outflow_bank=total_outflow_bank,
      total_internal_exp=total_internal_exp,
      total_internal_exp_cash=total_internal_exp_cash,
      total_internal_exp_bank=total_internal_exp_bank,
      total_withdraw_cash=total_withdraw_cash,
      total_deposit_cash=total_deposit_cash,
      cash_in_hand=cash_in_hand,
      bank_balance=bank_balance,
      profit=profit,
      search_results=search_results,
      search_query=search_query
  )

@app.route('/categories', methods=['GET', 'POST'])
def manage_categories():
  if request.method == 'POST':
    if 'name' in request.form and 'type' in request.form:
      name = request.form.get('name').strip()
      category_type = request.form.get('type').strip().upper()

      # Check for duplicate category
      existing_category = Category.query.filter(func.lower(Category.name) == name.lower()).first()
      if existing_category:
          flash('Category already exists!', 'danger')
      elif name:
          new_category = Category(name=name, type=category_type)
          db.session.add(new_category)
          db.session.commit()
          flash('Category added successfully!', 'success')

    if 'subcategory_name' in request.form and 'category_id' in request.form:
      subcategory_name = request.form.get('subcategory_name').strip()
      category_id = request.form.get('category_id')

      # Check for duplicate subcategory
      existing_subcategory = Subcategory.query.filter(
             func.lower(Subcategory.name) == subcategory_name.lower(),
                        Subcategory.category_id == category_id).first()
      if existing_subcategory:
          flash('Subcategory already exists under this category!', 'danger')
      elif subcategory_name and category_id:
          new_subcategory = Subcategory(name=subcategory_name, category_id=category_id)
          db.session.add(new_subcategory)
          db.session.commit()
          flash('Subcategory added successfully!', 'success')

  # Query categories and their subcategories
  categories = Category.query.all()
  subcategories = Subcategory.query.all()

  return render_template('categories.html', categories=categories, subcategories=subcategories)

@app.route('/customers', methods=['GET', 'POST'])
def manage_customers():
  if request.method == 'POST':
    customers = Customer.query.all()

    data = request.form.to_dict()

    full_name = request.form['full_name']
    mobile_no = request.form['mobile_no']

    # Check for duplicate name and mobile number
    existing_customer = Customer.query.filter_by(full_name=full_name, mobile_no=mobile_no).first()
    if existing_customer:
        return render_template('customers.html', customers=customers, error_message="Customer with this name and mobile number already exists.")

    new_customer = Customer(
        full_name=data['full_name'],
        mobile_no=data['mobile_no'],
        occupation=data.get('occupation'),
        email_id=data.get('email_id'),
        address=f"{data.get('street', '')}, {data.get('city', '')}, {data.get('state', '')}, {data.get('pincode', '')}"
    )
    db.session.add(new_customer)
    db.session.commit()
    flash('Customer added successfully!', 'success')

  customers = Customer.query.all()
  if not customers:
      flash('No customers found!', 'warning')
  return render_template('customers.html', customers=customers)

@app.route('/customer/<int:id>/work_details', methods=['GET', 'POST'])
def customer_work_details(id):
  customer = Customer.query.get_or_404(id)
  categories = Category.query.all()

  # Summarize inflow, outflow, and profit
  inflow_total = 0
  outflow_total = 0
  profit = 0
  try:
    #Outflow
    outflow_total = (
        db.session.query(db.func.sum(WorkDetail.amount))
        .join(Category, WorkDetail.category_id == Category.id)
        .filter(Category.type.ilike('outflow'), WorkDetail.customer_id == id)
        .scalar() or 0
    )
    outflow_cash = (
        db.session.query(db.func.sum(WorkDetail.amount))
        .join(Category, WorkDetail.category_id == Category.id)
        .filter(Category.type.ilike('outflow'), WorkDetail.customer_id == id,
               WorkDetail.method.ilike('cash'))
        .scalar() or 0
    )
    outflow_bank = (
        db.session.query(db.func.sum(WorkDetail.amount))
        .join(Category, WorkDetail.category_id == Category.id)
        .filter(Category.type.ilike('outflow'), WorkDetail.customer_id == id,
                WorkDetail.method.ilike('bank'))
        .scalar() or 0
    )

    #Inflow
    inflow_total = (
        db.session.query(db.func.sum(WorkDetail.amount))
        .join(Category, WorkDetail.category_id == Category.id)
        .filter(Category.type.ilike('inflow'), WorkDetail.customer_id == id)
        .scalar() or 0
    )
    inflow_cash = (
        db.session.query(db.func.sum(WorkDetail.amount))
        .join(Category, WorkDetail.category_id == Category.id)
        .join(Subcategory, WorkDetail.subcategory_id == Subcategory.id)
        .filter(Category.type.ilike('inflow'),
                WorkDetail.customer_id == id,
                Subcategory.name.ilike('cash'))
        .scalar() or 0
    )
    inflow_bank = (
        db.session.query(db.func.sum(WorkDetail.amount))
        .join(Category, WorkDetail.category_id == Category.id)
        .join(Subcategory, WorkDetail.subcategory_id == Subcategory.id)
        .filter(Category.type.ilike('inflow'),
                WorkDetail.customer_id == id,
                Subcategory.name.ilike('bank'))
        .scalar() or 0
    )

    #print(f"Inflow_cash: {inflow_cash}")
    #print(f"Inflow_bank: {inflow_bank}")
    #print(f"Inflow_total: {inflow_total}")
    if inflow_total != (inflow_cash + inflow_bank):
      raise ValueError(f"Total money recieved does not match")

    if outflow_total != (outflow_cash + outflow_bank):
      raise ValueError(f"Total money spent does not match")

    profit = inflow_total - outflow_total
  except Exception as e:
    print(f"Error calculating total: {e}")

  # Category summary
  category_summary = db.session.query(
      Category.id,
      Category.name,
      db.func.sum(WorkDetail.amount)
  ).join(WorkDetail, WorkDetail.category_id == Category.id)\
  .filter(WorkDetail.customer_id == id)\
  .group_by(Category.id, Category.name).all()

  # Get all work records (for a specific category if selected)
  selected_category_id = request.args.get('category_id', type=int)
  if selected_category_id:
      work_records_query = WorkDetail.query.filter_by(customer_id=id, category_id=selected_category_id).order_by(desc(WorkDetail.date)).all()
  else:
      work_records_query = WorkDetail.query.filter_by(customer_id=id).order_by(desc(WorkDetail.date)).all()

  # Serialize work records for use in the template
  work_records = [
      {
          'id': record.id,
          'date': record.date.strftime('%d-%m-%Y'),
          'category': Category.query.get(record.category_id).name,
          'subcategory': Subcategory.query.get(record.subcategory_id).name if record.subcategory_id else None,
          'amount': record.amount,
          'method': record.method,
          'description': record.description,
      }
      for record in work_records_query
  ]

  if selected_category_id:
    total_amount = sum(record.amount for record in work_records_query)
  else:
    total_amount = 0

  # Handle adding new work details
  if request.method == 'POST':
      data = request.form.to_dict()
      category_id = int(data['category_id'])
      selected_category = Category.query.get(category_id)

      if not selected_category:
          flash('Invalid category selected!', 'danger')
          return redirect(url_for('customer_work_details', id=id))

      new_work = WorkDetail(
          customer_id=id,
          date=datetime.strptime(data['date'], '%Y-%m-%d'),
          category_id=data['category_id'],
          subcategory_id=data.get('subcategory_id'),
          amount=float(data['amount']),
          method=data.get('method'),
          description=data.get('description'),
      )
      db.session.add(new_work)
      db.session.commit()
      flash('Work detail added successfully!', 'success')
      return redirect(url_for('customer_work_details', id=id))

  return render_template(
      'work_details.html',
      customer=customer,
      categories=categories,
      category_summary=category_summary,
      work_records=work_records,
      total_amount=total_amount,
      inflow_total=inflow_total,
      inflow_cash=inflow_cash,
      inflow_bank=inflow_bank,
      outflow_total=outflow_total,
      outflow_cash=outflow_cash,
      outflow_bank=outflow_bank,
      profit=profit,
      selected_category_id=selected_category_id
  )

@app.route('/customer/<int:id>/update', methods=['POST'])
def customer_update(id):
    try:
        customer = Customer.query.get_or_404(id)
        data = request.form
        customer.construction_size = data.get('home_construction_area', customer.construction_size)
        customer.rate_of_construction = data.get('home_construction_rate', customer.rate_of_construction)
        customer.wall_compound_size = data.get('wall_compound_area', customer.wall_compound_size)
        customer.rate_of_wall_compound = data.get('wall_compound_rate', customer.rate_of_wall_compound)
        db.session.commit()
        flash("Customer details updated successfully!", "success")
    except Exception as e:
        flash(f"Error updating customer details: {e}", "danger")

    return redirect(url_for('customer_work_details', id=id))
  

@app.route('/is_category_inflow/<int:category_id>')
def is_category_inflow(category_id):
  category = Category.query.filter_by(id=category_id).first()  # Fetch single category
  is_moneyflow = category.name.lower() == 'moneyflow'  # Check for 'moneyflow' type (case-insensitive)
  
  if is_moneyflow:
    # Hide method (return empty list or None)
    method_options = [
      {'value': 'NONE', 'label': 'NONE'},
    ]  # Empty list for hidden method
  else:
    # Show method options
    method_options = [  # Replace with your actual method data
      {'value': 'CASH', 'label': 'Cash'},
      {'value': 'BANK', 'label': 'Bank'},
      # ... other methods
    ]
  
  return jsonify({
    'is_moneyflow': is_moneyflow,
    'method_options': method_options,
  })

@app.route('/get_subcat_work_detail/<int:category_id>')
def get_subcat_work_detail(category_id):
    subcategories = Subcategory.query.filter_by(category_id=category_id).all()
    return jsonify([{'id': subcategory.id, 'name': subcategory.name} for subcategory in subcategories])

@app.route('/categories/<int:category_id>/subcategories')
def get_subcategories(category_id):
    subcategories = Subcategory.query.filter_by(category_id=category_id).all()
    subcategory_list = [{"id": sub.id, "name": sub.name} for sub in subcategories]
    return jsonify({"subcategories": subcategory_list})

@app.route('/categories/edit/<int:id>', methods=['POST'])
def edit_category(id):
    category = Category.query.get_or_404(id)
    category.name = request.form['name']
    db.session.commit()
    return jsonify({'message': 'Category updated successfully!'})

@app.route('/categories/delete/<int:id>', methods=['POST'])
def delete_category(id):
    category = Category.query.get_or_404(id)
    db.session.delete(category)
    db.session.commit()
    return jsonify({'message': 'Category deleted successfully!'})

@app.route('/subcategories/edit/<int:id>', methods=['POST'])
def edit_subcategory(id):
    subcategory = Subcategory.query.get_or_404(id)
    subcategory.name = request.form['name']
    subcategory.category_id = request.form['category_id']
    db.session.commit()
    return jsonify({'message': 'Subcategory updated successfully!'})

@app.route('/subcategories/delete/<int:id>', methods=['POST'])
def delete_subcategory(id):
    subcategory = Subcategory.query.get_or_404(id)
    db.session.delete(subcategory)
    db.session.commit()
    return jsonify({'message': 'Subcategory deleted successfully!'})

@app.route('/export/<string:file_type>')
def export_data(file_type):
    data = WorkDetail.query.all()
    if file_type == 'excel':
        df = pd.DataFrame([{column.name: getattr(record, column.name) for column in WorkDetail.__table__.columns} for record in data])
        df.to_excel('work_details.xlsx', index=False)
        return jsonify({'message': 'Exported to Excel successfully.'})
    elif file_type == 'pdf':
        # Add PDF export logic here
        return jsonify({'message': 'Exported to PDF successfully.'})

def load_expense_categories_from_file(filepath='./instance/expense_categories.txt'):
    expense_categories = []
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            for line in file:
                if line.strip():  # skip empty lines
                    parts = line.strip().split(',', 1)
                    if len(parts) == 2:
                        value, label = parts
                        expense_categories.append({"value": value, "label": label})
    except Exception as e:
        print(f"Error loading expense categories: {e}")
    return expense_categories

@app.route('/get_expense_categories')
def get_expense_categories():
#  expense_categories = [
#      {"value": "Fuel", "label": "Disel/Petrol cost"},
#      {"value": "Salary", "label": "Salary Distribution"},
#      {"value": "Tax", "label": "Tax Payment"},
#      {"value": "Withdraw_Cash", "label": "Withdraw cash from Bank"},
#      {"value": "Deposit_Cash", "label": "Deposit cash into Bank"}
#  ]
#  return jsonify(expense_categories)
  categories = load_expense_categories_from_file()
  return jsonify(categories)

@app.route('/get_expense_method/<string:expense_category>')
def get_expense_method(expense_category):
  is_moneyflow = expense_category.strip().lower() == 'withdraw_cash'

  if not is_moneyflow:
    is_moneyflow = expense_category.strip().lower() == 'deposit_cash'
  
  if is_moneyflow:
    method_options = [
      {'value': 'NONE', 'label': 'NONE'},
    ]  # Empty list for hidden method
  else:
    method_options = [  # Replace with your actual method data
      {'value': 'CASH', 'label': 'Cash'},
      {'value': 'BANK', 'label': 'Bank'},
      # ... other methods
    ]
  
  return jsonify({
    'method_options': method_options,
  })

@app.route('/company_expenses', methods=['GET', 'POST'])
def manage_expenses():
    customers = Customer.query.all()
    categories = Category.query.all()
    if request.method == 'POST':
        date = request.form.get('date')
        category = request.form.get('category')
        description = request.form.get('description')
        amount = float(request.form.get('amount'))
        method = request.form.get('method')
        expense = Expense(date=datetime.strptime(date, '%Y-%m-%d'), category=category, description=description, amount=amount, method=method)
        db.session.add(expense)
        db.session.commit()
        flash('Expense added successfully!', 'success')
        return redirect(url_for('manage_expenses'))
    
    expenses = Expense.query.order_by(desc(Expense.date)).all()
    summary = db.session.query(
        Expense.category, db.func.sum(Expense.amount)
    ).group_by(Expense.category).all()

    total_outflow = (db.session.query(db.func.sum(Expense.amount))
                     .filter(~Expense.method.ilike('None'))
                     .scalar() or 0
                    )

    return render_template('company_expenses.html', expenses=expenses, summary=summary, total_outflow=total_outflow, customers=customers, categories=categories)

@app.route('/delete_expense/<int:expense_id>', methods=['POST'])
def delete_expense(expense_id):
    try:
        expense = Expense.query.get_or_404(expense_id)
        db.session.delete(expense)
        db.session.commit()
        flash('Expense deleted successfully!', 'success')
    except Exception as e:
        print(f"Error deleting expense: {e}")
        flash('An error occurred while deleting the expense.', 'danger')
    return redirect(url_for('manage_expenses'))

@app.route('/export_work_details/<int:customer_id>', methods=['GET'])
def export_work_details(customer_id):
    try:
        # Fetch customer details
        customer = Customer.query.get(customer_id)
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404

        # Fetch and sort work details by date
        data = WorkDetail.query.filter_by(customer_id=customer_id).order_by(desc(WorkDetail.date)).all()
        if not data:
            return jsonify({'error': 'No work details found for this customer'}), 404

        # Generate the IST timestamp
        ist_offset = timedelta(hours=5, minutes=30)
        ist_now = datetime.now(timezone.utc) + ist_offset
        report_generated_at = ist_now.strftime("%d-%m-%Y %H:%M:%S")  # Format: DD-MM-YYYY HH:MM:SS

        # Create a PDF object
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", style="B", size=14)

        # Add customer information
        pdf.cell(0, 10, f"AB Construction - Customer Report", 0, 1, 'C')

        pdf.set_font("Arial", size=12)

        # Add customer information
        pdf.cell(0, 10, f"Customer Name: {customer.full_name},  Mobile No: {customer.mobile_no}, Email: {customer.email_id or 'N/A'}", 0, 1, 'L')
        pdf.cell(0, 10, f"Address: {customer.address or 'N/A'}", 0, 1, 'L')
        pdf.ln(10)

        #Outflow
        outflow_total = (
            db.session.query(db.func.sum(WorkDetail.amount))
            .join(Category, WorkDetail.category_id == Category.id)
            .filter(Category.type.ilike('outflow'), WorkDetail.customer_id == customer_id)
            .scalar() or 0
        )
        outflow_cash = (
            db.session.query(db.func.sum(WorkDetail.amount))
            .join(Category, WorkDetail.category_id == Category.id)
            .filter(Category.type.ilike('outflow'), WorkDetail.customer_id == customer_id,
                   WorkDetail.method.ilike('cash'))
            .scalar() or 0
        )
        outflow_bank = (
            db.session.query(db.func.sum(WorkDetail.amount))
            .join(Category, WorkDetail.category_id == Category.id)
            .filter(Category.type.ilike('outflow'), WorkDetail.customer_id == customer_id,
                    WorkDetail.method.ilike('bank'))
            .scalar() or 0
        )

        #Inflow
        inflow_total = (
            db.session.query(db.func.sum(WorkDetail.amount))
            .join(Category, WorkDetail.category_id == Category.id)
            .filter(Category.type.ilike('inflow'), WorkDetail.customer_id == customer_id)
            .scalar() or 0
        )
        inflow_cash = (
            db.session.query(db.func.sum(WorkDetail.amount))
            .join(Category, WorkDetail.category_id == Category.id)
            .join(Subcategory, WorkDetail.subcategory_id == Subcategory.id)
            .filter(Category.type.ilike('inflow'), WorkDetail.customer_id == customer_id,
                    Subcategory.name.ilike('cash'))
            .scalar() or 0
        )
        inflow_bank = (
            db.session.query(db.func.sum(WorkDetail.amount))
            .join(Category, WorkDetail.category_id == Category.id)
            .join(Subcategory, WorkDetail.subcategory_id == Subcategory.id)
            .filter(Category.type.ilike('inflow'), WorkDetail.customer_id == customer_id,
                    Subcategory.name.ilike('bank'))
            .scalar() or 0
        )

        profit = inflow_total - outflow_total
        # Add summary
        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(0, 10, f"Overall Summary", 0, 1, 'L')

        # Add table headers
        headers = ["Source", "Inflow Amount", "Outflow Amount", "Remaining"]
        col_widths = [25, 40, 40, 30]  # Adjusted column widths
        for i, header in enumerate(headers):
            pdf.cell(col_widths[i], 10, header, 1, 0, 'L')
        pdf.ln(10)

        pdf.cell(col_widths[0], 10, "Cash", 1, 0, 'L')
        pdf.set_font("Arial", size=12)
        pdf.cell(col_widths[1], 10, f"{inflow_cash:.2f}", 1, 0, 'L')
        pdf.cell(col_widths[2], 10, f"{outflow_cash:.2f}", 1, 0, 'L')
        pdf.cell(col_widths[3], 10, f"{(inflow_cash - outflow_cash):.2f}", 1, 0, 'L')
        pdf.ln(10)
        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(col_widths[0], 10, "Bank", 1, 0, 'L')
        pdf.set_font("Arial", size=12)
        pdf.cell(col_widths[1], 10, f"{inflow_bank:.2f}", 1, 0, 'L')
        pdf.cell(col_widths[2], 10, f"{outflow_bank:.2f}", 1, 0, 'L')
        pdf.cell(col_widths[3], 10, f"{(inflow_bank - outflow_bank):.2f}", 1, 0, 'L')
        pdf.ln(10)
        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(col_widths[0], 10, "Total", 1, 0, 'L')
        pdf.set_font("Arial", size=12)
        pdf.cell(col_widths[1], 10, f"{inflow_total:.2f}", 1, 0, 'L')
        pdf.cell(col_widths[2], 10, f"{outflow_total:.2f}", 1, 0, 'L')
        pdf.cell(col_widths[3], 10, f"{(inflow_total - outflow_total):.2f}", 1, 0, 'L')
        pdf.ln(10)

        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(0, 10, f"Overall Profit: {profit}", 0, 1, 'L')
        pdf.set_font("Arial", size=12)

        #Inflow details
        pdf.ln(10)
        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(0, 10, f"Inflow details", 0, 1, 'L')
        pdf.set_font("Arial", size=12)
        # Add table headers
        headers = ["Date", "Category", "Subcategory", "Amount", "Method", "Description"]
        col_widths = [30, 30, 30, 25, 25, 50]  # Adjusted column widths
        for i, header in enumerate(headers):
            pdf.cell(col_widths[i], 10, header, 1, 0, 'L')
        pdf.ln(10)

        # Add data rows
        data = (WorkDetail.query
               .join(Category, WorkDetail.category_id == Category.id)
               .filter(WorkDetail.customer_id == customer_id, 
                          Category.type.ilike('inflow'))
               .order_by(desc(WorkDetail.date)).all())

        for detail in data:
            pdf.cell(col_widths[0], 10, detail.date.strftime('%d-%m-%Y') if detail.date else '', 1, 0, 'L')
            pdf.cell(col_widths[1], 10, detail.category.name if detail.category else '', 1, 0, 'L')
            pdf.cell(col_widths[2], 10, detail.subcategory.name if detail.subcategory else '', 1, 0, 'L')
            pdf.cell(col_widths[3], 10, f"{detail.amount:.2f}", 1, 0, 'L')
            pdf.cell(col_widths[4], 10, detail.method if detail.method else '', 1, 0, 'L')
            truncated_description = (detail.description or '')[:30] + ('...' if len(detail.description or '') > 30 else '')
            pdf.cell(col_widths[5], 10, truncated_description, 1, 0, 'L')
            pdf.ln(10)

        #outflow details
        pdf.ln(10)
        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(0, 10, f"Outflow details", 0, 1, 'L')
        pdf.set_font("Arial", size=12)
        # Add table headers
        headers = ["Date", "Category", "Subcategory", "Amount", "Method", "Description"]
        col_widths = [30, 30, 30, 25, 25, 50]  # Adjusted column widths
        for i, header in enumerate(headers):
            pdf.cell(col_widths[i], 10, header, 1, 0, 'L')
        pdf.ln(10)

        # Add data rows
        data = (WorkDetail.query
               .join(Category, WorkDetail.category_id == Category.id)
               .filter(WorkDetail.customer_id == customer_id, 
                          Category.type.ilike('outflow'))
               .order_by(desc(WorkDetail.date)).all())

        for detail in data:
            pdf.cell(col_widths[0], 10, detail.date.strftime('%d-%m-%Y') if detail.date else '', 1, 0, 'L')
            pdf.cell(col_widths[1], 10, detail.category.name if detail.category else '', 1, 0, 'L')
            pdf.cell(col_widths[2], 10, detail.subcategory.name if detail.subcategory else '', 1, 0, 'L')
            pdf.cell(col_widths[3], 10, f"{detail.amount:.2f}", 1, 0, 'L')
            pdf.cell(col_widths[4], 10, detail.method if detail.method else '', 1, 0, 'L')
            truncated_description = (detail.description or '')[:30] + ('...' if len(detail.description or '') > 30 else '')
            pdf.cell(col_widths[5], 10, truncated_description, 1, 0, 'L')
            pdf.ln(10)

        pdf.cell(200, 10, txt=f"Report generated at: {report_generated_at}", ln=True, align='R')
        pdf.ln(10)

        # Output PDF content and ensure it is bytes
        pdf_data = bytes(pdf.output(dest='S'))  # Convert bytearray to bytes
        response = Response(pdf_data, mimetype='application/pdf')
        response.headers['Content-Disposition'] = f'attachment;filename={customer.full_name}_{customer.mobile_no}_Record.pdf'
        return response

    except Exception as e:
        print(f"Error exporting work details: {e}")
        return jsonify({'error': 'Failed to export work details'}), 500

@app.route('/export_work_subcat_details/<int:customer_id>/<int:category_id>/<int:subcategory_id>', methods=['GET'])
def export_work_subcat_details(customer_id, category_id, subcategory_id):
    try:
        # Fetch customer details
        customer = Customer.query.get(customer_id)
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404

        # Fetch and sort work details by date
        data = WorkDetail.query.filter_by(customer_id=customer_id, category_id=category_id, subcategory_id=subcategory_id).order_by(desc(WorkDetail.date)).all()
        if not data:
            return jsonify({'error': 'No record found for this customer'}), 404

        # Generate the IST timestamp
        ist_offset = timedelta(hours=5, minutes=30)
        ist_now = datetime.now(timezone.utc) + ist_offset
        report_generated_at = ist_now.strftime("%d-%m-%Y %H:%M:%S")  # Format: DD-MM-YYYY HH:MM:SS

        # Create a PDF object
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", style="B", size=14)

        # Add customer information
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, "AB Construction Report", 0, 1, 'C')
        pdf.ln(10)

        pdf.set_font("Arial", size=12)
        # Add customer information
        pdf.cell(0, 10, f"Customer Name: {customer.full_name},  Mobile No: {customer.mobile_no}, Email: {customer.email_id or 'N/A'}", 0, 1, 'L')
        pdf.cell(0, 10, f"Address: {customer.address or 'N/A'}", 0, 1, 'L')
        pdf.ln(10)

        # Add summary
        pdf.set_font("Arial", style="B", size=12)
        if data:  # Check if there are any records
            # Print the header once using the first record's category and subcategory
            pdf.cell(0, 10, f"Records for {data[0].category.name} - {data[0].subcategory.name}", ln=True, align="C")

        pdf.set_font("Arial", size=12)
        total_amount = 0
        col_widths = [30, 40, 30, 50]  # Adjusted column widths
        for detail in data:
            pdf.cell(col_widths[0], 10, detail.date.strftime('%d-%m-%Y') if detail.date else '', 1, 0, 'L')
            pdf.cell(col_widths[1], 10, f"{detail.amount:.2f}", 1, 0, 'L')
            pdf.cell(col_widths[2], 10, detail.method if detail.method else '', 1, 0, 'L')
            truncated_description = (detail.description or '')[:30] + ('...' if len(detail.description or '') > 30 else '')
            pdf.cell(col_widths[3], 10, truncated_description, 1, 0, 'L')
            pdf.ln(10)
            total_amount += detail.amount

        pdf.ln(10)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, f"Total Amount: {total_amount:.2f}", ln=True, align="R")

        # Output PDF content and ensure it is bytes
        pdf_data = bytes(pdf.output(dest='S'))  # Convert bytearray to bytes
        response = Response(pdf_data, mimetype='application/pdf')
        response.headers['Content-Disposition'] = f'attachment;filename={customer.full_name}_{customer.mobile_no}_Record.pdf'
        return response

    except Exception as e:
        print(f"Error exporting subcat work details: {e}")
        return jsonify({'error': 'Failed to export subcat work details'}), 500

# Define allowed extensions
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}

# Convert UTC to IST
def utc_to_ist(utc_time):
  ist = pytz.timezone('Asia/Kolkata')
  return utc_time.replace(tzinfo=pytz.utc).astimezone(ist)

def allowed_file(filename):
    """Check if the file has one of the allowed extensions."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload_customer_file', methods=['POST'])
def upload_customer_file():
    cust_id = request.form.get('customer_id')
    files = request.files.getlist('file')

    # Validate files
    valid_files = [file for file in files if file and allowed_file(file.filename)]
    if not valid_files:
        return jsonify({'error': 'No valid file selected or invalid file type'}), 400


    customer_dir = os.path.join(app.config['UPLOAD_FOLDER'], f'customer_{cust_id}')
    os.makedirs(customer_dir, exist_ok=True)
    clean_customer_files(cust_id)
    custFiles = CustomerFile.query.filter_by(customer_id=cust_id).all()
    uploaded_files = []
    for file in valid_files:
        filename = secure_filename(file.filename)
        # Handle duplicate file names
        filepath = os.path.join(customer_dir, filename)
        version = 1
        while os.path.exists(filepath):
            filename = f"{os.path.splitext(file.filename)[0]}_v{version}{os.path.splitext(file.filename)[1]}"
            filepath = os.path.join(customer_dir, filename)
            version += 1

        file.save(filepath)
        uploaded_files.append(filename)
        newFile = CustomerFile(
                    customer_id=cust_id,
                    file_name=filename,
                    file_path=filepath
                    )
        db.session.add(newFile)
        db.session.commit()

    return jsonify({'success': 'File(s) uploaded successfully', 'files': uploaded_files}), 200

@app.route('/get_customer_files/<int:cust_id>', methods=['GET'])
def get_customer_files(cust_id):
    custFiles = CustomerFile.query.filter_by(customer_id=cust_id).order_by(CustomerFile.uploaded_at.desc()).all()
    files = [
        {"id": f.id, "name": f.file_name, "path": f.file_path,
         "uploaded_at": utc_to_ist(f.uploaded_at).strftime('%d-%m-%Y %H:%M:%S')}
        for f in custFiles
    ]
    return jsonify({"files": files}), 200

def clean_customer_files(customer_id):
    customer_dir = os.path.join(app.config['UPLOAD_FOLDER'], f'customer_{customer_id}')
    
    # Ensure the directory exists
    if not os.path.exists(customer_dir):
        return

    # Get files from the directory
    directory_files = set(os.listdir(customer_dir))
    
    # Get files from the database
    db_files = set(f.file_name for f in CustomerFile.query.filter_by(customer_id=customer_id).all())

    # Identify untracked files
    untracked_files = directory_files - db_files

    # Delete untracked files
    for file in untracked_files:
        os.remove(os.path.join(customer_dir, file))

@app.route('/categories/<int:subcategory_id>/export_pdf', methods=['GET'])
def export_subcategory_pdf(subcategory_id):
    # Fetch records for the sub-category, sorted by descending date
    work_details = (db.session.query(WorkDetail)
      .filter(WorkDetail.subcategory_id == subcategory_id)
      .order_by(WorkDetail.date.desc())
      .all()
    )

    subCat = (db.session.query(Subcategory)
      .filter(Subcategory.id == subcategory_id)
      .first()
    )

    # Generate the IST timestamp
    ist_offset = timedelta(hours=5, minutes=30)
    ist_now = datetime.now(timezone.utc) + ist_offset
    report_generated_at = ist_now.strftime("%d-%m-%Y %H:%M:%S")  # Format: DD-MM-YYYY HH:MM:SS

    # Create a PDF
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Title
    pdf.set_font("Arial", style="B", size=16)
    pdf.cell(0, 10, f"AB Construction Report", 0, 1, 'C')
    pdf.cell(200, 10, f"Records for {subCat.name}", ln=True, align="C")
    pdf.ln(10)

    # Add table headers
    pdf.set_font("Arial", style="B", size=12)
    pdf.cell(40, 10, "Customer Name", border=1, align="C")
    pdf.cell(30, 10, "Date", border=1, align="C")
    pdf.cell(30, 10, "Amount", border=1, align="C")
    pdf.cell(30, 10, "Method", border=1, align="C")
    pdf.cell(50, 10, "Description", border=1, align="C")
    pdf.ln()

    # Add table rows
    pdf.set_font("Arial", size=12)
    for record in work_details:
        cust = (db.session.query(Customer)
          .filter(Customer.id == record.customer_id)
          .first()
        )
        pdf.cell(40, 10, cust.full_name, border=1)
        pdf.cell(30, 10, record.date.strftime('%d-%m-%Y'), border=1)
        pdf.cell(30, 10, f"{record.amount:.2f}", border=1)
        pdf.cell(30, 10, record.method or "N/A", border=1)
        pdf.cell(50, 10, record.description or "N/A", border=1)
        pdf.ln()

    # Footer
    pdf.ln(10)
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 10, txt=f"Report generated at: {report_generated_at}", ln=True, align='R')
    pdf.ln(10)

    # Output PDF content and ensure it is bytes
    pdf_data = bytes(pdf.output(dest='S'))  # Convert bytearray to bytes
    response = Response(pdf_data, mimetype='application/pdf')
    response.headers['Content-Disposition'] = f'attachment;filename=Report_{subCat.name}.pdf'
    return response

@app.route('/company_expense_work_details', methods=['GET', 'POST'])
def company_expense_work_details():

    try:
      if request.method == 'POST':
        custid = request.form.get('cust_id')
        date = request.form.get('cust_date')
        category = request.form.get('cust_category_id')
        subcat = request.form.get('cust_subcategory_id')
        description = request.form.get('cust_description')
        amount = float(request.form.get('cust_amount'))
        method = request.form.get('cust_method')

        new_work = WorkDetail(
          customer_id=custid,
          date=datetime.strptime(date, '%Y-%m-%d'),
          category_id=category,
          subcategory_id=subcat,
          amount=float(amount),
          method=method,
          description=description,
        )
        db.session.add(new_work)
        db.session.commit()

        flash('Customer record added successfully!', 'success')
        return redirect(url_for('manage_expenses'))
    except Exception as e:
        print(f"Error while adding customer record: {e}")
        flash('An error occurred while adding customer record.', 'danger')
    return redirect(url_for('manage_expenses'))

if __name__ == '__main__':
    setup_database()
    app.run(debug=True)


