import os
from flask import Flask, render_template, request, jsonify
import backend_processor

# Initialize Flask app
app = Flask(__name__, template_folder='templates')

# --- CONFIGURATION ---
# Set up directories relative to this app.py file
app.config['BASE_DIR'] = os.path.abspath(os.path.dirname(__file__))
app.config['DOWNLOAD_DIR'] = os.path.join(app.config['BASE_DIR'], "downloaded_pdfs")
app.config['OUTPUT_DIR'] = os.path.join(app.config['BASE_DIR'], "output_files")
app.config['DB_PATH'] = os.path.join(app.config['OUTPUT_DIR'], "kanoon_cases.db")
app.config['EXCEL_PATH'] = os.path.join(app.config['OUTPUT_DIR'], "metadata_audit_log.xlsx")
app.config['JSON_COMPREHENSIVE_PATH'] = os.path.join(app.config['OUTPUT_DIR'], "comprehensive_legal_cases.json")

# Create directories if they don't exist
os.makedirs(app.config['DOWNLOAD_DIR'], exist_ok=True)
os.makedirs(app.config['OUTPUT_DIR'], exist_ok=True)


# --- ROUTES ---

@app.route("/")
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

@app.route("/api/crawl", methods=['POST'])
def api_crawl():
    """
    API endpoint to start the crawling process.
    Receives JSON: { "url": "...", "pages": "..." }
    """
    try:
        data = request.json
        user_url = data.get('url')
        max_pages = int(data.get('pages', 5))

        if not user_url:
            return jsonify({"status": "error", "message": "Search URL is required."}), 400

        # Pass config to the backend processor
        config = {
            'DOWNLOAD_DIR': app.config['DOWNLOAD_DIR']
        }

        # Run the actual crawling logic
        result = backend_processor.run_crawling(config, user_url, max_pages)
        return jsonify(result)

    except Exception as e:
        return jsonify({"status": "error", "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route("/api/parse-meta", methods=['POST'])
def api_parse_meta():
    """API endpoint to run the basic metadata parsing."""
    try:
        # Pass config to the backend processor
        config = {
            'DOWNLOAD_DIR': app.config['DOWNLOAD_DIR'],
            'DB_PATH': app.config['DB_PATH'],
            'EXCEL_PATH': app.config['EXCEL_PATH']
        }
        result = backend_processor.run_meta_parsing(config)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route("/api/parse-sections", methods=['POST'])
def api_parse_sections():
    """API endpoint to run the advanced section parsing."""
    try:
        # Pass config to the backend processor
        config = {
            'DOWNLOAD_DIR': app.config['DOWNLOAD_DIR'],
            'JSON_COMPREHENSIVE_PATH': app.config['JSON_COMPREHENSIVE_PATH']
        }
        result = backend_processor.run_section_parsing(config)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": f"An unexpected error occurred: {str(e)}"}), 500

if __name__ == "__main__":
    # Note: `debug=True` is for development. Remove it for production.
    app.run(debug=True, port=5000)
