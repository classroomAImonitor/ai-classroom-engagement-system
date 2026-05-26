#!/bin/bash
# ============================================
# ClassMonitor AI — Project Setup Script
# ============================================
# Run this script whenever you clone/open the project fresh:
#   chmod +x setup.sh && ./setup.sh

set -e

echo "🔧 ClassMonitor AI — Setting up project..."
echo ""

# 1. Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "   ✅ Virtual environment created"
else
    echo "📦 Virtual environment already exists"
fi

# 2. Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# 3. Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip --quiet

# 4. Install dependencies
echo "📥 Installing dependencies from requirements.txt..."
pip install -r requirements.txt --quiet
echo "   ✅ All packages installed"

# 5. Check for .env file
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  WARNING: No .env file found!"
    echo "   Copying from .env.example..."
    cp .env.example .env
    echo "   📝 Please edit .env and add your actual secret keys!"
else
    echo "🔐 .env file found"
fi

# 6. Run migrations
echo "🗄️  Running database migrations..."
python manage.py migrate --run-syncdb
echo "   ✅ Database ready"

echo ""
echo "============================================"
echo "✅ Setup complete!"
echo ""
echo "To start the server:"
echo "   source venv/bin/activate"
echo "   python manage.py runserver"
echo "============================================"
