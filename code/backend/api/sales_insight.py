"""
SalesInsight API Blueprint.

This module provides the Flask API endpoints for the SalesInsight
natural language sales analytics feature.
"""

import logging
from flask import Blueprint, jsonify, request, Response
import json

logger = logging.getLogger(__name__)

bp_sales_insight = Blueprint("sales_insight", __name__)

# Lazy initialization of the agent to avoid import cycles
_agent = None


def get_sales_insight_agent():
    """Get or create the SalesInsight agent (lazy initialization)."""
    global _agent
    if _agent is None:
        from backend.batch.utilities.salesinsight import SalesInsightAgent
        _agent = SalesInsightAgent()
    return _agent


@bp_sales_insight.route("/sales-insight/query", methods=["POST"])
async def query_sales_data():
    """
    Process a natural language query about sales data.

    Request Body:
        {
            "question": "What are the top 10 products by revenue?",
            "include_chart": true,
            "conversation_id": "optional-conversation-id"
        }

    Response:
        {
            "request_id": "uuid",
            "question": "original question",
            "sql_query": "generated SQL",
            "data": [...],
            "chart": {
                "image_base64": "...",
                "format": "png"
            },
            "summary": "natural language summary",
            "execution_time_ms": 1234.5
        }
    """
    try:
        # Parse request
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400

        question = data.get("question")
        if not question:
            return jsonify({"error": "Question is required"}), 400

        include_chart = data.get("include_chart", True)
        conversation_id = data.get("conversation_id")

        logger.info(
            "SalesInsight query received: %s (conversation_id=%s)",
            question[:100],
            conversation_id,
        )

        # Get agent and process query
        agent = get_sales_insight_agent()
        response = await agent.query(
            question=question,
            generate_chart=include_chart,
        )

        # Return response
        return jsonify(response.to_dict())

    except Exception as e:
        logger.error("SalesInsight query failed: %s", e)
        return jsonify({
            "error": str(e),
            "message": "Failed to process sales insight query",
        }), 500


@bp_sales_insight.route("/sales-insight/query/stream", methods=["POST"])
async def query_sales_data_stream():
    """
    Process a sales query with streaming response.

    This endpoint streams the response as Server-Sent Events,
    providing incremental updates as the query is processed.

    Request Body: Same as /sales-insight/query

    Response: Server-Sent Events stream with:
        - status: Processing status updates
        - sql: Generated SQL query
        - data: Query results
        - chart: Generated chart
        - summary: Final summary
        - done: Completion signal
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400

        question = data.get("question")
        if not question:
            return jsonify({"error": "Question is required"}), 400

        include_chart = data.get("include_chart", True)

        def generate():
            """Generator for SSE stream."""
            try:
                # Send status update
                yield f"data: {json.dumps({'type': 'status', 'message': 'Processing query...'})}\n\n"

                # Get agent
                agent = get_sales_insight_agent()

                # Note: For true streaming, we'd need to break down the agent
                # pipeline. For now, we process and send results in chunks.
                import asyncio
                response = asyncio.run(agent.query(
                    question=question,
                    generate_chart=include_chart,
                ))

                # Send SQL
                yield f"data: {json.dumps({'type': 'sql', 'sql': response.sql_query, 'explanation': response.explanation})}\n\n"

                # Send data summary
                if response.data is not None and not response.data.empty:
                    yield f"data: {json.dumps({'type': 'data', 'row_count': response.row_count, 'columns': list(response.data.columns)})}\n\n"

                    # Send data in chunks
                    chunk_size = 50
                    for i in range(0, len(response.data), chunk_size):
                        chunk = response.data.iloc[i:i + chunk_size]
                        yield f"data: {json.dumps({'type': 'data_chunk', 'data': chunk.to_dict(orient='records')})}\n\n"

                # Send chart
                if response.chart_base64:
                    yield f"data: {json.dumps({'type': 'chart', 'image_base64': response.chart_base64, 'format': 'png'})}\n\n"

                # Send summary
                yield f"data: {json.dumps({'type': 'summary', 'summary': response.summary})}\n\n"

                # Send completion
                yield f"data: {json.dumps({'type': 'done', 'request_id': response.request_id, 'execution_time_ms': response.execution_time_ms})}\n\n"

            except Exception as e:
                logger.error("Streaming query failed: %s", e)
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    except Exception as e:
        logger.error("SalesInsight streaming query failed: %s", e)
        return jsonify({"error": str(e)}), 500


@bp_sales_insight.route("/sales-insight/schema", methods=["GET"])
def get_schema_info():
    """
    Get available database schema information.

    Query Parameters:
        table_name: Optional specific table to get schema for

    Response:
        {
            "tables": ["TableA", "TableB", ...],
            "columns": {...}  // if table_name specified
        }
    """
    try:
        from backend.batch.utilities.salesinsight import SalesInsightAgent

        table_name = request.args.get("table_name")

        agent = get_sales_insight_agent()
        schema_discovery = agent._schema_discovery

        if table_name:
            schema = schema_discovery.get_table_schema(table_name)
            return jsonify({
                "table": table_name,
                "columns": [
                    {
                        "name": col.name,
                        "type": col.data_type,
                        "nullable": col.nullable,
                        "description": col.description,
                    }
                    for col in schema.columns
                ],
                "row_count": schema.row_count,
            })
        else:
            tables = schema_discovery.discover_tables()
            return jsonify({"tables": tables})

    except Exception as e:
        logger.error("Schema info request failed: %s", e)
        return jsonify({"error": str(e)}), 500


@bp_sales_insight.route("/sales-insight/health", methods=["GET"])
def health_check():
    """
    Health check endpoint for the SalesInsight service.

    Response:
        {
            "status": "healthy" | "unhealthy",
            "components": {
                "snowflake": true | false,
                "openai": true | false
            }
        }
    """
    try:
        agent = get_sales_insight_agent()
        all_healthy = agent.test_connection()

        return jsonify({
            "status": "healthy" if all_healthy else "unhealthy",
            "components": {
                "snowflake": all_healthy,
                "openai": all_healthy,
            },
        }), 200 if all_healthy else 503

    except Exception as e:
        logger.error("Health check failed: %s", e)
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
        }), 503


@bp_sales_insight.route("/sales-insight/examples", methods=["GET"])
def get_example_queries():
    """
    Get example queries to help users understand what they can ask.

    Response:
        {
            "examples": [
                {
                    "question": "What are the top 10 products by revenue?",
                    "category": "ranking"
                },
                ...
            ]
        }
    """
    examples = [
        {
            "question": "What are the top 10 products by revenue this year?",
            "category": "ranking",
            "description": "Shows the highest-selling products by total revenue",
        },
        {
            "question": "Show me sales by region",
            "category": "distribution",
            "description": "Breaks down total sales by geographic region",
        },
        {
            "question": "Compare Q1 vs Q2 sales performance",
            "category": "comparison",
            "description": "Compares sales metrics between two quarters",
        },
        {
            "question": "Who are our top 5 customers by turnover?",
            "category": "ranking",
            "description": "Lists the customers with highest total purchases",
        },
        {
            "question": "What is the total revenue for fiscal year 2024?",
            "category": "aggregation",
            "description": "Calculates total revenue for a specific period",
        },
        {
            "question": "Show me the bottom 10 performing products",
            "category": "ranking",
            "description": "Identifies products with lowest sales",
        },
    ]

    return jsonify({"examples": examples})
