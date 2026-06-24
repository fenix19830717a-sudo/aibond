"""Unit tests for API routers using pytest + httpx AsyncClient."""

import pytest
from httpx import AsyncClient


# ── Health endpoint ──

@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    """GET /api/health returns ok status."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "aibond"


# ── Auth endpoints ──

@pytest.mark.asyncio
async def test_register(client: AsyncClient):
    """POST /api/auth/register creates a new user."""
    response = await client.post("/api/auth/register", json={
        "username": "newuser",
        "password": "Newpass1",
        "email": "newuser@example.com",
    })
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["user"]["username"] == "newuser"


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient):
    """POST /api/auth/register rejects duplicate username."""
    payload = {"username": "dupuser", "password": "Duppass1"}
    resp1 = await client.post("/api/auth/register", json=payload)
    assert resp1.status_code == 200

    resp2 = await client.post("/api/auth/register", json=payload)
    assert resp2.status_code == 400
    assert "already registered" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_login_valid(client: AsyncClient):
    """POST /api/auth/login returns token for valid credentials."""
    # Register first
    await client.post("/api/auth/register", json={
        "username": "loginuser",
        "password": "Loginpass1",
    })

    # Login
    response = await client.post("/api/auth/login", json={
        "username": "loginuser",
        "password": "Loginpass1",
    })
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["user"]["username"] == "loginuser"


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient):
    """POST /api/auth/login returns 401 for invalid credentials."""
    response = await client.post("/api/auth/login", json={
        "username": "nonexistent",
        "password": "wrongpass1",
    })
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    """POST /api/auth/login returns 401 when password is wrong."""
    await client.post("/api/auth/register", json={
        "username": "wrongpassuser",
        "password": "Correct1",
    })

    response = await client.post("/api/auth/login", json={
        "username": "wrongpassuser",
        "password": "Wrongpass1",
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_valid_token(client: AsyncClient, test_user):
    """POST /api/auth/me returns user info for valid token."""
    response = await client.post("/api/auth/me", json={
        "token": test_user["token"],
    })
    assert response.status_code == 200
    assert response.json()["username"] == "testuser"


@pytest.mark.asyncio
async def test_me_invalid_token(client: AsyncClient):
    """POST /api/auth/me returns 401 for invalid token."""
    response = await client.post("/api/auth/me", json={
        "token": "invalid-token-here",
    })
    assert response.status_code == 401


# ── Agent endpoints ──

@pytest.mark.asyncio
async def test_create_agent_token_with_auth(client: AsyncClient, auth_headers):
    """POST /api/agents/create-token creates agent with authentication."""
    response = await client.post(
        "/api/agents/create-token",
        json={"name": "Test Agent"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Agent"
    assert data["api_key"].startswith("abk_")
    assert "id" in data


@pytest.mark.asyncio
async def test_create_agent_token_without_auth(client: AsyncClient):
    """POST /api/agents/create-token returns 401 without authentication."""
    response = await client.post("/api/agents/create-token", json={"name": "No Auth Agent"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_agents_with_auth(client: AsyncClient, auth_headers):
    """GET /api/agents/ returns agents list with authentication."""
    response = await client.get("/api/agents/", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_list_agents_without_auth(client: AsyncClient):
    """GET /api/agents/ returns 401 without authentication."""
    response = await client.get("/api/agents/")
    assert response.status_code == 401


# ── Workflow endpoints ──

@pytest.mark.asyncio
async def test_create_workflow(client: AsyncClient, auth_headers):
    """POST /api/workflows/ creates a new workflow."""
    response = await client.post(
        "/api/workflows/",
        json={
            "name": "Test Workflow",
            "description": "A test workflow",
            "owner_id": "test-owner-id",
            "trigger_type": "manual",
            "definition": {
                "nodes": [
                    {
                        "id": "node1",
                        "data": {"nodeType": "trigger", "config": {}},
                    },
                    {
                        "id": "node2",
                        "data": {"nodeType": "output", "config": {"value": "done"}},
                    },
                ],
                "edges": [
                    {"source": "node1", "target": "node2"},
                ],
            },
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Workflow"
    assert "id" in data
    return data


@pytest.mark.asyncio
async def test_list_workflows(client: AsyncClient, auth_headers):
    """GET /api/workflows/ returns workflow list."""
    # Create a workflow first
    await client.post(
        "/api/workflows/",
        json={
            "name": "List Test Workflow",
            "owner_id": "test-owner-id",
        },
        headers=auth_headers,
    )

    response = await client.get("/api/workflows/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_workflow(client: AsyncClient, auth_headers):
    """GET /api/workflows/{id} returns a specific workflow."""
    # Create
    create_resp = await client.post(
        "/api/workflows/",
        json={"name": "Get Test", "owner_id": "test-owner-id"},
        headers=auth_headers,
    )
    workflow_id = create_resp.json()["id"]

    # Get
    response = await client.get(f"/api/workflows/{workflow_id}")
    assert response.status_code == 200
    assert response.json()["id"] == workflow_id


@pytest.mark.asyncio
async def test_get_workflow_not_found(client: AsyncClient):
    """GET /api/workflows/{id} returns 404 for nonexistent workflow."""
    response = await client.get("/api/workflows/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_workflow_definition(client: AsyncClient, auth_headers):
    """PUT /api/workflows/{id}/definition updates workflow definition."""
    # Create
    create_resp = await client.post(
        "/api/workflows/",
        json={"name": "Update Test", "owner_id": "test-owner-id"},
        headers=auth_headers,
    )
    workflow_id = create_resp.json()["id"]

    # Update
    new_definition = {
        "nodes": [
            {"id": "n1", "data": {"nodeType": "trigger", "config": {}}},
            {"id": "n2", "data": {"nodeType": "output", "config": {"value": "result"}}},
        ],
        "edges": [{"source": "n1", "target": "n2"}],
    }
    response = await client.put(
        f"/api/workflows/{workflow_id}/definition",
        json={"definition": new_definition},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_run_workflow(client: AsyncClient, auth_headers):
    """POST /api/workflows/{id}/run executes the workflow via engine."""
    # Create a workflow with trigger -> output nodes
    create_resp = await client.post(
        "/api/workflows/",
        json={
            "name": "Run Test Workflow",
            "owner_id": "test-owner-id",
            "definition": {
                "nodes": [
                    {"id": "trigger1", "data": {"nodeType": "trigger", "config": {}}},
                    {"id": "output1", "data": {"nodeType": "output", "config": {"value": "final_result"}}},
                ],
                "edges": [{"source": "trigger1", "target": "output1"}],
            },
        },
        headers=auth_headers,
    )
    workflow_id = create_resp.json()["id"]

    # Run
    response = await client.post(f"/api/workflows/{workflow_id}/run", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert "instance_id" in data
    assert "node_results" in data
    assert len(data["node_results"]) == 2


@pytest.mark.asyncio
async def test_run_workflow_not_found(client: AsyncClient, auth_headers):
    """POST /api/workflows/{id}/run returns 404 for nonexistent workflow."""
    response = await client.post("/api/workflows/nonexistent/run", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_run_workflow_with_ai_node(client: AsyncClient, auth_headers):
    """POST /api/workflows/{id}/run with AI node sends task via ws_manager."""
    create_resp = await client.post(
        "/api/workflows/",
        json={
            "name": "AI Node Workflow",
            "owner_id": "test-owner-id",
            "definition": {
                "nodes": [
                    {"id": "trigger1", "data": {"nodeType": "trigger", "config": {}}},
                    {
                        "id": "ai1",
                        "data": {
                            "nodeType": "ai",
                            "config": {
                                "agent_id": "test-agent-123",
                                "prompt": "Do something",
                                "title": "AI Task",
                            },
                        },
                    },
                    {"id": "output1", "data": {"nodeType": "output", "config": {"value": "done"}}},
                ],
                "edges": [
                    {"source": "trigger1", "target": "ai1"},
                    {"source": "ai1", "target": "output1"},
                ],
            },
        },
        headers=auth_headers,
    )
    workflow_id = create_resp.json()["id"]

    response = await client.post(f"/api/workflows/{workflow_id}/run", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    # Verify AI node result
    ai_result = next((r for r in data["node_results"] if r["node_type"] == "ai"), None)
    assert ai_result is not None
    assert ai_result["agent_id"] == "test-agent-123"


@pytest.mark.asyncio
async def test_run_workflow_with_condition_node(client: AsyncClient, auth_headers):
    """POST /api/workflows/{id}/run with condition node routes correctly."""
    create_resp = await client.post(
        "/api/workflows/",
        json={
            "name": "Condition Workflow",
            "owner_id": "test-owner-id",
            "definition": {
                "nodes": [
                    {"id": "trigger1", "data": {"nodeType": "trigger", "config": {}}},
                    {
                        "id": "cond1",
                        "data": {
                            "nodeType": "condition",
                            "config": {"expression": "true"},
                        },
                    },
                    {"id": "output_true", "data": {"nodeType": "output", "config": {"value": "yes"}}},
                    {"id": "output_false", "data": {"nodeType": "output", "config": {"value": "no"}}},
                ],
                "edges": [
                    {"source": "trigger1", "target": "cond1"},
                    {"source": "cond1", "target": "output_true", "data": {"handleId": "true"}},
                    {"source": "cond1", "target": "output_false", "data": {"handleId": "false"}},
                ],
            },
        },
        headers=auth_headers,
    )
    workflow_id = create_resp.json()["id"]

    response = await client.post(f"/api/workflows/{workflow_id}/run", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    # Should have executed trigger -> condition -> output_true (3 nodes)
    assert len(data["node_results"]) == 3


@pytest.mark.asyncio
async def test_run_workflow_with_human_review(client: AsyncClient, auth_headers):
    """POST /api/workflows/{id}/run with human_review pauses execution."""
    create_resp = await client.post(
        "/api/workflows/",
        json={
            "name": "Human Review Workflow",
            "owner_id": "test-owner-id",
            "definition": {
                "nodes": [
                    {"id": "trigger1", "data": {"nodeType": "trigger", "config": {}}},
                    {"id": "review1", "data": {"nodeType": "human_review", "config": {}}},
                    {"id": "output1", "data": {"nodeType": "output", "config": {"value": "after_review"}}},
                ],
                "edges": [
                    {"source": "trigger1", "target": "review1"},
                    {"source": "review1", "target": "output1"},
                ],
            },
        },
        headers=auth_headers,
    )
    workflow_id = create_resp.json()["id"]

    response = await client.post(f"/api/workflows/{workflow_id}/run", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending_review"
    assert data["current_node_id"] == "review1"
    # Only trigger + review executed (output not reached)
    assert len(data["node_results"]) == 2
