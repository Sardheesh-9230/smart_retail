import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify
from sklearn.linear_model import LinearRegression
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import os
import io
import base64
import numpy as np
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
from datetime import datetime, timedelta
import os
from barcode import Code128
from barcode.writer import ImageWriter
from pyzbar.pyzbar import decode
from PIL import Image
import json
import uuid

app = Flask(__name__)

# Database configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',  # Assuming no password
    'database': 'smart_inventory'
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to database: {err}")
        return None

def create_tables():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            # Create inventory table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    `Product ID` VARCHAR(255) PRIMARY KEY,
                    `Product Name` VARCHAR(255) NOT NULL,
                    Category VARCHAR(255),
                    Quantity INT NOT NULL,
                    Price DECIMAL(10, 2) NOT NULL,
                    Timestamp DATETIME
                )
            """)

            # Create sales_log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sales_log (
                    `Bill ID` VARCHAR(255),
                    `Product ID` VARCHAR(255),
                    `Product Name` VARCHAR(255),
                    `Quantity Sold` INT,
                    Price DECIMAL(10, 2),
                    `Total Amount` DECIMAL(10, 2),
                    Timestamp DATETIME,
                    Hour INT,
                    Day INT,
                    Month INT,
                    PRIMARY KEY (`Bill ID`, `Product ID`),
                    FOREIGN KEY (`Product ID`) REFERENCES inventory(`Product ID`)
                )
            """)
            conn.commit()
            print("Tables created successfully (if they didn't exist).")
        except mysql.connector.Error as err:
            print(f"Error creating tables: {err}")
        finally:
            cursor.close()
            conn.close()

# Initialize tables
create_tables()

os.makedirs('static/barcodes', exist_ok=True)
barcode_folder = os.path.join('static', 'barcodes')
os.makedirs(barcode_folder, exist_ok=True)

@app.route('/')
def home():
    return render_template("home.html")

# --- Billing Routes ---

@app.route('/get_product_details')
def get_product_details():
    barcode = request.args.get('barcode')
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM inventory WHERE `Product ID` = %s", (barcode,))
        product = cursor.fetchone()
        if product:
             # Convert Decimal to float for JSON serialization
            for key, value in product.items():
                if isinstance(value, decimal.Decimal):
                    product[key] = float(value)
            return jsonify(product)
        else:
            return jsonify({'success': False, 'message': 'Product not found'}), 404  # 404 for not found
    except mysql.connector.Error as err:
        print(f"Database error: {err}")  # Log the error
        return jsonify({'success': False, 'message': f'Database error: {err}'}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/generate_bill', methods=['POST'])
def generate_bill():
    billing_data = request.get_json()
    if not billing_data or not billing_data.get('cart'):
        return jsonify({'success': False, 'message': 'No products in cart'}), 400

    # Generate unique bill ID
    bill_id = str(uuid.uuid4())[:8].upper()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Extract customer information
    customer = billing_data.get('customer', {})
    customer_name = customer.get('name', 'Guest')
    customer_phone = customer.get('phone', '')
    customer_email = customer.get('email', '')
    
    conn = get_db_connection()
    if not conn:
         return jsonify({'success': False, 'message': 'Database connection error'}), 500

    cursor = conn.cursor(dictionary=True)

    # Create a customers table if it doesn't exist
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                `Customer ID` INT AUTO_INCREMENT PRIMARY KEY,
                `Name` VARCHAR(255) NOT NULL,
                `Phone` VARCHAR(20) NOT NULL,
                `Email` VARCHAR(255),
                `Created At` DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create bills table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bills (
                `Bill ID` VARCHAR(255) PRIMARY KEY,
                `Customer ID` INT,
                `Subtotal` DECIMAL(10, 2) NOT NULL,
                `Tax` DECIMAL(10, 2) NOT NULL,
                `Total Amount` DECIMAL(10, 2) NOT NULL,
                `Timestamp` DATETIME,
                FOREIGN KEY (`Customer ID`) REFERENCES customers(`Customer ID`)
            )
        """)
        conn.commit()
    except mysql.connector.Error as err:
        print(f"Error creating tables: {err}")
        # Continue execution even if there's an error as tables may already exist

    try:
        # Save customer information
        cursor.execute("""
            INSERT INTO customers (`Name`, `Phone`, `Email`)
            VALUES (%s, %s, %s)
        """, (customer_name, customer_phone, customer_email))
        customer_id = cursor.lastrowid
        
        # Save bill information
        cursor.execute("""
            INSERT INTO bills (`Bill ID`, `Customer ID`, `Subtotal`, `Tax`, `Total Amount`, `Timestamp`)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            bill_id, 
            customer_id, 
            billing_data.get('summary', {}).get('subtotal', 0), 
            billing_data.get('summary', {}).get('tax', 0),
            billing_data.get('summary', {}).get('total', 0),
            timestamp
        ))

        # Process each cart item
        for product in billing_data.get('cart', []):
            product_id = product.get('Product ID')
            if not product_id:
                continue

            quantity = product.get('quantity', 1)

            # Fetch product details and check quantity
            cursor.execute("SELECT * FROM inventory WHERE `Product ID` = %s", (product_id,))
            inventory_row = cursor.fetchone()

            if not inventory_row:
                return jsonify({'success': False, 'message': f'Product {product_id} not found'}), 400

            current_quantity = inventory_row['Quantity']

            if quantity > current_quantity:
                return jsonify({'success': False, 'message': f'Insufficient stock for {product_id}'}), 400

            # Update inventory
            cursor.execute("UPDATE inventory SET Quantity = Quantity - %s WHERE `Product ID` = %s", (quantity, product_id))

            # Add to sales log
            cursor.execute("""
                INSERT INTO sales_log (`Bill ID`, `Product ID`, `Product Name`, `Quantity Sold`, Price, `Total Amount`, Timestamp, Hour, Day, Month)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                bill_id, 
                product_id, 
                inventory_row['Product Name'], 
                quantity, 
                inventory_row['Price'], 
                inventory_row['Price'] * quantity, 
                timestamp,
                datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").hour,
                datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").day,
                datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").month
            ))

        conn.commit()
        
        return jsonify({
            'success': True, 
            'bill_id': bill_id,
            'timestamp': timestamp
        })

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Database error: {err}'}), 500
    finally:
        cursor.close()
        conn.close()

# --- Existing Routes (Modified for consistency) ---
@app.route('/billing', methods=['GET', 'POST'])
def billing():
  return render_template('billing.html')

@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        product_id = request.form['product_id']
        product_name = request.form['product_name']
        category = request.form['category']
        try:
            quantity = int(request.form['quantity'])
            price = float(request.form['price'])
        except ValueError:
            return render_template("add_product.html", error_message="Invalid quantity or price!")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO inventory (`Product ID`, `Product Name`, Category, Quantity, Price, Timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (product_id, product_name, category, quantity, price, timestamp))
                conn.commit()

                # Generate Barcode
                barcode_file_path = os.path.join(barcode_folder, f"{product_id}")
                barcode = Code128(product_id, writer=ImageWriter())
                barcode.save(barcode_file_path)

                return render_template(
                    "add_product.html",
                    success_message="Product added successfully!",
                    barcode_path=barcode_file_path,
                    product_id=product_id
                )
            except mysql.connector.Error as err:
                conn.rollback()
                return render_template("add_product.html", error_message=f"Database error: {err}")
            finally:
                cursor.close()
                conn.close()
        else:
            return render_template("add_product.html", error_message="Database connection error")

    return render_template("add_product.html")


@app.route('/update_stock', methods=['GET', 'POST'])
def update_stock():
    if request.method == 'POST':
        product_id = request.form['product_id']
        try:
            quantity = int(request.form['new_quantity'])
        except ValueError:
            return render_template('update_stock.html', error_message="Invalid quantity!")

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute("UPDATE inventory SET Quantity = %s WHERE `Product ID` = %s", (quantity, product_id))
                conn.commit()
                if cursor.rowcount == 0:
                    return render_template('update_stock.html', error_message="Product ID not found!")
                return render_template('update_stock.html', success_message=f"Stock updated for Product ID: {product_id}")
            except mysql.connector.Error as err:
                conn.rollback()
                return render_template('update_stock.html', error_message=f"Database error: {err}")
            finally:
                cursor.close()
                conn.close()
        else:
            return render_template('update_stock.html', error_message="Database connection error")

    return render_template('update_stock.html')

@app.route('/display_inventory')
def display_inventory():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM inventory")
        inventory_data = cursor.fetchall()
        cursor.close()
        conn.close()
        # Convert Decimal to float for JSON serialization
        for row in inventory_data:
            for key, value in row.items():
                if isinstance(value, decimal.Decimal):
                    row[key] = float(value)
        tables = pd.DataFrame(inventory_data).to_html(classes='table table-striped', index=False)

    else:
        tables = "<p>Error: Could not connect to database.</p>"
    return render_template('display_inventory.html', tables=tables)


@app.route("/remove_product", methods=["GET", "POST"])
def remove_product():
    if request.method == "POST":
        product_id = request.form["product_id"]
        try:
            quantity_to_remove = int(request.form["quantity"])
        except ValueError:
            return render_template("remove_product.html", error_message="Invalid quantity!")

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT Quantity FROM inventory WHERE `Product ID` = %s", (product_id,))
                result = cursor.fetchone()

                if result:
                    current_quantity = result[0]
                    if quantity_to_remove <= current_quantity:
                        new_quantity = current_quantity - quantity_to_remove
                        if new_quantity == 0:
                            cursor.execute("DELETE FROM inventory WHERE `Product ID` = %s", (product_id,))
                        else:
                            cursor.execute("UPDATE inventory SET Quantity = %s WHERE `Product ID` = %s", (new_quantity, product_id))
                        conn.commit()
                        return redirect(url_for("remove_product"))
                    else:
                        return render_template("remove_product.html", error_message="Insufficient quantity!")
                else:
                    return render_template("remove_product.html", error_message="Product ID not found!")
            except mysql.connector.Error as err:
                conn.rollback()
                return render_template("remove_product.html", error_message=f"Database error: {err}")
            finally:
                cursor.close()
                conn.close()
        else:
            return render_template("remove_product.html", error_message="Database connection error")

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM inventory")
        inventory_data = cursor.fetchall()
        cursor.close()
        conn.close()
    else:
        inventory_data = []  # Handle case where database connection fails
    return render_template("remove_product.html", inventory=inventory_data)

import decimal
@app.route('/analyze_inventory')
def analyze_inventory():
    conn = get_db_connection()
    if not conn:
        return render_template("analyze_inventory.html", error_message="Database connection error.")

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT i.Category, SUM(s.Price) as TotalSales
            FROM sales_log s
            LEFT JOIN inventory i ON s.`Product ID` = i.`Product ID`
            GROUP BY i.Category
        """)
        sales_data = cursor.fetchall()

        if not sales_data:
            return render_template("analyze_inventory.html", error_message="No sales data available or category data unavailable.")
        
        # Convert Decimal to float for plotting
        sales_by_category = {row['Category']: float(row['TotalSales']) if row['TotalSales'] is not None else 0 for row in sales_data}


        # Plotting
        fig, ax = plt.subplots(figsize=(10, 6))
        categories = list(sales_by_category.keys())
        total_sales = list(sales_by_category.values())

        ax.bar(categories, total_sales, color='skyblue')
        ax.set_title('Sales by Category')
        ax.set_xlabel('Category')
        ax.set_ylabel('Total Sales ($)')
        ax.set_xticks(range(len(categories)))
        ax.set_xticklabels(categories, rotation=45)

        plt.tight_layout()

        # Save plot as image
        img = io.BytesIO()
        plt.savefig(img, format='png')
        img.seek(0)
        plot_url = base64.b64encode(img.getvalue()).decode()
        plt.close()

    except mysql.connector.Error as err:
        return render_template("analyze_inventory.html", error_message=f"Database error: {err}")
    finally:
        cursor.close()
        conn.close()

    return render_template("analyze_inventory.html", plot_url=plot_url)


@app.route('/predict_sales')
def predict_sales():
    conn = get_db_connection()
    if not conn:
        return render_template("predict_sales.html", error_message="Database connection error.")

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT `Product Name`, DATE_FORMAT(Timestamp, '%Y-%m') as Month, SUM(`Quantity Sold`) as `Quantity Sold`
            FROM sales_log
            GROUP BY `Product Name`, DATE_FORMAT(Timestamp, '%Y-%m')
            ORDER BY `Product Name`, Month
        """)
        sales_data = cursor.fetchall()

        if not sales_data:
            return render_template("predict_sales.html", error_message="No sales data available.")

        # Prepare data for prediction
        sales_by_month = {}
        for row in sales_data:
            product_name = row['Product Name']
            month = row['Month']
            quantity_sold = int(row['Quantity Sold']) if row['Quantity Sold'] is not None else 0 # Ensure numeric

            if product_name not in sales_by_month:
                sales_by_month[product_name] = {}
            sales_by_month[product_name][month] = quantity_sold

        predictions = {}
        future_months = 3  # Number of months to predict

        for product, monthly_data in sales_by_month.items():
            # Convert monthly data to lists for the model
            months = list(monthly_data.keys())
            quantities = list(monthly_data.values())
            
            # Create numeric representation of months for the model
            numeric_months = list(range(len(months)))

            if len(numeric_months) > 1:
                # Prepare features (X) and target (y)
                X = np.array(numeric_months).reshape(-1, 1)
                y = np.array(quantities)

                # Train Linear Regression model
                model = LinearRegression()
                model.fit(X, y)
                
                # Predict sales for the next few months
                last_month = datetime.strptime(months[-1] + '-01', '%Y-%m-%d')
                future_month_labels = [(last_month + timedelta(days=30 * i)).strftime('%Y-%m') for i in range(1, future_months + 1)]
                next_months = np.array([[len(numeric_months) + i] for i in range(1, future_months + 1)])
                predicted_sales = model.predict(next_months)

                # Ensure predicted sales are non-negative
                predicted_sales = [max(0, int(sale)) for sale in predicted_sales]  # Convert to integers

                # Prepare predictions
                predictions[product] = {
                    'months': months,
                    'quantities': quantities,
                    'future_months': future_month_labels,
                    'predicted_quantities': predicted_sales
                }

        # If predictions are empty, return an error message
        if not predictions:
            return render_template("predict_sales.html", error_message="Insufficient data for predictions.")

        # Plotting Predictions
        fig, ax = plt.subplots(figsize=(12, 8))
        for product, data in predictions.items():
            ax.plot(data['months'], data['quantities'], label=f"{product} (Actual)", marker='o')
            ax.plot(data['future_months'], data['predicted_quantities'], linestyle='--', label=f"{product} (Predicted)")

        ax.set_title("Sales Prediction by Product")
        ax.set_xlabel("Month")
        ax.set_ylabel("Quantity Sold")
        ax.legend()
        plt.xticks(rotation=45)
        plt.tight_layout()

        # Save plot as image
        img = io.BytesIO()
        plt.savefig(img, format='png')
        img.seek(0)
        plot_url = base64.b64encode(img.getvalue()).decode()
        plt.close()

    except mysql.connector.Error as err:
        return render_template("predict_sales.html", error_message=f"Database error: {err}")
    finally:
        cursor.close()
        conn.close()

    return render_template("predict_sales.html", plot_url=plot_url)


@app.route('/view_sales')
def view_sales():
    conn = get_db_connection()
    if not conn:
        return render_template("view_sales.html", error_message="Database connection error.")

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT `Bill ID`, `Product ID`, `Product Name`, `Quantity Sold`, Price, `Total Amount`, Timestamp, Hour, Day, Month
            FROM sales_log
        """)
        sales_data = cursor.fetchall()

        # Convert Decimal to float and format Timestamp
        for row in sales_data:
            for key, value in row.items():
                if isinstance(value, decimal.Decimal):
                    row[key] = float(value)
                if isinstance(value, datetime):
                    row[key] = value.strftime("%Y-%m-%d %H:%M:%S")

        if sales_data:
             table_html = pd.DataFrame(sales_data).to_html(classes='table table-striped', index=False)
        else:
            table_html = "<p>No sales data available.</p>"

    except mysql.connector.Error as err:
        return render_template("view_sales.html", error_message=f"Database error: {err}")
    finally:
        cursor.close()
        conn.close()

    return render_template(
        "view_sales.html",
        tables=table_html,
        datetime=datetime
    )


@app.route('/download_qr_pdf')
def download_qr_pdf():
    # Define the folder where QR codes are stored
    barcode_folder= os.path.join('static', 'barcodes')

    # Get all image files in the folder (filter for .png files)
    barcode_files= [f for f in os.listdir(barcode_folder) if f.endswith('.png')]

    # Check if there are no QR code files
    if not barcode_files:
        return "No Barcode images found in the directory."

    # Create a BytesIO buffer for the PDF
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(letter))

    # Define the starting position for the QR codes
    y_position = 500
    for barcode_filename in barcode_files:
        qr_code_path = os.path.join(barcode_folder,barcode_filename)
        
        # Extract the product number from the filename (assuming it's the part before '.png')
        product_number = os.path.splitext(barcode_filename)[0]

        # Check if the file exists before adding it to the PDF
        if os.path.exists(qr_code_path):
            # Add QR code to the PDF
            c.drawImage(qr_code_path, 100, y_position, width=200, height=200)

            # Add the product number as text below the QR code
            c.setFont("Helvetica", 12)
            c.drawString(100, y_position - 20, f"Product Number: {product_number}")

            # Adjust the vertical position for the next QR code
            y_position -= 240  # Adjust the vertical position to leave space for the next QR code and text
            
            # Check if space is running out on the current page and create a new one
            if y_position < 100:
                c.showPage()
                y_position = 500  # Reset the position for the new page

    # Finalize the PDF
    c.showPage()
    c.save()

    # Get the PDF data from the buffer
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="barcodes_with_product_numbers.pdf", mimetype='application/pdf')

@app.route('/billing_history')
def billing_history():
    conn = get_db_connection()
    if not conn:
        return render_template("view_sales.html", error_message="Database connection error.")

    cursor = conn.cursor(dictionary=True)
    try:
        # Join bills, customers, and sales_log tables to get comprehensive transaction data
        cursor.execute("""
            SELECT b.`Bill ID`, b.`Timestamp`, b.`Subtotal`, b.`Tax`, b.`Total Amount`,
                   c.`Name` as CustomerName, c.`Phone` as CustomerPhone, c.`Email` as CustomerEmail,
                   COUNT(DISTINCT s.`Product ID`) as TotalItems, SUM(s.`Quantity Sold`) as TotalQuantity
            FROM bills b
            JOIN customers c ON b.`Customer ID` = c.`Customer ID`
            JOIN sales_log s ON b.`Bill ID` = s.`Bill ID`
            GROUP BY b.`Bill ID`
            ORDER BY b.`Timestamp` DESC
        """)
        bills_data = cursor.fetchall()

        # Convert Decimal to float and format Timestamp
        for row in bills_data:
            for key, value in row.items():
                if isinstance(value, decimal.Decimal):
                    row[key] = float(value)
                if isinstance(value, datetime):
                    row[key] = value.strftime("%Y-%m-%d %H:%M:%S")

        if bills_data:
            bills_df = pd.DataFrame(bills_data)
            bills_table = bills_df.to_html(classes='table table-striped', index=False)
        else:
            bills_table = "<p>No billing history available.</p>"

    except mysql.connector.Error as err:
        return render_template("billing_history.html", error_message=f"Database error: {err}")
    finally:
        cursor.close()
        conn.close()

    return render_template(
        "billing_history.html",
        tables=bills_table
    )

if __name__ == '__main__':
    app.run(debug=True)
