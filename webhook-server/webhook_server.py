from flask import Flask, request, jsonify
import os
import time
import requests
import logging
import json

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Konfiguracja z zmiennych środowiskowych
KUBEFLOW_ENDPOINT = os.environ.get('KUBEFLOW_ENDPOINT', 'http://ml-pipeline.kubeflow.svc.cluster.local:8888')
KUBEFLOW_PIPELINE_ID = os.environ.get('KUBEFLOW_PIPELINE_ID')
WEBHOOK_TOKEN = os.environ.get('WEBHOOK_TOKEN')
KUBEFLOW_TOKEN_PATH = os.environ.get('KF_PIPELINES_SA_TOKEN_PATH', '/var/run/secrets/kubeflow/pipelines/token')

@app.route('/trigger', methods=['POST'])
def trigger_pipeline():
    # Weryfikacja tokenu
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer ') or auth_header[7:] != WEBHOOK_TOKEN:
        logger.error("Unauthorized request attempt")
        return jsonify({"error": "Unauthorized"}), 401
    
    # Pobranie parametrów z żądania
    data = request.json or {}
    logger.info(f"Received webhook trigger with data: {data}")
    
    # Pobranie nazwy obrazu Docker
    image_name = data.get('image_name', 'loprych/kfp-repo:latest')
    
    # Pobranie innych parametrów
    commit_sha = data.get('commit_sha', '')
    commit_message = data.get('commit_message', '')
    
    # Przygotowanie parametrów dla pipeline'u
    pipeline_params = {
        'image_name': image_name
    }
    
    # Dodaj inne parametry, jeśli są potrzebne
    if commit_sha:
        pipeline_params['commit_sha'] = commit_sha
    if commit_message:
        pipeline_params['commit_message'] = commit_message
    
    # Przygotowanie nagłówków dla API call
    headers = {
        'Content-Type': 'application/json'
    }
    
    # Odczytanie tokenu Kubeflow z pliku
    kubeflow_token = None
    if os.path.exists(KUBEFLOW_TOKEN_PATH):
        try:
            with open(KUBEFLOW_TOKEN_PATH, 'r') as token_file:
                kubeflow_token = token_file.read().strip()
                headers['Authorization'] = f'Bearer {kubeflow_token}'
                logger.info("Successfully read Kubeflow token from file")
        except Exception as e:
            logger.error(f"Error reading Kubeflow token: {str(e)}")
    else:
        logger.warning(f"Kubeflow token file not found at {KUBEFLOW_TOKEN_PATH}")
        logger.info("Attempting to continue without authentication")
    
    # Użyj podanego lub domyślnego pipeline ID
    pipeline_id = data.get('pipeline_id', KUBEFLOW_PIPELINE_ID)
    if not pipeline_id:
        return jsonify({"error": "No pipeline_id provided and no default set"}), 400
    
    # Utworzenie nazwy dla uruchomienia pipeline'u
    run_name = f"github-trigger-{commit_sha[:7]}" if commit_sha else f"github-trigger-{int(time.time())}"
    
    # Przygotowanie payload dla Kubeflow Pipelines API v2beta1
    payload = {
        "display_name": run_name,
        "pipeline_spec": {
            "pipeline_id": pipeline_id
        },
        "runtime_config": {
            "parameters": pipeline_params
        }
    }
    
    try:
        # Wywołanie API Kubeflow Pipelines
        api_url = f"{KUBEFLOW_ENDPOINT}/apis/v2beta1/runs"
        logger.info(f"Calling Kubeflow API: {api_url}")
        logger.info(f"With payload: {json.dumps(payload)}")
        
        response = requests.post(
            api_url,
            json=payload,
            headers=headers
        )
        
        # Log odpowiedzi przed sprawdzeniem statusu HTTP
        logger.info(f"Kubeflow API response status: {response.status_code}")
        logger.info(f"Kubeflow API response: {response.text}")
        
        response.raise_for_status()
        result = response.json()
        
        logger.info(f"Pipeline triggered successfully: {result}")
        return jsonify({
            "status": "success",
            "message": "Pipeline triggered successfully",
            "run_id": result.get('run_id') or result.get('id'),
            "parameters": pipeline_params
        }), 200
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error triggering pipeline: {str(e)}")
        if hasattr(e, 'response') and e.response:
            logger.error(f"Response from Kubeflow: {e.response.text}")
        return jsonify({
            "status": "error",
            "message": f"Failed to trigger pipeline: {str(e)}"
        }), 500
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Internal server error: {str(e)}"
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    # Sprawdzenie, czy token Kubeflow jest dostępny
    token_status = "available" if os.path.exists(KUBEFLOW_TOKEN_PATH) else "not available"
    
    return jsonify({
        "status": "healthy", 
        "kubeflow_endpoint": KUBEFLOW_ENDPOINT,
        "pipeline_id": KUBEFLOW_PIPELINE_ID or "not set",
        "kubeflow_token": token_status
    }), 200

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "message": "Kubeflow Pipeline Webhook Server",
        "endpoints": {
            "/health": "Check server status",
            "/trigger": "Trigger Kubeflow Pipeline (POST)"
        }
    }), 200

if __name__ == '__main__':
    # Dodaj informację o konfiguracji przy starcie
    logger.info(f"Starting webhook server with configuration:")
    logger.info(f"Kubeflow Endpoint: {KUBEFLOW_ENDPOINT}")
    logger.info(f"Pipeline ID: {KUBEFLOW_PIPELINE_ID or 'not set'}")
    logger.info(f"Kubeflow Token Path: {KUBEFLOW_TOKEN_PATH}")
    logger.info(f"Webhook Token: {'configured' if WEBHOOK_TOKEN else 'not configured'}")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)