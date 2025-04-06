# Smart Retail System

A comprehensive retail management system that includes inventory tracking, sales processing, billing, and sales prediction capabilities.

## Live Demo

Visit the live demo of Smart Retail System at: [https://sardheesh-9230.github.io/smart_retail/](https://sardheesh-9230.github.io/smart_retail/)

## Features

- **Inventory Management**: Add, update, and remove products from inventory
- **Barcode Integration**: Manage products with barcode support
- **Billing System**: Process sales and generate bills
- **Sales Analysis**: View and analyze sales history
- **Predictive Analytics**: Forecast future sales based on historical data
- **User-friendly Interface**: Clean and responsive design for ease of use

## Technologies Used

- **Backend**: Python with Flask
- **Database**: SQL
- **Frontend**: HTML, CSS, JavaScript
- **Deployment**: GitHub Pages

## Installation & Setup

### Prerequisites
- Python 3.7 or higher
- SQL database (such as SQLite, MySQL)
- Web browser

### Setup Instructions

1. Clone the repository:
   ```
   git clone https://github.com/Sardheesh-9230/smart_retail.git
   ```

2. Navigate to the project directory:
   ```
   cd smart_retail
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

4. Initialize the database:
   ```
   python -c "import app; app.init_db()"
   ```

5. Run the application:
   ```
   python app.py
   ```

6. Open a web browser and navigate to `http://localhost:5000`

## Project Structure

- **app.py**: Main Flask application
- **create_tables.sql**: SQL script to initialize database tables
- **css/**: Stylesheet files
- **js/**: JavaScript files
- **static/**: Static assets including images and barcodes
- **templates/**: HTML templates for different pages

## Usage Instructions

1. **Home Page**: Navigate through different modules
2. **Add Product**: Add new products to inventory
3. **Update Stock**: Update existing product quantities
4. **Billing**: Process customer sales
5. **View Sales**: See sales history and analytics
6. **Predict Sales**: Use predictive analytics for inventory planning

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Contact

For questions or feedback, please contact the project maintainer at [sardheeshmuthusamy@gmail.com](mailto:sardheeshmuthusamy@gmail).

## License

This project is licensed under the MIT License - see the LICENSE file for details.
