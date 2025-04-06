-- Create the inventory table
CREATE TABLE IF NOT EXISTS inventory (
    `Product ID` VARCHAR(255) PRIMARY KEY,
    `Product Name` VARCHAR(255) NOT NULL,
    Category VARCHAR(255),
    Quantity INT NOT NULL,
    Price DECIMAL(10, 2) NOT NULL,
    Timestamp DATETIME
);

-- Create the sales_log table
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
);