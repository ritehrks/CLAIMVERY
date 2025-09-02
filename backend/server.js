    // backend/server.js

    const express = require('express');
    const { spawn } = require('child_process');
    const cors = require('cors');
    const path = require('path');
    const multer = require('multer'); // For handling file uploads
    const fs = require('fs');

    require('dotenv').config();

    const app = express();
    const PORT = process.env.PORT || 5001;

    // --- Setup for File Uploads ---
    const uploadDir = 'uploads';
    if (!fs.existsSync(uploadDir)) {
        fs.mkdirSync(uploadDir);
    }
    const storage = multer.diskStorage({
        destination: (req, file, cb) => {
            cb(null, uploadDir);
        },
        filename: (req, file, cb) => {
            cb(null, Date.now() + path.extname(file.originalname));
        }
    });
    const upload = multer({ storage: storage });

    // --- Middleware ---
    app.use(cors());
    app.use(express.json());

    // --- API Endpoint ---
    // The upload.single('claimImage') middleware handles the file upload.
    app.post('/api/verify', upload.single('claimImage'), (req, res) => {
        const { original_claim, source_identifier } = req.body;
        
        // The path to the uploaded image, or 'null' if no file was uploaded.
        const imagePath = req.file ? req.file.path : 'null';

        if (!original_claim) {
            return res.status(400).json({ error: 'Claim text is required.' });
        }

        console.log('Received request:', { original_claim, source_identifier, imagePath });
        console.log('Starting Python Planner-Executor agent...');

        const pythonProcess = spawn('python', [
            path.join(__dirname, 'main.py'),
            original_claim,
            source_identifier || 'N/A', // Pass N/A if identifier is empty
            imagePath
        ], {
            env: process.env // This is critical for passing API keys to Python
        });

        let resultData = '';
        let errorData = '';

        pythonProcess.stdout.on('data', (data) => { resultData += data.toString(); });
        pythonProcess.stderr.on('data', (data) => { errorData += data.toString(); });

        pythonProcess.on('close', (code) => {
            console.log(`Python script exited with code ${code}`);
            
            // Clean up the uploaded file after the script finishes
            if (req.file) {
                fs.unlinkSync(imagePath);
            }

            if (code === 0 && resultData) {
                try {
                    res.json(JSON.parse(resultData));
                } catch (e) {
                    res.status(500).json({ error: 'Failed to parse agent result.', details: resultData });
                }
            } else {
                res.status(500).json({ error: 'Agent script failed.', details: errorData });
            }
        });
    });

    app.listen(PORT, () => {
        console.log(`Server is running on http://localhost:${PORT}`);
    });
    