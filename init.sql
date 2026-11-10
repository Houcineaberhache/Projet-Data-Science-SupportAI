CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    chunks_count INTEGER DEFAULT 0,
    uploaded_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE conversations (
    id VARCHAR(64) PRIMARY KEY,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(64) REFERENCES conversations(id),
    question TEXT,
    answer TEXT,
    is_abstained BOOLEAN DEFAULT FALSE,
    intent VARCHAR(50),
    confidence FLOAT,
    mode VARCHAR(20),
    latency_ms INTEGER,
    sources TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE feedback (
    id SERIAL PRIMARY KEY,
    message_id INTEGER REFERENCES messages(id),
    rating INTEGER,
    comment TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE orders (
    order_id VARCHAR(20) PRIMARY KEY,
    customer_id VARCHAR(20),
    product_id VARCHAR(20),
    status VARCHAR(30),
    estimated_delivery VARCHAR(20)
);

INSERT INTO orders VALUES
('ORD001', 'CUST001', 'PROD001', 'shipped', '2026-11-10'),
('ORD002', 'CUST002', 'PROD002', 'processing', '2026-11-14'),
('ORD003', 'CUST003', 'PROD003', 'delivered', '2026-11-02');