import os
import logging
from flask import render_template, send_from_directory
from app import app

# Set up logging
logger = logging.getLogger(__name__)

@app.route('/')
def index():
    """Render landing page with API overview"""
    return render_template('index.html')

@app.route('/docs')
def documentation():
    """Render API documentation page using OpenAPI spec"""
    return render_template('documentation.html')

@app.route('/openapi.yaml')
def openapi_spec():
    """Serve the OpenAPI specification file"""
    return send_from_directory('static', 'openapi.yaml')
