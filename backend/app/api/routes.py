"""
WeatherTato — API Route Handler
"""
import logging
import sqlite3
from fastapi import APIRouter, BackgroundTasks

from models.schemas import UserQuery
from services.llm_service import compiled_graph
from core.env import ENABLE_MLFLOW, MLFLOW_TRACKING_URI, MLFLOW_EXPERIMENT_NAME

logger = logging.getLogger(__name__)
router = APIRouter()

def get_db():
    """
    Generator function to provide a sqlite3 database connection.
    Yields a connection that is closed after use.
    """
    conn = sqlite3.connect("data/weathertato.db", check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


if ENABLE_MLFLOW:
    try:
        import mlflow
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)
    except Exception as e:
        logger.warning(f"[MLflow Warning] Failed to initialize MLflow tracking: {e}")


def run_agent(query: UserQuery) -> dict:
    """Hydrate conversation history and invoke the LangGraph agent."""
    # We rely on LangGraph's internal MemorySaver for conversation history.
    # We DO NOT map or inject query.history into the graph_input because 
    # doing so would overwrite the persistent checkpointer state.
    
    # Ensure a valid thread_id for the MemorySaver
    session_id = query.session_id if query.session_id else "default_session"
    config = {"configurable": {"thread_id": session_id}}
            
    graph_input = {
        "user_query": query.user_query, 
        "waiting_for_location": False, 
        "error": None
        # Omit 'messages' here so it inherits from the MemorySaver checkpoint
    }
    
    try:
        if ENABLE_MLFLOW:
            try:
                import mlflow
                response = compiled_graph.invoke(graph_input, config=config)
            except Exception as mlflow_err:
                logger.error(f"MLflow tracing failed: {mlflow_err}. Executing graph invocation directly without MLflow.")
                response = compiled_graph.invoke(graph_input, config=config)
        else:
            response = compiled_graph.invoke(graph_input, config=config)

        return {
            "response": response.get("final_response"),
            "intent": response.get("intent"),
            "waiting_for_location": response.get("waiting_for_location"),
            "error_detail": None
        }
    except Exception as e:
        logger.error(f"Graph execution failed: {e}", exc_info=True)
        return {
            "response": "Sorry, I couldn't process that at the moment. Please try again.",
            "intent": None,
            "waiting_for_location": False,
            "error_detail": str(e)
        }


@router.post("/chat")
def chat_endpoint(query: UserQuery) -> dict:
    """Handle a single chat turn from the Streamlit frontend."""
    if ENABLE_MLFLOW:
        try:
            import mlflow
            exp = mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)
            with mlflow.start_run(experiment_id=exp.experiment_id, run_name="agent_execution"):
                return run_agent(query)
        except Exception as e:
            logger.warning(f"[MLflow Warning] MLflow tracking failed: {e}")
            return run_agent(query)
    return run_agent(query)


def run_etl_job():
    """
    Executes the ETL pipeline to fetch and insert palay production and retail price data.
    """
    logger.info("Starting ETL Job from API...")
    from services.etl.etl import insert_into_palay_production, insert_into_retail
    
    # Use get_db context to run ETL
    conn_generator = get_db()
    conn = next(conn_generator)
    try:
        cur = conn.cursor()
        insert_into_palay_production(cur)
        insert_into_retail(cur)
        conn.commit()
        logger.info("ETL Job completed successfully.")
    except Exception as e:
        logger.error(f"ETL Job failed: {e}")
        conn.rollback()
    finally:
        conn.close()

@router.post("/etl/run")
def trigger_etl(background_tasks: BackgroundTasks) -> dict:
    """Trigger the ETL pipeline to run in the background."""
    background_tasks.add_task(run_etl_job)
    return {"status": "success", "message": "ETL job started in the background."}

@router.on_event("startup")
def startup_event():
    """Run seeding and ETL on startup in the background."""
    import threading
    
    def run_startup_tasks():
        """
        Background task executed on startup to seed location data and run the initial ETL job.
        """
        logger.info("Running startup tasks: seedlocs and ETL...")
        # 1. seedlocs
        try:
            import os
            import sys
            import csv
            root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            if root_dir not in sys.path:
                sys.path.append(root_dir)
            from data.seed_locs import seed_muni, seed_brgy
            
            conn_generator = get_db()
            conn = next(conn_generator)
            try:
                cur = conn.cursor()
                
                # Execute init.sql first to ensure schema exists
                init_sql_path = os.path.join(root_dir, "data", "init.sql")
                if os.path.exists(init_sql_path):
                    with open(init_sql_path, "r", encoding="utf-8") as sql_file:
                        cur.executescript(sql_file.read())
                
                cur.execute("PRAGMA foreign_keys = ON;")
                muni_csv = os.path.join(root_dir, "data", "philippines_municities_coordinates_2023.csv")
                brgy_csv = os.path.join(root_dir, "data", "philippines_barangay_coordinates_2023.csv")
                
                with open(muni_csv, "r", encoding="utf-8") as f:
                    mdata = list(csv.DictReader(f))
                with open(brgy_csv, "r", encoding="utf-8") as f:
                    bdata = list(csv.DictReader(f))
                    
                seed_muni(cur, mdata)
                seed_brgy(cur, bdata)
                conn.commit()
                logger.info("Seedlocs completed successfully on startup.")
            except Exception as e:
                logger.error(f"Seedlocs failed: {e}")
                conn.rollback()
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"Could not import or run seed_locs: {e}")
            
        # 2. etl
        run_etl_job()

    # Run in a background thread so we don't block server startup
    threading.Thread(target=run_startup_tasks, daemon=True).start()
