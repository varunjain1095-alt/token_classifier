"""Main FastAPI application."""
import asyncio
import os
from fastapi import FastAPI, HTTPException, Request, Response, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.shared.config import get_settings
from src.shared.logger import configure_logging, get_logger
from src.identity.session_manager import session_manager
from src.identity.user_manager import user_manager
from src.intake.file_upload import file_upload_handler
from src.intake.csv_parser import csv_parser
from src.intake.excel_parser import excel_parser
from src.intake.file_validator import file_validator
from src.intake.import_diagnostics import import_diagnostics
from src.intake.stored_dataset import load_stored_rows, build_dataset_records
from src.snapshot.eligibility_screener import eligibility_screener
from src.preview.field_mapper import field_mapper
from src.preview.workload_selector import workload_selector, WorkloadMode
from src.intake.db_connection_validator import connection_validator
from src.intake.metadata_discovery import metadata_discovery
from src.intake.db_preview import db_preview

# Configure logging
settings = get_settings()
configure_logging(debug=settings.debug)
logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Review Classification Workbench",
    description="API for reviewing AI classifications before processing large datasets",
    version="0.1.0",
)

# Configure CORS for frontend. In production the SPA is served same-origin,
# so no CORS is needed; extra origins can be allowed via ALLOWED_ORIGINS.
_default_origins = "http://localhost:3000,http://localhost:3001,http://localhost:5173"
_allowed_origins = [o.strip() for o in
                    os.environ.get("ALLOWED_ORIGINS", _default_origins).split(",")
                    if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Log application startup."""
    logger.info("Application starting up", environment=settings.flask_env)


@app.on_event("shutdown")
async def shutdown_event():
    """Log application shutdown."""
    logger.info("Application shutting down")


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    logger.info("Health check requested")
    return {
        "status": "healthy",
        "service": "review-classification-workbench",
        "version": "0.1.0",
        "environment": settings.flask_env
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Review Classification Workbench API"}


# Session Management Endpoints

class AnonymousSessionRequest(BaseModel):
    pass


class SignedInSessionRequest(BaseModel):
    user_id: str
    project_id: str


@app.post("/api/session/anonymous")
async def create_anonymous_session(request: Request):
    """Create a new anonymous session."""
    try:
        session_id = session_manager.create_anonymous_session(request)
        
        # Create response with session cookie
        response_data = {
            "session_id": session_id,
            "session_type": "anonymous",
            "expires_at": "24 hours"
        }
        
        from fastapi.responses import JSONResponse
        response = JSONResponse(content=response_data)
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="lax",
            max_age=settings.session_timeout
        )
        
        logger.info("Anonymous session created", session_id=session_id[:8])
        return response
    except Exception as e:
        logger.error("Failed to create anonymous session", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create session")


@app.post("/api/session/signed-in")
async def create_signed_in_session(request: Request, session_request: SignedInSessionRequest):
    """Create a new signed-in session."""
    try:
        # Validate user and project (in a real app, you'd verify credentials)
        if not session_request.user_id or not session_request.project_id:
            raise HTTPException(status_code=400, detail="User ID and Project ID required")
        
        session_id = session_manager.create_signed_in_session(
            session_request.user_id, 
            session_request.project_id, 
            request
        )
        
        # Set session cookie
        response = Response()
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="lax",
            max_age=settings.permanent_session_lifetime
        )
        
        logger.info("Signed-in session created", 
                   session_id=session_id[:8], 
                   user_id=session_request.user_id)
        return {
            "session_id": session_id,
            "session_type": "signed_in",
            "user_id": session_request.user_id,
            "project_id": session_request.project_id,
            "expires_at": "7 days"
        }
    except Exception as e:
        logger.error("Failed to create signed-in session", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create session")


@app.get("/api/session/current")
async def get_current_session(request: Request):
    """Get current session information."""
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="No session found")
    
    session_data = session_manager.get_session(session_id)
    if not session_data:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    return {
        "session_id": session_data.session_id,
        "session_type": session_data.session_type.value,
        "user_id": session_data.user_id,
        "project_id": session_data.project_id,
        "created_at": session_data.created_at,
        "last_activity": session_data.last_activity,
        "free_preview_used": session_data.free_preview_used
    }


@app.delete("/api/session/current")
async def delete_current_session(request: Request):
    """Delete current session."""
    session_id = request.cookies.get("session_id")
    if session_id:
        session_manager.delete_session(session_id)
        logger.info("Session deleted", session_id=session_id[:8])
    
    response = Response()
    response.delete_cookie("session_id")
    return {"message": "Session deleted"}


# Health check for session validation
@app.get("/api/session/validate")
async def validate_session(request: Request):
    """Validate current session."""
    session_id = request.cookies.get("session_id")
    if not session_id:
        return {"valid": False, "reason": "No session cookie"}
    
    try:
        session_data = session_manager.validate_session(session_id, request)
        return {
            "valid": True,
            "session_type": session_data.session_type.value,
            "user_id": session_data.user_id,
            "project_id": session_data.project_id
        }
    except HTTPException as e:
        return {"valid": False, "reason": e.detail}
    except Exception as e:
        logger.error("Session validation error", error=str(e))
        return {"valid": False, "reason": "Validation error"}


@app.get("/api/session/project-state")
async def get_project_state(request: Request):
    """Return the wizard/project state persisted on this session."""
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="No session found")

    session_data = session_manager.validate_session(session_id, request)
    if not session_data:
        raise HTTPException(status_code=401, detail="Invalid session")

    return {
        "success": True,
        "project_state": session_data.project_state or {}
    }


@app.post("/api/session/project-state")
async def save_project_state(request: Request, state_request: dict):
    """Persist wizard/project state (file_id, mapping, workload, ...) on the session."""
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="No session found")

    session_data = session_manager.validate_session(session_id, request)
    if not session_data:
        raise HTTPException(status_code=401, detail="Invalid session")

    project_state = state_request.get('project_state')
    if not isinstance(project_state, dict):
        raise HTTPException(status_code=400, detail="project_state must be an object")

    session_manager.update_project_state(session_id, project_state)
    return {"success": True}


# Database Endpoints

@app.post("/api/database/test-connection")
async def test_database_connection(request: Request, connection_request: dict):
    """Test database connection."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        
        # Validate connection
        adapter_type = connection_request.get('adapter_type', 'postgresql')
        connection_params = connection_request.get('connection_params', {})
        
        # Validate parameters
        param_validation = connection_validator.validate_connection_params(adapter_type, connection_params)
        if not param_validation['valid']:
            raise HTTPException(status_code=400, detail=param_validation['error'])
        
        # Test connection
        result = connection_validator.validate_connection(adapter_type, connection_params)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Database connection test error", error=str(e))
        raise HTTPException(status_code=500, detail="Connection test failed")


@app.post("/api/database/schemas")
async def get_database_schemas(request: Request, schema_request: dict):
    """Get database schemas."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        
        adapter_type = schema_request.get('adapter_type', 'postgresql')
        connection_params = schema_request.get('connection_params', {})
        
        schemas = metadata_discovery.discover_schemas(adapter_type, connection_params)
        
        return {
            'success': True,
            'schemas': schemas,
            'adapter': adapter_type
        }
        
    except Exception as e:
        logger.error("Schema discovery error", error=str(e))
        raise HTTPException(status_code=500, detail="Schema discovery failed")


@app.post("/api/database/tables")
async def get_database_tables(request: Request, table_request: dict):
    """Get database tables."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        
        adapter_type = table_request.get('adapter_type', 'postgresql')
        connection_params = table_request.get('connection_params', {})
        schema = table_request.get('schema', 'public')
        
        tables = metadata_discovery.discover_tables(adapter_type, connection_params, schema)
        
        return {
            'success': True,
            'tables': [
                {
                    'schema': table.schema,
                    'name': table.name,
                    'type': table.type,
                    'columns': [
                        {
                            'name': col.name,
                            'data_type': col.data_type,
                            'is_nullable': col.is_nullable,
                            'is_primary_key': col.is_primary_key
                        } for col in table.columns
                    ],
                    'estimated_rows': table.estimated_rows
                } for table in tables
            ],
            'adapter': adapter_type
        }
        
    except Exception as e:
        logger.error("Table discovery error", error=str(e))
        raise HTTPException(status_code=500, detail="Table discovery failed")


@app.post("/api/database/preview")
async def get_database_preview(request: Request, preview_request: dict):
    """Get database preview data."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        
        adapter_type = preview_request.get('adapter_type', 'postgresql')
        connection_params = preview_request.get('connection_params', {})
        schema = preview_request.get('schema', 'public')
        table_name = preview_request.get('table_name')
        columns = preview_request.get('columns', [])
        limit = preview_request.get('limit', 100)
        
        if not table_name:
            raise HTTPException(status_code=400, detail="Table name required")
        
        # Create filter conditions (simplified for now)
        filters = []
        
        preview_result = db_preview.get_preview(
            adapter_type, connection_params, schema, table_name,
            columns, filters, limit
        )
        
        return preview_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Database preview error", error=str(e))
        raise HTTPException(status_code=500, detail="Preview failed")


# Mapping and Workload Endpoints

@app.post("/api/mapping/suggest")
async def suggest_field_mapping(request: Request, mapping_request: dict):
    """Suggest field mappings based on data."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        
        headers = mapping_request.get('headers', [])
        sample_data = mapping_request.get('sample_data', [])
        
        suggestions = field_mapper.suggest_mappings(headers, sample_data)
        
        return {
            'success': True,
            'suggestions': {k: v.value for k, v in suggestions.items()},
            'headers': headers
        }
        
    except Exception as e:
        logger.error("Field mapping suggestion error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to generate suggestions")


@app.post("/api/mapping/validate")
async def validate_field_mapping(request: Request, validation_request: dict):
    """Validate field mapping."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        
        mapping = validation_request.get('mapping', {})
        headers = validation_request.get('headers', [])
        
        validation_result = field_mapper.validate_mapping(mapping, headers)
        
        return {
            'success': True,
            'validation': validation_result
        }
        
    except Exception as e:
        logger.error("Field mapping validation error", error=str(e))
        raise HTTPException(status_code=500, detail="Validation failed")


@app.post("/api/eligibility/screen")
async def screen_eligibility(request: Request, screen_request: dict):
    """Screen records for eligibility."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        
        field_mapping = screen_request.get('field_mapping', {})
        file_id = screen_request.get('file_id')

        if file_id:
            # Screen the complete stored snapshot, not request-supplied rows
            try:
                headers, data_rows, _ = load_stored_rows(file_id)
            except FileNotFoundError:
                raise HTTPException(status_code=404, detail="Uploaded file not found")

            dataset = build_dataset_records(headers, data_rows, field_mapping)
            screening_result = eligibility_screener.screen_records(
                dataset['records'], field_mapping
            )
            screening_result['loaded_physical_rows'] = dataset['loaded_physical_rows']
            screening_result['blank_rows_excluded'] = dataset['blank_rows_excluded']
        else:
            records = screen_request.get('records', [])
            screening_result = eligibility_screener.screen_records(records, field_mapping)

        return {
            'success': True,
            'screening_result': screening_result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Eligibility screening error", error=str(e))
        raise HTTPException(status_code=500, detail="Screening failed")


@app.post("/api/eligibility/records")
async def list_eligible_records(request: Request, records_request: dict):
    """List eligible records from the stored snapshot with pagination and search."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")

        session_data = session_manager.validate_session(session_id, request)

        file_id = records_request.get('file_id')
        if not file_id:
            raise HTTPException(status_code=400, detail="file_id is required")

        field_mapping = records_request.get('field_mapping', {})
        use_column_ids = records_request.get('use_column_ids', True)
        page = max(1, int(records_request.get('page', 1)))
        page_size = min(200, max(1, int(records_request.get('page_size', 25))))
        search = (records_request.get('search') or '').strip().lower()

        try:
            headers, data_rows, _ = load_stored_rows(file_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Uploaded file not found")

        dataset = build_dataset_records(
            headers, data_rows, field_mapping, use_column_ids=use_column_ids
        )
        eligible = dataset['eligible_records']

        if search:
            eligible = [
                r for r in eligible
                if search in str(r['id']).lower()
                or search in str(r['original_review_text']).lower()
            ]

        total = len(eligible)
        start = (page - 1) * page_size
        page_records = eligible[start:start + page_size]

        return {
            'success': True,
            'records': [
                {
                    'record_id': r['id'],
                    'source_row': r['source_row'],
                    'review_text': str(r['original_review_text'])[:200],
                    'metadata': {
                        h: v for h, v in r['mapped_metadata'].items()
                        if field_mapping.get(h) not in (None, 'other')
                    },
                }
                for r in page_records
            ],
            'total_eligible': total,
            'page': page,
            'page_size': page_size,
            'total_pages': max(1, (total + page_size - 1) // page_size),
            'loaded_physical_rows': dataset['loaded_physical_rows'],
            'blank_rows_excluded': dataset['blank_rows_excluded'],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Eligible records listing error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list eligible records")


@app.post("/api/workload/select")
async def select_workload(request: Request, workload_request: dict):
    """Select workload for processing."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        
        mode = workload_request.get('mode')
        params = workload_request.get('params', {})
        file_id = workload_request.get('file_id')
        field_mapping = workload_request.get('field_mapping', {})

        if file_id:
            # Select from the complete stored snapshot
            try:
                headers, data_rows, _ = load_stored_rows(file_id)
            except FileNotFoundError:
                raise HTTPException(status_code=404, detail="Uploaded file not found")

            dataset = build_dataset_records(headers, data_rows, field_mapping)
            records = dataset['records']
        else:
            records = workload_request.get('records', [])
        
        # Convert mode string to enum
        try:
            mode_enum = WorkloadMode(mode)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid workload mode: {mode}")
        
        selection_result = workload_selector.select_workload(records, mode_enum, params)
        
        return {
            'success': selection_result['success'],
            'selection_result': selection_result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Workload selection error", error=str(e))
        raise HTTPException(status_code=500, detail="Workload selection failed")


# Configuration Endpoints

@app.post("/api/configuration/category-sets")
async def create_category_set(request: Request, category_set_data: dict):
    """Create a new category set."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        
        # Validate request contract
        validation = contract_validator.validate_request(
            ContractType.CATEGORY_DEFINITION, 
            category_set_data
        )
        
        if not validation['valid']:
            raise HTTPException(status_code=400, detail=validation['errors'])
        
        # Create category set - use session_id as user_id for anonymous sessions
        user_id = session_data.user_id or session_data.session_id
        result = category_manager.create_category_set(
            name=category_set_data['name'],
            categories=category_set_data['categories'],
            user_id=user_id,
            description=category_set_data.get('description')
        )
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return {
            'success': True,
            'category_set_id': result['category_set_id'],
            'category_set': result['category_set']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Category set creation error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create category set")


@app.get("/api/configuration/category-sets")
async def get_category_sets(request: Request):
    """Get all active category sets for user."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        
        user_id = session_data.user_id or session_data.session_id
        category_sets = category_manager.get_active_category_sets(user_id)
        
        return {
            'success': True,
            'category_sets': category_sets
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Category sets retrieval error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve category sets")


@app.post("/api/configuration/experiment-configs")
async def create_experiment_config(request: Request, config_data: dict):
    """Create a new experiment configuration."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        
        # Validate request contract
        validation = contract_validator.validate_request(
            ContractType.EXPERIMENT_CONFIG, 
            config_data
        )
        
        if not validation['valid']:
            raise HTTPException(status_code=400, detail=validation['errors'])
        
        # Create experiment config
        result = experiment_manager.create_experiment_config(
            name=config_data['name'],
            config_data=config_data['config'],
            user_id=session_data.user_id or session_data.session_id,
            description=config_data.get('description')
        )
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return {
            'success': True,
            'config_id': result['config_id'],
            'config': result['config']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Experiment config creation error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create experiment config")


@app.get("/api/configuration/experiment-configs")
async def get_experiment_configs(request: Request):
    """Get all active experiment configurations for user."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        
        user_id = session_data.user_id or session_data.session_id
        configs = experiment_manager.get_active_configs(user_id)
        
        return {
            'success': True,
            'configs': configs
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Experiment configs retrieval error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve experiment configs")


@app.post("/api/configuration/build-request")
async def build_classification_request(request: Request, request_data: dict):
    """Build classification request payload."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        
        # Validate request contract
        validation = contract_validator.validate_request(
            ContractType.CLASSIFICATION_REQUEST, 
            request_data
        )
        
        if not validation['valid']:
            raise HTTPException(status_code=400, detail=validation['errors'])
        
        # Build request payload
        result = experiment_manager.build_request_payload(
            config_id=request_data['config_id'],
            input_data=request_data['input_data']
        )
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return {
            'success': True,
            'payload': result['payload']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Request building error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to build request")


@app.get("/api/configuration/contracts")
async def get_contracts(request: Request):
    """Get all available request contracts."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        contracts = contract_validator.list_contracts()
        
        return contracts
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Contracts retrieval error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve contracts")


# Token and Pricing Endpoints

@app.post("/api/tokens/estimate-ranges")
async def estimate_token_ranges(request: Request, request_data: dict):
    """Estimate token ranges for a request."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)

        payload = request_data.get('payload')
        experiment_config = request_data.get('experiment_config')
        review_text = request_data.get('review_text')
        file_id = request_data.get('file_id')
        field_mapping = request_data.get('field_mapping', {})
        workload_selection = request_data.get('workload_selection')

        # When an experiment config is supplied, construct the same request
        # the preview executor would send — real system prompt (objective,
        # taxonomy labels, output schema) plus actual review text — instead
        # of trusting a synthetic payload.
        breakdown = None
        if experiment_config is not None:
            # Resolve the exact selected records when a stored file +
            # workload selection are available, so review-text tokens are
            # counted across every record — not extrapolated.
            selected_records = None
            if file_id and workload_selection:
                try:
                    headers, data_rows, _ = load_stored_rows(file_id)
                    dataset = build_dataset_records(headers, data_rows, field_mapping)
                    ws = workload_selection
                    params = {
                        'count': ws.get('count'),
                        'row_ids': ws.get('specificRows') or [],
                        'seed': ws.get('seed'),
                    }
                    sel = workload_selector.select_workload(
                        dataset['records'], WorkloadMode(ws.get('mode', 'all')), params)
                    selected_records = (sel.get('selection') or {}).get('selected_records') \
                        or sel.get('selected_records')
                except Exception as e:
                    logger.warning("Stored-record token counting failed", error=str(e))

            # Per-request payload uses a representative (median-length)
            # review so the token ranges reflect this dataset.
            texts = [str(r.get('review_text') or r.get('original_review_text') or '')
                     for r in (selected_records or [])]
            texts = [t for t in texts if t.strip()]
            if texts:
                texts.sort(key=len)
                rep_text = texts[len(texts) // 2]
            else:
                rep_text = review_text or ''

            record = {'review_text': rep_text}
            config = experiment_config.get('config', {})
            classification_type = config.get('classification_type', 'sentiment')
            taxonomy = (config.get('draft_taxonomy') or {}).get('labels')
            payload = preview_executor._build_classification_payload(
                record, experiment_config, taxonomy)
            review_tokens = token_counter.count_tokens(rep_text)
            input_tokens = payload and token_counter.count_message_tokens(
                payload['messages'], payload['model'])
            overhead = max(0, (input_tokens or 0) - review_tokens)

            if texts:
                # Exact: tokenize every selected review.
                review_total = sum(token_counter.count_tokens(t) for t in texts)
                review_status = 'exact'
                total_requests = len(texts)
            else:
                count = (workload_selection or {}).get('count', 0) or 0
                review_total = review_tokens * count
                review_status = 'estimated' if count else 'unavailable'
                total_requests = count

            breakdown = {
                'review_text_tokens': review_tokens,
                'review_text_tokens_total': review_total,
                'prompt_overhead_tokens': overhead,
                'prompt_overhead_tokens_total': overhead * total_requests,
                'reviews_per_request': 1,
                'total_requests': total_requests,
                'review_text_status': review_status,
                'output_status': 'estimated',
                'taxonomy_applied': bool(taxonomy),
            }

        if not payload:
            payload = {}
        token_ranges = token_counter.get_token_ranges(payload)

        if breakdown:
            breakdown['output_tokens'] = token_ranges['base']['output_tokens']
            breakdown['output_tokens_total'] = (
                token_ranges['base']['output_tokens'] * breakdown['total_requests'])
            token_ranges['breakdown'] = breakdown

        return {
            'success': True,
            'token_ranges': token_ranges
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Token range estimation error", error=str(e))
        raise HTTPException(status_code=500, detail="Token estimation failed")


@app.post("/api/tokens/estimate-cost")
async def estimate_request_cost(request: Request, request_data: dict):
    """Estimate cost for a single request."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        
        token_estimate = request_data.get('token_estimate', {})
        model = request_data.get('model')
        cost_estimate = pricing_manager.estimate_request_cost(token_estimate, model=model)
        
        return {
            'success': True,
            'cost_estimate': cost_estimate
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Cost estimation error", error=str(e))
        raise HTTPException(status_code=500, detail="Cost estimation failed")


@app.post("/api/tokens/estimate-workload-cost")
async def estimate_workload_cost(request: Request, request_data: dict):
    """Estimate cost for a workload of requests."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        
        requests = request_data.get('requests', [])
        model = request_data.get('model')
        workload_cost = pricing_manager.estimate_workload_cost(requests, model=model)
        
        return {
            'success': True,
            'workload_cost': workload_cost
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Workload cost estimation error", error=str(e))
        raise HTTPException(status_code=500, detail="Workload cost estimation failed")


@app.post("/api/tokens/compare-costs")
async def compare_model_costs(request: Request, compare_request: dict):
    """Compare costs across multiple catalogue models on one token estimate."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")

        session_data = session_manager.validate_session(session_id, request)

        token_estimate = compare_request.get('token_estimate', {})
        request_count = int(compare_request.get('request_count', 1))
        model_ids = compare_request.get('model_ids', [])

        if not model_ids:
            raise HTTPException(status_code=400, detail="model_ids is required")

        service_tier = compare_request.get('service_tier', 'standard')
        result = pricing_manager.compare_costs(
            token_estimate, request_count, model_ids, service_tier=service_tier)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Cost comparison error", error=str(e))
        raise HTTPException(status_code=500, detail="Cost comparison failed")


@app.get("/api/tokens/pricing-info")
async def get_pricing_info(request: Request):
    """Get pricing information and metadata."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        pricing_info = pricing_manager.get_pricing_info()
        
        return {
            'success': True,
            'pricing_info': pricing_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Pricing info error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get pricing info")


@app.post("/api/tokens/record-usage")
async def record_actual_usage(request: Request, usage_data: dict):
    """Record actual token usage for recalibration."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        
        request_id = usage_data.get('request_id')
        estimated_tokens = usage_data.get('estimated_tokens', {})
        actual_tokens = usage_data.get('actual_tokens', {})
        model = usage_data.get('model', settings.openai_model_name)
        
        result = recalibration_contract.add_actual_usage(
            request_id, estimated_tokens, actual_tokens, model
        )
        
        return {
            'success': result['success'],
            'record_id': result.get('record_id'),
            'accuracy': result.get('accuracy')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Usage recording error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to record usage")


@app.get("/api/tokens/recalibration-status")
async def get_recalibration_status(request: Request):
    """Get recalibration status and recommendations."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        status = recalibration_contract.get_recalibration_status()
        
        return {
            'success': True,
            'status': status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Recalibration status error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get recalibration status")


@app.get("/api/tokens/calibration-metrics")
async def get_calibration_metrics(request: Request):
    """Get detailed calibration metrics."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        metrics = recalibration_contract.get_calibration_metrics()
        
        return {
            'success': True,
            'metrics': metrics
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Calibration metrics error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get calibration metrics")


# Sampling and Expectations Endpoints

@app.post("/api/sampling/select")
async def select_sample(request: Request, sampling_data: dict):
    """Select representative sample from records."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        
        method = sampling_data.get('method', 'random')
        sample_size = sampling_data.get('sample_size')
        stratify_field = sampling_data.get('stratify_field')
        seed = sampling_data.get('seed')

        file_id = sampling_data.get('file_id')
        pool_size = None

        if file_id:
            # Load eligible records from the stored full snapshot, restricted
            # to the persisted workload selection when one is provided.
            field_mapping = sampling_data.get('field_mapping', {})
            use_column_ids = sampling_data.get('use_column_ids', True)

            try:
                headers, data_rows, _ = load_stored_rows(file_id)
            except FileNotFoundError:
                raise HTTPException(status_code=404, detail="Uploaded file not found")

            dataset = build_dataset_records(
                headers, data_rows, field_mapping, use_column_ids=use_column_ids
            )
            pool = dataset['eligible_records']

            workload = sampling_data.get('workload') or {}
            workload_mode = workload.get('mode')
            if workload_mode:
                try:
                    mode_enum = WorkloadMode(workload_mode)
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid workload mode: {workload_mode}"
                    )
                params = {
                    'count': workload.get('count'),
                    'row_ids': workload.get('specificRows') or workload.get('row_ids') or [],
                    'seed': workload.get('seed'),
                }
                selection = workload_selector.select_workload(pool, mode_enum, params)
                if not selection['success']:
                    raise HTTPException(status_code=400, detail=selection.get('error'))
                pool = selection['selected_records']

            pool_size = len(pool)
            records = [
                {
                    'id': r['id'],
                    'source_row': r['source_row'],
                    'review_text': r['original_review_text'],
                    **r['mapped_metadata'],
                }
                for r in pool
            ]
        else:
            records = sampling_data.get('records', [])
            pool_size = len(records)

        # Convert method string to enum
        try:
            method_enum = SamplingMethod(method)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid sampling method: {method}")

        result = sample_selector.select_sample(
            records, method_enum, sample_size, stratify_field, seed
        )
        result['pool_size'] = pool_size
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return {
            'success': True,
            'sample_result': result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Sample selection error", error=str(e))
        raise HTTPException(status_code=500, detail="Sample selection failed")


@app.post("/api/sampling/expectations")
async def create_expectations(request: Request, expectations_data: dict):
    """Create expectation set for a sample."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        
        sample_id = expectations_data.get('sample_id')
        expectations = expectations_data.get('expectations', [])
        description = expectations_data.get('description')
        
        user_id = session_data.user_id or session_data.session_id
        result = expectations_manager.create_expectation_set(
            sample_id, expectations, user_id, description
        )
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return {
            'success': True,
            'expectation_set_id': result['expectation_set_id'],
            'expectation_set': result['expectation_set']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Expectations creation error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create expectations")


@app.get("/api/sampling/expectations/{expectation_set_id}")
async def get_expectation_set(expectation_set_id: str, request: Request):
    """Get expectation set by ID."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        expectation_set = expectations_manager.get_expectation_set(expectation_set_id)
        
        if not expectation_set:
            raise HTTPException(status_code=404, detail="Expectation set not found")
        
        return {
            'success': True,
            'expectation_set': expectation_set
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Expectation set retrieval error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get expectation set")


@app.post("/api/sampling/validate-sample")
async def validate_sample(request: Request, validation_data: dict):
    """Validate sample size and method."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        sample_size = validation_data.get('sample_size', 10)
        total_records = validation_data.get('total_records', 0)
        
        validation = sample_selector.validate_sample_size(sample_size, total_records)
        
        return {
            'success': True,
            'validation': validation
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Sample validation error", error=str(e))
        raise HTTPException(status_code=500, detail="Sample validation failed")


@app.get("/api/sampling/recommendations/{total_records}")
async def get_sampling_recommendations(total_records: int, request: Request):
    """Get sampling method recommendations."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        # Mock data characteristics for recommendations
        data_characteristics = {
            'has_ratings': True,
            'has_languages': False,
            'has_products': False
        }
        
        recommendations = sample_selector.get_sampling_recommendations(
            total_records, data_characteristics
        )
        
        return {
            'success': True,
            'recommendations': recommendations
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Sampling recommendations error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get recommendations")


# Preview Endpoints

@app.post("/api/preview/execute")
async def execute_preview(request: Request, preview_data: dict):
    """Execute classification preview."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        
        sample_records = preview_data.get('sample_records', [])
        experiment_config = preview_data.get('experiment_config', {})
        expectations = preview_data.get('expectations', [])
        api_key = preview_data.get('api_key')
        regenerate_taxonomy = bool(preview_data.get('regenerate_taxonomy'))
        stability_run = bool(preview_data.get('stability_run'))

        user_id = session_data.user_id or session_data.session_id
        user_type = 'signed_in' if session_data.user_id else 'anonymous'

        # Check quota before execution
        quota_info = preview_executor.check_quota(user_id, user_type)
        if quota_info['exceeded']['any']:
            raise HTTPException(status_code=429, detail="Quota exceeded")

        # Execute preview
        result = await preview_executor.execute_preview(
            sample_records, experiment_config, expectations, user_id, api_key,
            regenerate_taxonomy=regenerate_taxonomy,
            stability_run=stability_run
        )

        if not result['success']:
            raise HTTPException(status_code=400, detail=result['error'])

        return {
            'success': True,
            'preview_id': result['preview_id'],
            'status': result.get('status'),
            'taxonomy': result['results'].get('taxonomy'),
            'run_fingerprint': result['results'].get('run_fingerprint'),
            'diagnostics': result['results'].get('diagnostics'),
            'stability': result['results'].get('stability'),
            'consistency': result['results'].get('consistency'),
            'diagnostic_usage': result['results'].get('diagnostic_usage'),
            'results': result['results'],
            'quota_info': quota_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Preview execution error", error=str(e))
        raise HTTPException(status_code=500, detail="Preview execution failed")


@app.get("/api/preview/quota")
async def get_preview_quota(request: Request):
    """Get user quota information."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        user_id = session_data.user_id or session_data.session_id
        user_type = 'signed_in' if session_data.user_id else 'anonymous'
        
        quota_info = preview_executor.check_quota(user_id, user_type)
        
        return {
            'success': True,
            'quota_info': quota_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Quota check error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to check quota")


@app.get("/api/preview/analysis/{preview_id}")
async def get_preview_analysis(preview_id: str, request: Request):
    """Get preview analysis with results vs expectations."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        analysis = preview_executor.get_preview_summary(preview_id)
        
        if 'error' in analysis:
            raise HTTPException(status_code=404, detail=analysis['error'])
        
        return {
            'success': True,
            'analysis': analysis['analysis']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Preview analysis error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get analysis")


@app.get("/api/preview/status/{preview_id}")
async def get_preview_status(preview_id: str, request: Request):
    """Get preview status."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        preview = preview_executor.get_preview(preview_id)
        
        if not preview:
            raise HTTPException(status_code=404, detail="Preview not found")
        
        return {
            'success': True,
            'preview': {
                'id': preview['id'],
                'status': preview['status'],
                'created_at': preview['created_at'],
                'completed_at': preview.get('completed_at'),
                'provider_status': preview.get('provider_status')
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Preview status error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get preview status")


@app.post("/api/preview/test-connection")
async def test_openai_connection(request: Request, test_data: dict):
    """Test OpenAI API connection."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        api_key = test_data.get('api_key')
        
        # Initialize client with provided key or default
        if api_key:
            if not openai_provider.initialize_client(api_key):
                raise HTTPException(status_code=400, detail="Failed to initialize OpenAI client")
        elif not openai_provider.client:
            if not openai_provider.initialize_client():
                raise HTTPException(status_code=500, detail="OpenAI client not initialized")
        
        # Test connection
        result = await openai_provider.test_connection()
        
        return {
            'success': result['success'],
            'model': result.get('model'),
            'provider_status': result.get('provider_status'),
            'error': result.get('error')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Connection test error", error=str(e))
        raise HTTPException(status_code=500, detail="Connection test failed")


# Results Analysis Endpoints

@app.post("/api/results/analyze")
async def analyze_results(request: Request, analysis_data: dict):
    """Analyze classification results."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        
        results = analysis_data.get('results', [])
        expectations = analysis_data.get('expectations', [])
        analysis_types = analysis_data.get('analysis_types')
        
        # Convert analysis types if provided
        analysis_type_enums = None
        if analysis_types:
            try:
                analysis_type_enums = [AnalysisType(t) for t in analysis_types]
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid analysis type")
        
        result = results_analyzer.analyze_results(results, expectations, analysis_type_enums)
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return {
            'success': True,
            'analysis': result['analysis']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Results analysis error", error=str(e))
        raise HTTPException(status_code=500, detail="Results analysis failed")


@app.post("/api/results/recalibrate")
async def recalibrate_estimates(request: Request, recalibration_data: dict):
    """Perform recalibration based on results."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        
        preview_results = recalibration_data.get('preview_results', [])
        token_estimates = recalibration_data.get('token_estimates', {})
        actual_usage = recalibration_data.get('actual_usage', [])
        expectations = recalibration_data.get('expectations', [])

        result = recalibration_manager.analyze_and_recalibrate(
            preview_results, token_estimates, actual_usage, expectations
        )
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return {
            'success': True,
            'recalibration': result['recalibration']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Recalibration error", error=str(e))
        raise HTTPException(status_code=500, detail="Recalibration failed")


@app.get("/api/results/calibration-status")
async def get_calibration_status(request: Request):
    """Get current calibration status."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        status = recalibration_manager.get_calibration_status()
        
        return {
            'success': True,
            'status': status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Calibration status error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get calibration status")


@app.post("/api/results/apply-calibration")
async def apply_calibration_factors(request: Request, calibration_data: dict):
    """Apply calibration factors to estimates."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        token_estimate = calibration_data.get('token_estimate', {})
        confidence_score = calibration_data.get('confidence_score')
        
        result = recalibration_manager.apply_calibration_factors(token_estimate, confidence_score)
        
        return {
            'success': True,
            'calibrated_estimate': result['calibrated_estimate'],
            'confidence_meets_threshold': result['confidence_meets_threshold'],
            'applied_factors': result['applied_factors']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Calibration application error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to apply calibration")


@app.get("/api/results/recalibration-history")
async def get_recalibration_history(request: Request, limit: int = 10):
    """Get recalibration history."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        history = recalibration_manager.get_recalibration_history(limit)
        
        return {
            'success': True,
            'history': history
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Recalibration history error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get recalibration history")


@app.post("/api/results/compare-previews")
async def compare_previews(request: Request, comparison_data: dict):
    """Compare two preview results."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        preview1_results = comparison_data.get('preview1_results', [])
        preview2_results = comparison_data.get('preview2_results', [])
        
        result = results_analyzer.compare_previews(preview1_results, preview2_results)
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return {
            'success': True,
            'comparison': result['comparison']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Preview comparison error", error=str(e))
        raise HTTPException(status_code=500, detail="Preview comparison failed")


# Category Discovery Endpoints

@app.post("/api/categories/discover")
async def discover_categories(request: Request, discovery_data: dict):
    """Discover categories from sample records."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        
        sample_records = discovery_data.get('sample_records', [])
        method = discovery_data.get('method', 'ai_analysis')
        api_key = discovery_data.get('api_key')
        
        user_id = session_data.user_id or session_data.session_id
        
        # Convert method string to enum
        try:
            method_enum = DiscoveryMethod(method)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid discovery method: {method}")
        
        # Execute category discovery
        result = await category_discovery.discover_categories(
            sample_records, method_enum, user_id, api_key
        )
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return {
            'success': True,
            'discovery_id': result['discovery_id'],
            'discovery': result['discovery']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Category discovery error", error=str(e))
        raise HTTPException(status_code=500, detail="Category discovery failed")


@app.post("/api/categories/refine/{discovery_id}")
async def refine_categories(discovery_id: str, request: Request, refinement_data: dict):
    """Refine discovered categories."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        # Apply refinement
        result = category_discovery.refine_categories(discovery_id, refinement_data)
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return {
            'success': True,
            'discovery': result['discovery']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Category refinement error", error=str(e))
        raise HTTPException(status_code=500, detail="Category refinement failed")


@app.get("/api/categories/discovery/{discovery_id}")
async def get_discovery(discovery_id: str, request: Request):
    """Get discovery by ID."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        discovery = category_discovery.get_discovery(discovery_id)
        
        if not discovery:
            raise HTTPException(status_code=404, detail="Discovery not found")
        
        return {
            'success': True,
            'discovery': discovery
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Discovery retrieval error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get discovery")


@app.get("/api/categories/discoveries")
async def get_user_discoveries(request: Request):
    """Get all discoveries for user."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        user_id = session_data.user_id or session_data.session_id
        
        discoveries = category_discovery.get_user_discoveries(user_id)
        
        return {
            'success': True,
            'discoveries': discoveries
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Discoveries retrieval error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get discoveries")


# Export Endpoints

@app.post("/api/export/create")
async def create_export(request: Request, export_data: dict):
    """Create a new export."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        user_id = session_data.user_id or session_data.session_id
        
        execution_id = export_data.get('execution_id')
        export_type = export_data.get('export_type', 'full_report')
        export_format = export_data.get('export_format', 'csv')
        include_metadata = export_data.get('include_metadata', True)
        filters = export_data.get('filters')
        
        if not execution_id:
            raise HTTPException(status_code=400, detail="Execution ID required")
        
        # Create export
        result = export_manager.create_export(
            user_id, execution_id, export_type, export_format, filters, include_metadata
        )
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return {
            'success': True,
            'export_id': result['export_id'],
            'export': result['export']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Export creation error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create export")


@app.get("/api/export/download/{export_id}")
async def download_export(export_id: str, request: Request):
    """Download export file."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        # Get export
        export = export_manager.get_export(export_id)
        if not export:
            raise HTTPException(status_code=404, detail="Export not found")
        
        # Get execution data for export generation
        # This is simplified - in a real implementation, you'd fetch from database
        execution_data = {
            'results': export.get('results', []),
            'errors': export.get('errors', []),
            'summary': export.get('summary', {}),
            'final_analysis': export.get('final_analysis', {})
        }
        
        # Generate file
        result = export_manager.generate_export_file(export_id, execution_data)
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['error'])
        
        # Return file content
        from fastapi.responses import Response
        
        content = result['file_content']
        filename = result['filename']
        
        # Determine content type
        content_type_map = {
            'csv': 'text/csv',
            'json': 'application/json',
            'excel': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'pdf': 'application/pdf'
        }
        
        content_type = content_type_map.get(export['export_format'], 'application/octet-stream')
        
        return Response(
            content=content,
            media_type=content_type,
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Export download error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to download export")


@app.get("/api/export/list")
async def list_exports(request: Request):
    """Get user's exports."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        user_id = session_data.user_id or session_data.session_id
        
        exports = export_manager.get_user_exports(user_id)
        
        return {
            'success': True,
            'exports': exports
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Export list error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get exports")


@app.get("/api/export/statistics")
async def get_export_statistics(request: Request):
    """Get export statistics."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        user_id = session_data.user_id or session_data.session_id
        
        statistics = export_manager.get_export_statistics(user_id)
        
        return {
            'success': True,
            'statistics': statistics
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Export statistics error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get export statistics")


@app.get("/api/export/{export_id}")
async def get_export(export_id: str, request: Request):
    """Get export by ID."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        export = export_manager.get_export(export_id)
        
        if not export:
            raise HTTPException(status_code=404, detail="Export not found")
        
        return {
            'success': True,
            'export': export
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Export retrieval error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get export")


@app.delete("/api/export/{export_id}")
async def delete_export(export_id: str, request: Request):
    """Delete export."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        result = export_manager.delete_export(export_id)
        
        if not result['success']:
            raise HTTPException(status_code=404, detail=result['error'])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Export deletion error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete export")


# Execution Endpoints

@app.post("/api/execution/start")
async def start_execution(request: Request, execution_data: dict):
    """Start full classification execution."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        user_id = session_data.user_id or session_data.session_id
        
        dataset_records = execution_data.get('dataset_records', [])
        experiment_config = execution_data.get('experiment_config', {})
        category_set = execution_data.get('category_set', {})
        api_key = execution_data.get('api_key', '')
        estimated_cost = execution_data.get('estimated_cost', 0.0)
        
        if not dataset_records:
            raise HTTPException(status_code=400, detail="No dataset records provided")
        
        if not api_key:
            raise HTTPException(status_code=400, detail="API key required")
        
        # Start execution
        result = await classification_executor.start_execution(
            user_id, dataset_records, experiment_config, category_set, api_key, estimated_cost
        )
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['error'])
        
        # Start async execution (don't await it)
        asyncio.create_task(classification_executor.execute_classification(result['execution_id']))
        
        return {
            'success': True,
            'execution_id': result['execution_id'],
            'execution': result['execution']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Execution start error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to start execution")


@app.get("/api/execution/status/{execution_id}")
async def get_execution_status(execution_id: str, request: Request):
    """Get execution status."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        status = classification_executor.get_execution_status(execution_id)
        
        if 'error' in status:
            raise HTTPException(status_code=404, detail=status['error'])
        
        return {
            'success': True,
            'execution': status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Execution status error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get execution status")


@app.post("/api/execution/pause/{execution_id}")
async def pause_execution(execution_id: str, request: Request):
    """Pause execution."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        result = classification_executor.pause_execution(execution_id)
        
        if 'error' in result:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Execution pause error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to pause execution")


@app.post("/api/execution/resume/{execution_id}")
async def resume_execution(execution_id: str, request: Request):
    """Resume execution."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        result = classification_executor.resume_execution(execution_id)
        
        if 'error' in result:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Execution resume error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to resume execution")


@app.post("/api/execution/cancel/{execution_id}")
async def cancel_execution(execution_id: str, request: Request):
    """Cancel execution."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        result = classification_executor.cancel_execution(execution_id)
        
        if 'error' in result:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Execution cancel error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to cancel execution")


@app.get("/api/execution/results/{execution_id}")
async def get_execution_results(execution_id: str, request: Request):
    """Get execution results."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        results = classification_executor.get_execution_results(execution_id)
        
        if 'error' in results:
            raise HTTPException(status_code=404, detail=results['error'])
        
        return {
            'success': True,
            'results': results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Execution results error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get execution results")


@app.get("/api/execution/list")
async def list_executions(request: Request):
    """Get user's executions."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        user_id = session_data.user_id or session_data.session_id
        
        executions = classification_executor.get_user_executions(user_id)
        
        return {
            'success': True,
            'executions': executions
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Execution list error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get executions")


# Recommendations Endpoints

@app.post("/api/recommendations/generate")
async def generate_recommendations(request: Request, recommendation_data: dict):
    """Generate recommendations for optimal configuration."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        
        analysis_results = recommendation_data.get('analysis_results', {})
        discovery_results = recommendation_data.get('discovery_results', {})
        current_config = recommendation_data.get('current_config', {})
        cost_estimate = recommendation_data.get('cost_estimate', {})
        preview_results = recommendation_data.get('preview_results', {})

        # Generate recommendations
        result = recommendation_engine.generate_recommendations(
            analysis_results, discovery_results, current_config, cost_estimate,
            preview_results
        )
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return {
            'success': True,
            'recommendation_id': result['recommendation_id'],
            'recommendation': result['recommendation']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Recommendation generation error", error=str(e))
        raise HTTPException(status_code=500, detail="Recommendation generation failed")


@app.post("/api/recommendations/apply/{recommendation_index}")
async def apply_recommendation(recommendation_index: int, request: Request, apply_data: dict):
    """Apply a specific recommendation."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        session_data = session_manager.validate_session(session_id, request)
        user_id = session_data.user_id or session_data.session_id
        
        # For now, we'll need to get the recommendation_id from the request
        # In a real implementation, you'd store this in the session or pass it
        recommendation_id = apply_data.get('recommendation_id')
        
        if not recommendation_id:
            raise HTTPException(status_code=400, detail="Recommendation ID required")
        
        result = recommendation_engine.apply_recommendation(
            recommendation_id, recommendation_index, user_id
        )
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return {
            'success': True,
            'applied_recommendation': result['applied_recommendation'],
            'message': result['message']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Recommendation application error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to apply recommendation")


@app.get("/api/recommendations/{recommendation_id}")
async def get_recommendation(recommendation_id: str, request: Request):
    """Get recommendation by ID."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        recommendation = recommendation_engine.get_recommendation(recommendation_id)
        
        if not recommendation:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        
        return {
            'success': True,
            'recommendation': recommendation
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Recommendation retrieval error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get recommendation")


@app.get("/api/recommendations/{recommendation_id}/summary")
async def get_recommendation_summary(recommendation_id: str, request: Request):
    """Get recommendation summary."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        summary = recommendation_engine.get_recommendation_summary(recommendation_id)
        
        if 'error' in summary:
            raise HTTPException(status_code=404, detail=summary['error'])
        
        return {
            'success': True,
            'summary': summary
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Recommendation summary error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get recommendation summary")


# Import needed modules
from src.configuration.category_manager import category_manager
from src.configuration.experiment_manager import experiment_manager
from src.configuration.request_contract import contract_validator, ContractType
from src.token_module.token_counter import token_counter
from src.token_module.pricing_manager import pricing_manager
from src.token_module.recalibration_contract import recalibration_contract
from src.sampling.sample_selector import sample_selector, SamplingMethod
from src.sampling.expectations_manager import expectations_manager
from src.providers.openai_provider import openai_provider
from src.preview.preview_executor import preview_executor
from src.results.results_analyzer import results_analyzer, AnalysisType
from src.results.recalibration_manager import recalibration_manager
from src.categories.category_discovery import category_discovery, DiscoveryMethod
from src.recommendations.recommendation_engine import recommendation_engine
from src.execution.classification_executor import classification_executor
from src.export.export_manager import export_manager


# File Upload Endpoints

@app.post("/api/upload/file")
async def upload_file(request: Request, file: UploadFile = File(...)):
    """Handle file upload with parsing."""
    try:
        # Get or create session - anonymous uploads are allowed
        session_id = request.cookies.get("session_id")
        new_session = False
        
        if session_id:
            session_data = session_manager.validate_session(session_id, request)
            if not session_data:
                session_id = None
        
        if not session_id:
            try:
                session_id = session_manager.create_anonymous_session(request)
                new_session = True
            except Exception as e:
                logger.error("Session initialization failed", error=str(e))
                raise HTTPException(
                    status_code=500,
                    detail="Failed to initialize upload session"
                )
        
        # Handle file upload
        upload_result = await file_upload_handler.handle_upload(file, session_id)
        
        # Validate file
        validation_result = file_validator.validate_file(
            upload_result['file_path'], 
            upload_result['filename']
        )
        
        if not validation_result['valid']:
            # Cleanup file on validation failure
            file_upload_handler.cleanup_file(upload_result['file_path'])
            raise HTTPException(status_code=400, detail=validation_result['error'])
        
        # Parse file based on type
        file_extension = upload_result['file_extension']
        
        if file_extension == '.csv':
            # Read file content
            with open(upload_result['file_path'], 'rb') as f:
                file_content = f.read()
            parse_result = csv_parser.parse_file(
                file_content, 
                max_rows=100
            )
        elif file_extension in ['.xlsx', '.xls']:
            # Read file content
            with open(upload_result['file_path'], 'rb') as f:
                file_content = f.read()
            
            # Get sheet names first
            sheet_info = excel_parser.get_sheet_names(
                file_content, 
                file_extension
            )
            
            if not sheet_info['success']:
                raise HTTPException(status_code=400, detail=sheet_info['error'])
            
            # Use first sheet if not specified
            sheet_name = sheet_info['sheet_names'][0] if sheet_info['sheet_names'] else None
            parse_result = excel_parser.parse_file(
                file_content, 
                file_extension, 
                sheet_name, 
                max_rows=100
            )
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")
        
        if not parse_result['success']:
            file_upload_handler.cleanup_file(upload_result['file_path'])
            raise HTTPException(status_code=400, detail=parse_result['error'])
        
        # Generate diagnostics
        diagnostics = import_diagnostics.generate_diagnostics(
            parse_result, 
            upload_result
        )
        
        logger.info("File uploaded and parsed successfully", 
                   file_id=upload_result['file_id'],
                   filename=upload_result['filename'],
                   file_type=parse_result['file_type'])
        
        from fastapi.responses import JSONResponse
        response = JSONResponse(content={
            'file_id': upload_result['file_id'],
            'filename': upload_result['filename'],
            'file_size': upload_result['file_size'],
            'parse_result': parse_result,
            'diagnostics': diagnostics,
            'source_data': upload_result['source_data']
        })
        
        # Set session cookie for newly created anonymous sessions
        if new_session:
            response.set_cookie(
                key="session_id",
                value=session_id,
                httponly=True,
                secure=False,  # Set to True in production with HTTPS
                samesite="lax",
                max_age=settings.session_timeout
            )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("File upload endpoint error", error=str(e))
        raise HTTPException(status_code=500, detail="File upload failed")


@app.get("/api/upload/preview/{file_id}")
async def get_file_preview(file_id: str, request: Request):
    """Get file preview data."""
    try:
        # Get session
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No session found")
        
        # For now, return a placeholder - in a real app, you'd retrieve from database
        return {
            'file_id': file_id,
            'message': 'File preview endpoint - implement with database integration'
        }
        
    except Exception as e:
        logger.error("File preview error", error=str(e), file_id=file_id)
        raise HTTPException(status_code=500, detail="Failed to get preview")


# -----------------------------------------------------------------------------
# Serve the built frontend (production / single-service deploy).
# Mounted LAST so every /api/* route registered above takes precedence.
# In local dev, frontend/dist may not exist — Vite serves the app instead.
# -----------------------------------------------------------------------------
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_FRONTEND_DIST = os.path.join(_REPO_ROOT, 'frontend', 'dist')

if os.path.isdir(_FRONTEND_DIST):
    from fastapi.responses import FileResponse

    _index = os.path.join(_FRONTEND_DIST, 'index.html')

    @app.get('/healthz', include_in_schema=False)
    async def _healthz():
        return {'status': 'ok'}

    @app.get('/{full_path:path}', include_in_schema=False)
    async def _serve_spa(full_path: str):
        """Serve built assets; everything else falls back to index.html."""
        if full_path.startswith('api/'):
            raise HTTPException(status_code=404)
        candidate = os.path.join(_FRONTEND_DIST, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(_index)

    logger.info("Serving frontend build", dist=_FRONTEND_DIST)

