// Ecosystem PM2 untuk Development Mode (dengan auto-reload)
// Membaca konfigurasi dari .env.services di root directory

const fs = require('fs');
const path = require('path');

// Load environment variables from .env.services
function loadEnvServices() {
  const rootDir = path.join(__dirname, '..');
  const envPath = path.join(rootDir, '.env.services');
  
  if (fs.existsSync(envPath)) {
    const envContent = fs.readFileSync(envPath, 'utf8');
    const lines = envContent.split('\n');
    
    lines.forEach(line => {
      // Skip comments and empty lines
      if (line.trim().startsWith('#') || !line.trim()) return;
      
      const match = line.match(/^([^=]+)=(.*)$/);
      if (match) {
        const key = match[1].trim();
        const value = match[2].trim();
        process.env[key] = value;
      }
    });
  }
}

// Load env
loadEnvServices();

module.exports = {
  apps: [
    {
      name: "agent-service",
      cwd: __dirname,
      script: process.env.AGENT_SERVICE_VENV || "/home/imaji/opensource/rag-llm/.venv/bin/python",
      args: [
        "-m", "uvicorn", 
        "app.router:app", 
        "--host", process.env.AGENT_SERVICE_HOST || "0.0.0.0", 
        "--port", process.env.AGENT_SERVICE_PORT || "8001",
        "--reload"
      ],
      exec_mode: "fork",
      instances: 1,
      autorestart: true,
      watch: ["app"],
      ignore_watch: ["__pycache__", "*.pyc", ".git", "logs"],
      max_memory_restart: "1G",
      env: {
        NODE_ENV: "development",
        DEBUG: "true",
        HOST_AGENT: process.env.AGENT_SERVICE_HOST || "0.0.0.0",
        PORT_AGENT: process.env.AGENT_SERVICE_PORT || "8001"
      },
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
      time: true
    }
  ]
};
