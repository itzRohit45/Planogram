import sqlite3 from 'sqlite3';
import path from 'path';

const dbPath = path.resolve(__dirname, '../../database.sqlite');

const db = new sqlite3.Database(dbPath, (err) => {
  if (err) {
    console.error('Could not connect to database', err);
  } else {
    console.log('Connected to SQLite database');
    initializeDatabase();
  }
});

function initializeDatabase() {
  db.serialize(() => {
    // Baselines table
    db.run(`
      CREATE TABLE IF NOT EXISTS baselines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        image_path TEXT NOT NULL,
        shelf_capacity INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // Audits table
    db.run(`
      CREATE TABLE IF NOT EXISTS audits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        baseline_id INTEGER NOT NULL,
        name TEXT,
        image_path TEXT NOT NULL,
        compliance_score REAL,
        fill_rate REAL,
        report_path TEXT,
        visual_report_path TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (baseline_id) REFERENCES baselines(id)
      )
    `);

    // Products table (Catalog)
    db.run(`
      CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        image_path TEXT NOT NULL,
        fingerprint TEXT NOT NULL,
        color_hist TEXT,
        aspect_ratio REAL,
        orb_descriptors TEXT,
        ocr_text TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);
  });
}

export default db;
