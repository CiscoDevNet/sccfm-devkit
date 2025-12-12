#!/bin/bash
set -e

echo "🔨 Building and installing cisco.sccfm Ansible collection..."

# Step 1: Ensure poetry venv exists and install Python dependencies
echo "📦 Setting up Python virtual environment and dependencies..."
cd ..
poetry env use python3.12 || poetry env use python3
poetry install

# Step 2: Install Ansible collection
echo "🎭 Installing Ansible collection..."
cd sccfm-ansible
ansible-galaxy collection install . --force

echo "✅ Build complete!"
echo ""
echo "To use the collection, run:"
echo "  export SCCFM_REGION=your-region"
echo "  export SCCFM_API_TOKEN=your-token"
echo "  ansible-playbook -i examples/inventory.sccfm.yml examples/show_devices.yml"
