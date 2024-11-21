from flask import Flask, send_from_directory
import os

# Create a Flask app
app = Flask(__name__)

# Configure the static folder
STATIC_FOLDER = 'static'
app.config['STATIC_FOLDER'] = STATIC_FOLDER

@app.route('/images/<filename>')
def serve_image(filename):
    """Serve images from the static folder."""
    return send_from_directory(app.config['STATIC_FOLDER'], filename)

# Run the Flask server
if __name__ == "__main__":
    # Ensure the static folder exists
    os.makedirs(STATIC_FOLDER, exist_ok=True)
    print(f"Serving images from {STATIC_FOLDER}")
    app.run(host='0.0.0.0', port=5000)
