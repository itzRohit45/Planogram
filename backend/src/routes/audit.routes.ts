import { Router } from 'express';
import multer from 'multer';
import path from 'path';
import fs from 'fs';
import db from '../config/db';
import { runMLBaseline, runMLAudit } from '../services/ml.service';

const router = Router();

// Ensure upload directories exist
const uploadDir = path.join(__dirname, '../../../uploads');
const baselineDir = path.join(uploadDir, 'baseline');
const auditDir = path.join(uploadDir, 'audit');
const reportsDir = path.join(__dirname, '../../../reports');

[baselineDir, auditDir, reportsDir].forEach(dir => {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
});

// Configure multer for file uploads
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    if (req.path.includes('/baseline')) {
      cb(null, baselineDir);
    } else {
      cb(null, auditDir);
    }
  },
  filename: (req, file, cb) => {
    const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
    cb(null, file.fieldname + '-' + uniqueSuffix + path.extname(file.originalname));
  }
});

const upload = multer({ 
  storage,
  limits: { fileSize: 10 * 1024 * 1024 }, // 10MB limit
  fileFilter: (req, file, cb) => {
    const allowedTypes = /jpeg|jpg|png|bmp/;
    const extname = allowedTypes.test(path.extname(file.originalname).toLowerCase());
    const mimetype = allowedTypes.test(file.mimetype);
    if (extname && mimetype) {
      return cb(null, true);
    } else {
      cb(new Error('Only JPEG, PNG, and BMP images are allowed.'));
    }
  }
});

// Route: Upload Baseline
router.post('/baseline/upload', upload.single('image'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No image provided' });
    }

    // Convert Windows backslashes to forward slashes for web compatibility
    const imagePath = req.file.path.replace(/\\/g, '/');
    const name = req.body.name || '';

    // Run ML Baseline detection
    const mlResult = await runMLBaseline(imagePath);
    
    if (mlResult.error) {
      return res.status(500).json({ error: mlResult.error });
    }

    const shelfCapacity = mlResult.shelf_capacity;

    // Save to DB
    let visPath = mlResult.visual_report_path ? mlResult.visual_report_path.replace(/\\/g, '/') : null;
    if (visPath) {
      visPath = visPath.split('/').pop() || null; // Store only filename for easy serving
    }
    
    db.run(
      `INSERT INTO baselines (name, image_path, visual_report_path, shelf_capacity) VALUES (?, ?, ?, ?)`,
      [name, imagePath, visPath, shelfCapacity],
      function(err) {
        if (err) {
          console.error(err);
          return res.status(500).json({ error: 'Database error' });
        }
        res.json({
          id: this.lastID,
          name: name,
          image_path: imagePath,
          shelf_capacity: shelfCapacity,
          visual_report_path: mlResult.visual_report_path || null,
          boxes: mlResult.boxes || [],
          message: 'Baseline uploaded and processed successfully'
        });
      }
    );

  } catch (error: any) {
    res.status(500).json({ error: error.message });
  }
});

// Route: Upload Audit and Compare
router.post('/audit/compare', upload.single('image'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No image provided' });
    }
    
    const baselineId = req.body.baselineId;
    const name = req.body.name || '';
    if (!baselineId) {
      return res.status(400).json({ error: 'baselineId is required' });
    }

    // Convert Windows backslashes to forward slashes for web compatibility
    const auditImagePath = req.file.path.replace(/\\/g, '/');

    // Fetch baseline from DB
    db.get(`SELECT * FROM baselines WHERE id = ?`, [baselineId], async (err, baseline: any) => {
      if (err) {
        return res.status(500).json({ error: 'Database error' });
      }
      if (!baseline) {
        return res.status(404).json({ error: 'Baseline not found' });
      }

      // Run ML Comparison
      const mlResult = await runMLAudit(baseline.image_path, auditImagePath, baseline.shelf_capacity);
      
      if (mlResult.error) {
        return res.status(500).json({ error: mlResult.error });
      }

      // Convert Windows backslashes to forward slashes for web compatibility
      if (mlResult.report_path) mlResult.report_path = mlResult.report_path.replace(/\\/g, '/');
      if (mlResult.visual_report_path) mlResult.visual_report_path = mlResult.visual_report_path.replace(/\\/g, '/');

      // Save Audit to DB
      db.run(
        `INSERT INTO audits (baseline_id, name, image_path, compliance_score, fill_rate, report_path, visual_report_path) 
         VALUES (?, ?, ?, ?, ?, ?, ?)`,
        [
          baselineId,
          name,
          auditImagePath, 
          mlResult.compliance_score, 
          mlResult.fill_rate, 
          mlResult.report_path, 
          mlResult.visual_report_path
        ],
        function(err) {
          if (err) {
             console.error(err);
             return res.status(500).json({ error: 'Database error' });
          }
          res.json({
            id: this.lastID,
            compliance_score: mlResult.compliance_score,
            fill_rate: mlResult.fill_rate,
            report_path: mlResult.report_path,
            visual_report_path: mlResult.visual_report_path,
            comparison_report: mlResult.comparison_report,
            message: 'Audit processed successfully'
          });
        }
      );
    });

  } catch (error: any) {
    res.status(500).json({ error: error.message });
  }
});

// Route: Get Baseline List
router.get('/baselines', (req, res) => {
  db.all(`SELECT * FROM baselines ORDER BY created_at DESC`, [], (err, rows) => {
    if (err) return res.status(500).json({ error: 'Database error' });
    res.json(rows);
  });
});

// Route: Get Audits List
router.get('/audits', (req, res) => {
  db.all(`
    SELECT a.*, b.image_path as baseline_image_path 
    FROM audits a 
    JOIN baselines b ON a.baseline_id = b.id 
    ORDER BY a.created_at DESC
  `, [], (err, rows) => {
    if (err) return res.status(500).json({ error: 'Database error' });
    res.json(rows);
  });
});

// Route: Delete Baseline
router.delete('/baseline/:id', (req, res) => {
  const id = req.params.id;
  db.run(`DELETE FROM baselines WHERE id = ?`, [id], function(err) {
    if (err) return res.status(500).json({ error: 'Database error' });
    res.json({ success: true });
  });
});

// Route: Delete Audit
router.delete('/audit/:id', (req, res) => {
  const id = req.params.id;
  db.run(`DELETE FROM audits WHERE id = ?`, [id], function(err) {
    if (err) return res.status(500).json({ error: 'Database error' });
    res.json({ success: true });
  });
});

export default router;
