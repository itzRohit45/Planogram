import { Router } from 'express';
import multer from 'multer';
import path from 'path';
import fs from 'fs';
import db from '../config/db';
import { runMLCatalog } from '../services/ml.service';

const router = Router();

// Ensure upload directories exist
const uploadDir = path.join(__dirname, '../../../uploads');
const catalogDir = path.join(uploadDir, 'catalog');

if (!fs.existsSync(catalogDir)) {
  fs.mkdirSync(catalogDir, { recursive: true });
}

// Configure multer for file uploads
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    cb(null, catalogDir);
  },
  filename: (req, file, cb) => {
    const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
    cb(null, file.fieldname + '-' + uniqueSuffix + path.extname(file.originalname));
  }
});

const upload = multer({ 
  storage,
  limits: { fileSize: 10 * 1024 * 1024 }, // 10MB limit
});

// Route: Upload new product to catalog
router.post('/', upload.single('image'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No image provided' });
    }

    // Convert Windows backslashes to forward slashes for web compatibility
    const imagePath = req.file.path.replace(/\\/g, '/');
    const name = req.body.name;
    
    if (!name) {
      return res.status(400).json({ error: 'Product name is required' });
    }

    // Run ML Catalog extraction
    const mlResult = await runMLCatalog(imagePath);
    
    if (mlResult.error) {
      return res.status(500).json({ error: mlResult.error });
    }

    const fingerprintJson = JSON.stringify(mlResult.fingerprint);
    const colorHistJson = mlResult.color_hist ? JSON.stringify(mlResult.color_hist) : null;
    const orbDescJson = mlResult.orb_descriptors ? JSON.stringify(mlResult.orb_descriptors) : null;
    const aspectRatio = mlResult.aspect_ratio || null;
    const ocrText = mlResult.ocr_text || null;

    // Log the generated ML features as requested
    console.log(`\n--- ML Feature Generation for ${name} ---`);
    console.log(`DINOv2 Semantic Fingerprint Generated: Yes (${mlResult.fingerprint.length} dimensions)`);
    console.log(`HSV Color Histogram Generated: ${mlResult.color_hist ? 'Yes' : 'No'}`);
    console.log(`Aspect Ratio Extracted: ${aspectRatio ? aspectRatio.toFixed(2) : 'No'}`);
    console.log(`ORB Descriptors Generated: ${mlResult.orb_descriptors ? 'Yes' : 'No'}`);
    if (mlResult.color_hist) {
        // Just print a small sample of the 512-dimension histogram array
        console.log(`Histogram Sample: [${mlResult.color_hist.slice(0, 5).map((x: number) => x.toFixed(4)).join(', ')} ...]`);
    }
    console.log(`----------------------------------\n`);

    // Save to DB
    db.run(
      `INSERT INTO products (name, image_path, fingerprint, color_hist, aspect_ratio, orb_descriptors, ocr_text) VALUES (?, ?, ?, ?, ?, ?, ?)`,
      [name, imagePath, fingerprintJson, colorHistJson, aspectRatio, orbDescJson, ocrText],
      function(err) {
        if (err) {
          console.error(err);
          return res.status(500).json({ error: 'Database error' });
        }
        res.json({
          id: this.lastID,
          name: name,
          image_path: imagePath,
          message: 'Product added to catalog successfully'
        });
      }
    );

  } catch (error: any) {
    res.status(500).json({ error: error.message });
  }
});

// Route: Get all products
router.get('/', (req, res) => {
  db.all(`SELECT id, name, image_path, created_at FROM products ORDER BY id DESC`, [], (err, rows) => {
    if (err) {
      return res.status(500).json({ error: 'Database error' });
    }
    res.json(rows);
  });
});

// Route: Delete a product
router.delete('/:id', (req, res) => {
  const { id } = req.params;
  db.run(`DELETE FROM products WHERE id = ?`, [id], function(err) {
    if (err) {
      return res.status(500).json({ error: 'Database error' });
    }
    res.json({ message: 'Product deleted successfully' });
  });
});

export default router;
