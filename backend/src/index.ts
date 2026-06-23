import express from 'express';
import cors from 'cors';
import path from 'path';
const auditRoutes = require('./routes/audit.routes').default;
import db from './config/db';

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Serve uploaded files and generated reports statically
app.use('/uploads', express.static(path.join(__dirname, '../../uploads')));
app.use('/reports', express.static(path.join(__dirname, '../../reports')));

// Test DB Connection implicitly on import
console.log('Initializing DB...');

// Routes
app.use('/api', auditRoutes);

app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
});
