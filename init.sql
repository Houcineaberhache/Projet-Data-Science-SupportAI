CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT,
    chunks_count INTEGER DEFAULT 0,
    uploaded_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE orders (
    order_id VARCHAR(20) PRIMARY KEY,
    customer_id VARCHAR(20),
    product_id VARCHAR(20),
    status VARCHAR(30),
    estimated_delivery VARCHAR(20)
);

CREATE TABLE products (
    product_id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(50),
    price NUMERIC(10, 2)
);

INSERT INTO products VALUES
('PROD001', 'NovaPhone X5', 'smartphones', 4999.00),
('PROD002', 'NovaBook Pro 15', 'laptops', 8999.00),
('PROD003', 'NovaPods Wireless', 'audio', 799.00);

INSERT INTO orders VALUES
('ORD001', 'CUST001', 'PROD001', 'shipped', '2026-11-10'),
('ORD002', 'CUST002', 'PROD002', 'processing', '2026-11-14'),
('ORD003', 'CUST003', 'PROD003', 'delivered', '2026-11-02');
